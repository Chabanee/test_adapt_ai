# Application Cadastrale – Aisne (Département 02)

Application web permettant de visualiser les parcelles cadastrales du département de l'Aisne sur une carte interactive, et d'afficher le SIREN du propriétaire pour les personnes morales.

## Architecture

```
├── adapt_ai_test/          # Projet Django principal
│   ├── cadastre/           # Application Django (modèles, API, services)
│   │   ├── models.py       # Modèle Parcelle (PostGIS)
│   │   ├── views.py        # API REST (list, detail, propriétaire)
│   │   ├── serializers.py  # Sérialisation GeoJSON
│   │   └── services/
│   │       ├── majic_service.py   # API Carto IGN (MAJIC)
│   │       └── siren_service.py   # API SIRENE INSEE
│   ├── templates/          # Frontend HTML (Leaflet.js)
│   ├── static/             # CSS et JavaScript
│   └── scripts/            # Scripts de données
│       ├── download_pci.py # Téléchargement données PCI
│       └── import_pci.py   # Import shapefile → PostGIS
├── docker-compose.yml
└── Dockerfile
```

## Prérequis

- Docker et Docker Compose
- (Optionnel, hors Docker) Python 3.12, GDAL 3.x, PostgreSQL 16 + PostGIS

## Installation et démarrage

### 1. Cloner et configurer

```bash
git clone <repo-url>
cd adapt_ai_test

cp .env.example .env
# Éditez .env si nécessaire
```

### 2. Démarrer avec Docker Compose

```bash
docker-compose up --build
```

Cela lance :
- **PostgreSQL 16 + PostGIS** sur le port 5432
- **Django** sur http://localhost:8000

### 3. Créer les tables

Dans un autre terminal :

```bash
docker-compose exec backend python manage.py migrate
```

### 4. Importer les données PCI via WFS (Aisne – département 02)

Les données sont importées directement depuis le service WFS public de la Géoplateforme IGN (aucun téléchargement de fichier requis).

```bash
# Import complet (~999 000 parcelles, ~45 min selon connexion)
docker-compose exec backend python scripts/download_pci.py --dept 02

# Import rapide pour tester (10 000 parcelles)
docker-compose exec backend python scripts/download_pci.py --dept 02 --limit 10000

# Import d'une seule commune (ex : Laon, code INSEE 02408)
docker-compose exec backend python scripts/download_pci.py --commune 02408
```

> Les données PCI sont publiées par l'IGN sous licence Ouverte Etalab 2.0.
> Source WFS : `https://data.geopf.fr/wfs/ows`

### 6. Accéder à l'application

Ouvrez http://localhost:8000 dans votre navigateur.

Zoomez sur le département de l'Aisne (zoom ≥ 14) pour voir les parcelles.
Cliquez sur une parcelle pour afficher ses informations, puis sur **"Rechercher le propriétaire"**.

---

## API REST

### `GET /api/parcelles/?bbox=xmin,ymin,xmax,ymax`

Retourne les parcelles dans la bounding box (WGS84) en GeoJSON FeatureCollection.

```
GET /api/parcelles/?bbox=3.35,49.53,3.40,49.57
```

### `GET /api/parcelles/<id>/`

Détail d'une parcelle en GeoJSON Feature.

### `GET /api/parcelles/<id>/proprietaire/`

Récupère le SIREN du propriétaire (personnes morales uniquement) via :
1. **API Carto IGN** (https://apicarto.ign.fr) pour les données MAJIC
2. **API SIRENE** (https://recherche-entreprises.api.gouv.fr) pour les informations d'entreprise

---

## Données MAJIC et SIREN

Les fichiers MAJIC (DGFiP) contiennent les informations fiscales des propriétaires.
Seul le SIREN des **personnes morales** (entreprises, collectivités) est accessible publiquement.
Les propriétaires personnes physiques sont protégés par la CNIL.

Pour accéder aux données SIRENE enrichies, obtenez une clé API INSEE :
https://api.insee.fr/catalogue/ et renseignez `SIREN_API_KEY` dans `.env`.

---

## Développement local (sans Docker)

```bash
# Prérequis : PostgreSQL + PostGIS + GDAL installés
pip install -r requirements.txt

export DATABASE_URL=postgis://user:password@localhost:5432/cadastre
python manage.py migrate
python manage.py runserver
```

---

## Technologies utilisées

| Composant | Technologie |
|-----------|-------------|
| Backend | Django 5.1 + GeoDjango |
| API | Django REST Framework + DRF-GIS |
| Base de données | PostgreSQL 16 + PostGIS |
| Frontend | HTML/JS vanilla + Leaflet.js |
| Fond de carte | OpenStreetMap |
| Données cadastrales | PCI IGN (Géoplateforme) |
| Données SIREN | API Carto IGN + API SIRENE INSEE |

## Contact

Pour toute question : contact@adapt-ai.fr
