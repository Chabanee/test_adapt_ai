"""
Service d'accès aux données MAJIC via l'API Carto de l'IGN.

L'API Carto (https://apicarto.ign.fr) permet de récupérer des informations
cadastrales enrichies, notamment pour identifier les propriétaires de parcelles.

Note : les données MAJIC complètes (propriétaires personnes physiques) sont
soumises à des restrictions d'accès CNIL. Seuls les SIREN des personnes morales
(entreprises, collectivités) sont accessibles librement.
"""

import requests
import logging

logger = logging.getLogger(__name__)

APICARTO_BASE = "https://apicarto.ign.fr/api/cadastre"


def get_parcelle_info(code_insee: str, section: str, numero: str) -> dict | None:
    """
    Récupère les informations cadastrales d'une parcelle via l'API Carto IGN.

    Retourne un dict avec les champs disponibles ou None en cas d'erreur.
    """
    params = {
        "code_insee": code_insee,
        "section": section,
        "numero": numero,
        "_limit": 1,
    }
    try:
        resp = requests.get(f"{APICARTO_BASE}/parcelle", params=params, timeout=10)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            return features[0].get("properties", {})
    except requests.RequestException as e:
        logger.warning("Erreur API Carto pour %s/%s/%s : %s", code_insee, section, numero, e)
    return None


def get_siren_from_majic(code_insee: str, section: str, numero: str) -> str | None:
    """
    Tente de récupérer le SIREN du propriétaire d'une parcelle.

    Utilise d'abord l'API Carto. Le champ SIREN n'est disponible que pour
    les propriétaires personnes morales (entreprises).

    Retourne le SIREN (chaîne de 9 chiffres) ou None.
    """
    info = get_parcelle_info(code_insee, section, numero)
    if not info:
        return None

    # Le champ peut s'appeler 'siren' ou être dans 'dnupro' selon la version de l'API
    siren = info.get("siren") or info.get("dnupro")

    # Validation basique : un SIREN valide fait 9 chiffres
    if siren and str(siren).isdigit() and len(str(siren)) == 9:
        return str(siren)
    return None
