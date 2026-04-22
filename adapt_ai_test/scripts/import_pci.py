"""
Script d'import des données PCI (shapefile) dans la base PostGIS.

Lit le shapefile PARCELLE.shp (CRS Lambert 93 / EPSG:2154) et insère les
données dans la table Parcelle via Django ORM après reprojection en WGS84.

Prérequis : GDAL installé, Django configuré avec PostGIS.

Usage :
    # Depuis la racine du projet Django
    python manage.py shell < scripts/import_pci.py
    # Ou directement :
    DJANGO_SETTINGS_MODULE=adapt_ai_test.settings python scripts/import_pci.py --shp data/pci_D002/.../PARCELLE.shp
"""

import argparse
import os
import sys
import django
from pathlib import Path

# Configure Django si exécuté directement (hors manage.py shell)
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adapt_ai_test.settings")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
django.setup()

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.db import transaction
from cadastre.models import Parcelle


BATCH_SIZE = 500


def to_multipolygon(geom: GEOSGeometry) -> MultiPolygon:
    """Normalise une géométrie en MultiPolygon."""
    if isinstance(geom, Polygon):
        return MultiPolygon(geom)
    if isinstance(geom, MultiPolygon):
        return geom
    raise ValueError(f"Type de géométrie inattendu : {geom.geom_type}")


def import_shapefile(shp_path: str, truncate: bool = False, limit: int = None):
    shp = Path(shp_path)
    if not shp.exists():
        print(f"Erreur : fichier introuvable : {shp}")
        sys.exit(1)

    print(f"Ouverture de {shp.name}...")
    ds = DataSource(str(shp))
    layer = ds[0]

    print(f"  Couche    : {layer.name}")
    print(f"  CRS       : {layer.srs.name}")
    print(f"  Entités   : {len(layer)}")
    print(f"  Champs    : {layer.fields}")

    if truncate:
        count = Parcelle.objects.count()
        print(f"\nSuppression de {count} parcelles existantes...")
        Parcelle.objects.all().delete()

    total = len(layer) if limit is None else min(limit, len(layer))
    batch = []
    imported = 0
    skipped = 0

    print(f"\nImport de {total} parcelles...")

    for i, feature in enumerate(layer):
        if limit and i >= limit:
            break

        try:
            # Récupère la géométrie et la reprojette en WGS84 (EPSG:4326)
            geom_wkt = feature.geom.wkt
            geom = GEOSGeometry(geom_wkt, srid=layer.srs.srid or 2154)
            geom.transform(4326)
            mp = to_multipolygon(geom)

            # Champs du shapefile PCI (noms standardisés IGN)
            idu = (feature.get("IDU") or feature.get("idu") or "").strip()
            code_dep = (feature.get("CODE_DEP") or feature.get("code_dep") or "").strip()
            code_com = (feature.get("CODE_COM") or feature.get("code_com") or "").strip()
            nom_com = (feature.get("NOM_COM") or feature.get("nom_com") or "").strip()
            section = (feature.get("SECTION") or feature.get("section") or "").strip()
            numero = (feature.get("NUMERO") or feature.get("numero") or "").strip()
            contenance = feature.get("CONTENANCE") or feature.get("contenance")
            feuille = feature.get("FEUILLE") or feature.get("feuille") or 0

            if not idu:
                skipped += 1
                continue

            batch.append(
                Parcelle(
                    idu=idu,
                    code_dep=code_dep,
                    code_com=code_com,
                    nom_com=nom_com,
                    section=section,
                    numero=numero,
                    feuille=int(feuille) if feuille else 0,
                    contenance=float(contenance) if contenance else None,
                    geom=mp,
                )
            )

            if len(batch) >= BATCH_SIZE:
                with transaction.atomic():
                    Parcelle.objects.bulk_create(batch, ignore_conflicts=True)
                imported += len(batch)
                batch = []
                pct = (i + 1) / total * 100
                print(f"\r  Progression : {pct:.1f}% ({imported} importées, {skipped} ignorées)", end="")

        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"\n  Avertissement entité {i} : {e}")

    # Dernier batch
    if batch:
        with transaction.atomic():
            Parcelle.objects.bulk_create(batch, ignore_conflicts=True)
        imported += len(batch)

    print(f"\n\nImport terminé :")
    print(f"  Importées : {imported}")
    print(f"  Ignorées  : {skipped}")
    print(f"  Total DB  : {Parcelle.objects.count()}")


def main():
    parser = argparse.ArgumentParser(description="Importe le shapefile PCI dans PostGIS")
    parser.add_argument("--shp", required=True, help="Chemin vers PARCELLE.shp")
    parser.add_argument("--truncate", action="store_true", help="Vide la table avant import")
    parser.add_argument("--limit", type=int, default=None, help="Limite le nombre d'entités importées")
    args = parser.parse_args()

    import_shapefile(args.shp, truncate=args.truncate, limit=args.limit)


if __name__ == "__main__":
    main()
