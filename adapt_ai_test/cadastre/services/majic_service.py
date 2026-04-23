"""
Service d'accès aux données MAJIC / propriétaires de parcelles cadastrales.

Situation réelle des données publiques :
- L'API Carto IGN (/api/cadastre/parcelle) retourne uniquement les données
  géométriques et administratives, PAS les informations sur les propriétaires.
- Les fichiers MAJIC complets (DGFiP) sont soumis à une convention d'accès
  spécifique ; les données propriétaires (personnes physiques) sont protégées CNIL.
- Seuls les SIREN des personnes morales (entreprises, communes, établissements
  publics) peuvent être retrouvés via des sources tierces publiques.

Stratégie implémentée :
  1. API Carto – vérifie si un champ SIREN est présent dans les métadonnées
     (uniquement pour certaines parcelles de propriétaires institutionnels).
  2. Fallback DVF (Demandes de Valeurs Foncières) – cherche une transaction
     récente impliquant la parcelle et extrait le SIREN de l'acheteur/vendeur
     professionnel si disponible.
"""

import requests
import logging

logger = logging.getLogger(__name__)

APICARTO_BASE = "https://apicarto.ign.fr/api/cadastre"
DVF_API_BASE = "https://tabular-api.data.gouv.fr/api/resources"
# Ressource DVF open data (Etalab) – transactions immobilières avec SIREN
DVF_RESOURCE_ID = "90a98de0-f562-4328-aa16-fe0dd1dca60f"


def get_parcelle_apicarto(code_dep: str, code_com: str, section: str, numero: str) -> dict | None:
    """
    Récupère les données cadastrales via l'API Carto IGN.
    Paramètres corrects : code_dep + code_com séparés (pas code_insee agrégé).
    """
    params = {
        "code_dep": code_dep,
        "code_com": code_com,
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
        logger.warning("Erreur API Carto %s/%s/%s/%s : %s", code_dep, code_com, section, numero, e)
    return None


def _siren_from_dvf(code_insee: str, section: str, numero: str) -> str | None:
    """
    Cherche un SIREN professionnel dans les transactions DVF pour cette parcelle.
    Le DVF (Demandes de Valeurs Foncières) est un jeu de données open data DGFiP
    qui recense les mutations immobilières depuis 2014.
    Seules les personnes morales (entreprises, sociétés) ont un SIREN dans ce fichier.
    """
    idu_like = f"{code_insee}000{section}{numero}"
    try:
        resp = requests.get(
            f"{DVF_API_BASE}/{DVF_RESOURCE_ID}/data/",
            params={"idpar__contains": idu_like, "page_size": 5},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        for row in data.get("data", []):
            # Cherche un SIREN dans les champs acheteur/vendeur
            for field in ("siren_acheteur1", "siren_acheteur2", "siren_vendeur1", "siren_vendeur2"):
                val = row.get(field, "")
                if val and str(val).isdigit() and len(str(val)) == 9:
                    return str(val)
    except requests.RequestException as e:
        logger.debug("DVF non disponible pour %s : %s", idu_like, e)
    return None


def get_siren_from_majic(code_dep: str, code_com: str, section: str, numero: str) -> str | None:
    """
    Tente de récupérer le SIREN du propriétaire d'une parcelle.

    1. Interroge l'API Carto IGN (données cadastrales).
    2. Cherche dans le DVF (transactions récentes avec SIREN acheteur/vendeur).

    Retourne le SIREN (9 chiffres) ou None si le propriétaire est une
    personne physique (non accessible publiquement) ou inconnu.
    """
    # Étape 1 : API Carto (champs siren/dnupro si disponibles)
    info = get_parcelle_apicarto(code_dep, code_com, section, numero)
    if info:
        for field in ("siren", "dnupro", "siren_proprietaire"):
            val = info.get(field)
            if val and str(val).isdigit() and len(str(val)) == 9:
                return str(val)

    # Étape 2 : DVF – transactions immobilières récentes
    code_insee = code_dep + code_com.zfill(3)
    return _siren_from_dvf(code_insee, section, numero)
