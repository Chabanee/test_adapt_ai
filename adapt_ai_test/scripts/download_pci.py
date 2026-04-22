"""
Script d'import des parcelles cadastrales via le WFS IGN Géoplateforme.

Le téléchargement bulk (archive .7z) de la Géoplateforme IGN n'est plus
accessible sans authentification. Ce script utilise le service WFS public
qui ne requiert aucune clé d'API.

Source : https://data.geopf.fr/wfs/ows
Couche  : CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle
Licence : Licence Ouverte Etalab 2.0

Usage :
    # Import complet du département 02 (env. 999 000 parcelles, ~45 min)
    python scripts/download_pci.py

    # Import limité pour test rapide
    python scripts/download_pci.py --dept 02 --limit 5000

    # Import d'une commune spécifique (code INSEE)
    python scripts/download_pci.py --commune 02408
"""

import argparse
import os
import sys
import time
import django
from pathlib import Path

# Configure Django
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adapt_ai_test.settings")
django.setup()

import requests
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.db import transaction
from cadastre.models import Parcelle

WFS_URL = "https://data.geopf.fr/wfs/ows"
TYPENAME = "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle"
PAGE_SIZE = 1000  # max fiable par requête WFS
MAX_RETRIES = 3
BATCH_SIZE = 500  # insertions par transaction


def _build_url(**kwargs) -> str:
    """
    Construit l'URL WFS sans encoder les caractères spéciaux du CQL_FILTER.
    Le serveur IGN rejette les apostrophes encodées (%27) dans les filtres CQL.
    """
    parts = "&".join(f"{k}={v}" for k, v in kwargs.items())
    return f"{WFS_URL}?{parts}"


def wfs_page(dept: str = None, commune: str = None, start: int = 0, count: int = PAGE_SIZE) -> dict:
    """Récupère une page de features WFS."""
    if commune:
        cql = f"code_insee='{commune}'"
    elif dept:
        cql = f"code_dep='{dept}'"
    else:
        raise ValueError("Fournissez --dept ou --commune")

    url = _build_url(
        SERVICE="WFS", VERSION="2.0.0", REQUEST="GetFeature",
        TYPENAMES=TYPENAME, OUTPUTFORMAT="application/json",
        COUNT=count, STARTINDEX=start, CQL_FILTER=cql,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_RETRIES:
                raise
            wait = attempt * 5
            print(f"\n  Tentative {attempt}/{MAX_RETRIES} échouée ({e}), retry dans {wait}s...")
            time.sleep(wait)


def count_features(dept: str = None, commune: str = None) -> int:
    """Compte le nombre total de features disponibles."""
    if commune:
        cql = f"code_insee='{commune}'"
    else:
        cql = f"code_dep='{dept}'"

    url = _build_url(
        SERVICE="WFS", VERSION="2.0.0", REQUEST="GetFeature",
        TYPENAMES=TYPENAME, RESULTTYPE="hits", CQL_FILTER=cql,
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    # Cherche numberMatched ou numberOfFeatures dans le XML de réponse
    import re
    for attr in ("numberMatched", "numberOfFeatures"):
        m = re.search(rf'{attr}="(\d+)"', resp.text)
        if m:
            return int(m.group(1))
    return 0


def feature_to_parcelle(f: dict) -> Parcelle | None:
    """Convertit un GeoJSON feature en instance Parcelle."""
    p = f.get("properties", {})
    geom_data = f.get("geometry")
    if not geom_data or not p.get("idu"):
        return None

    try:
        import json
        geom = GEOSGeometry(json.dumps(geom_data), srid=4326)
        if isinstance(geom, Polygon):
            geom = MultiPolygon(geom)
        elif not isinstance(geom, MultiPolygon):
            return None
    except Exception:
        return None

    return Parcelle(
        idu=p["idu"],
        code_dep=p.get("code_dep", ""),
        code_com=p.get("code_com", ""),
        nom_com=p.get("nom_com", ""),
        section=p.get("section", ""),
        numero=p.get("numero", ""),
        feuille=int(p.get("feuille") or 0),
        contenance=float(p["contenance"]) if p.get("contenance") is not None else None,
        geom=geom,
    )


def import_wfs(dept: str = None, commune: str = None, truncate: bool = False, limit: int = None):
    print("=== Import WFS – Parcellaire Express IGN ===")
    print(f"Filtre : {'département ' + dept if dept else 'commune ' + commune}")

    total = count_features(dept=dept, commune=commune)
    if limit:
        total = min(total, limit)
    print(f"Parcelles à importer : {total:,}")

    if truncate:
        existing = Parcelle.objects.count()
        print(f"Suppression de {existing:,} parcelles existantes...")
        Parcelle.objects.all().delete()

    imported = 0
    skipped = 0
    start = 0

    while start < total:
        count = min(PAGE_SIZE, total - start)
        print(f"\r  [{imported:,}/{total:,}] Page {start//PAGE_SIZE + 1}...", end="", flush=True)

        try:
            data = wfs_page(dept=dept, commune=commune, start=start, count=count)
        except Exception as e:
            print(f"\nErreur page {start}: {e}")
            break

        features = data.get("features", [])
        if not features:
            break

        batch = []
        for f in features:
            p = feature_to_parcelle(f)
            if p:
                batch.append(p)
            else:
                skipped += 1

        if batch:
            with transaction.atomic():
                Parcelle.objects.bulk_create(batch, ignore_conflicts=True)
            imported += len(batch)

        start += len(features)
        if len(features) < count:
            break  # dernière page

    print(f"\n\nImport terminé :")
    print(f"  Importées : {imported:,}")
    print(f"  Ignorées  : {skipped}")
    print(f"  Total DB  : {Parcelle.objects.count():,}")


def main():
    parser = argparse.ArgumentParser(
        description="Import parcelles cadastrales via WFS IGN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scripts/download_pci.py --dept 02
  python scripts/download_pci.py --dept 02 --limit 10000
  python scripts/download_pci.py --commune 02408 --truncate
        """
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dept", metavar="CODE", help="Code département (ex: 02)")
    group.add_argument("--commune", metavar="INSEE", help="Code INSEE commune (ex: 02408)")
    parser.add_argument("--truncate", action="store_true", help="Vide la table avant import")
    parser.add_argument("--limit", type=int, default=None, help="Limite le nombre de parcelles")
    # Argument legacy ignoré (conservé pour compatibilité avec ancienne doc)
    parser.add_argument("--output", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    import_wfs(
        dept=args.dept,
        commune=args.commune,
        truncate=args.truncate,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
