"""
Script de téléchargement des données PCI (Parcellaire Express) pour le département 02 (Aisne).

Source : Géoplateforme IGN – données libres (Licence Ouverte Etalab 2.0)
URL : https://data.geopf.fr/telechargement/

Usage :
    python scripts/download_pci.py
    python scripts/download_pci.py --dept 02 --output data/
"""

import argparse
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# URL de téléchargement PCI sur la géoplateforme IGN
# Format : PARCELLAIRE-EXPRESS_2-1__SHP_LAMB93_D{dept}_2024-01-01
PCI_URL_TEMPLATE = (
    "https://data.geopf.fr/telechargement/download/PARCELLAIRE-EXPRESS/"
    "PARCELLAIRE-EXPRESS_2-1__SHP_LAMB93_D{dept}_2024-01-01/"
    "PARCELLAIRE-EXPRESS_2-1__SHP_LAMB93_D{dept}_2024-01-01.7z"
)

def download_with_progress(url: str, dest: Path):
    """Télécharge un fichier avec affichage de la progression."""
    print(f"Téléchargement depuis :\n  {url}")
    print(f"Destination : {dest}")

    def progress(block_num, block_size, total_size):
        if total_size > 0:
            downloaded = block_num * block_size
            pct = min(downloaded / total_size * 100, 100)
            bar = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
            mb = downloaded / 1_000_000
            total_mb = total_size / 1_000_000
            print(f"\r  [{bar}] {pct:.1f}% ({mb:.1f}/{total_mb:.1f} Mo)", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print()  # nouvelle ligne après la barre
        print(f"Téléchargement terminé : {dest} ({dest.stat().st_size / 1_000_000:.1f} Mo)")
    except urllib.error.HTTPError as e:
        print(f"\nErreur HTTP {e.code} : {e.reason}")
        print("Vérifiez l'URL ou téléchargez manuellement depuis :")
        print("  https://geoservices.ign.fr/parcellaire-express-pci")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nErreur réseau : {e.reason}")
        sys.exit(1)


def extract_7z(archive: Path, output_dir: Path):
    """Extrait une archive .7z avec p7zip."""
    import subprocess
    print(f"\nExtraction de {archive.name} vers {output_dir}...")
    result = subprocess.run(
        ["7z", "x", str(archive), f"-o{output_dir}", "-y"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Erreur lors de l'extraction :")
        print(result.stderr)
        sys.exit(1)
    print("Extraction terminée.")


def find_shapefiles(directory: Path, name_filter: str = "PARCELLE") -> list[Path]:
    """Trouve les fichiers shapefile (.shp) correspondant au filtre."""
    return list(directory.rglob(f"*{name_filter}*.shp"))


def main():
    parser = argparse.ArgumentParser(description="Télécharge les données PCI IGN")
    parser.add_argument("--dept", default="002", help="Code département (ex: 002, 075)")
    parser.add_argument("--output", default="data", help="Répertoire de destination")
    parser.add_argument("--no-extract", action="store_true", help="Ne pas extraire l'archive")
    args = parser.parse_args()

    dept = args.dept.zfill(3)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = PCI_URL_TEMPLATE.format(dept=dept)
    archive_name = f"PARCELLAIRE-EXPRESS_D{dept}.7z"
    archive_path = output_dir / archive_name

    if archive_path.exists():
        print(f"Archive déjà présente : {archive_path}")
        answer = input("Re-télécharger ? [o/N] ").strip().lower()
        if answer != "o":
            print("Téléchargement ignoré.")
        else:
            download_with_progress(url, archive_path)
    else:
        download_with_progress(url, archive_path)

    if not args.no_extract:
        extract_dir = output_dir / f"pci_D{dept}"
        extract_7z(archive_path, extract_dir)

        shapefiles = find_shapefiles(extract_dir)
        if shapefiles:
            print(f"\nFichiers shapefile trouvés ({len(shapefiles)}) :")
            for shp in shapefiles:
                print(f"  {shp}")
            print("\nPour importer dans PostGIS, exécutez :")
            print(f"  python scripts/import_pci.py --shp {shapefiles[0]}")
        else:
            print(f"\nAucun shapefile trouvé dans {extract_dir}")
            print("Vérifiez le contenu de l'archive.")


if __name__ == "__main__":
    main()
