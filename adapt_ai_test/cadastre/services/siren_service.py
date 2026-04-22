"""
Service de recherche d'entreprises via l'API SIRENE (data.gouv.fr / INSEE).

Utilise l'API publique recherche-entreprises.api.gouv.fr (sans clé API)
et en bonus l'API SIRENE officielle de l'INSEE (avec clé optionnelle).
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

RECHERCHE_ENTREPRISES_URL = "https://recherche-entreprises.api.gouv.fr/search"
INSEE_SIRENE_URL = "https://api.insee.fr/entreprises/sirene/V3.11/siren"


def get_entreprise_by_siren(siren: str) -> dict | None:
    """
    Récupère les informations d'une entreprise à partir de son SIREN.

    Utilise en priorité l'API recherche-entreprises (publique, sans authentification).
    Si une clé INSEE est configurée (SIREN_API_KEY), utilise l'API SIRENE officielle.

    Retourne un dict avec les informations ou None si non trouvé.
    """
    # Nettoyage : on s'assure d'avoir 9 chiffres
    siren_clean = str(siren).strip().replace(" ", "")
    if not siren_clean.isdigit() or len(siren_clean) != 9:
        return None

    # Tentative via l'API officielle INSEE si une clé est disponible
    if settings.SIREN_API_KEY:
        result = _get_from_insee(siren_clean)
        if result:
            return result

    # Fallback : API publique recherche-entreprises
    return _get_from_recherche_entreprises(siren_clean)


def _get_from_recherche_entreprises(siren: str) -> dict | None:
    """Utilise l'API publique https://recherche-entreprises.api.gouv.fr."""
    try:
        resp = requests.get(
            RECHERCHE_ENTREPRISES_URL,
            params={"q": siren, "page": 1, "per_page": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            r = results[0]
            return {
                "siren": r.get("siren"),
                "nom": r.get("nom_raison_sociale") or r.get("nom_complet"),
                "siret_siege": r.get("siege", {}).get("siret"),
                "activite_principale": r.get("activite_principale"),
                "adresse": r.get("siege", {}).get("adresse"),
                "nature_juridique": r.get("nature_juridique"),
                "etat": r.get("etat_administratif"),
            }
    except requests.RequestException as e:
        logger.warning("Erreur API recherche-entreprises pour SIREN %s : %s", siren, e)
    return None


def _get_from_insee(siren: str) -> dict | None:
    """Utilise l'API officielle INSEE SIRENE (nécessite une clé API Bearer)."""
    try:
        resp = requests.get(
            f"{INSEE_SIRENE_URL}/{siren}",
            headers={
                "Authorization": f"Bearer {settings.SIREN_API_KEY}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json().get("uniteLegale", {})
        periods = data.get("periodesUniteLegale", [{}])
        current = periods[0] if periods else {}
        return {
            "siren": data.get("siren"),
            "nom": current.get("denominationUniteLegale") or current.get("nomUniteLegale"),
            "siret_siege": data.get("siretSiegeUniteLegale"),
            "activite_principale": current.get("activitePrincipaleUniteLegale"),
            "nature_juridique": current.get("categorieJuridiqueUniteLegale"),
            "etat": current.get("etatAdministratifUniteLegale"),
        }
    except requests.RequestException as e:
        logger.warning("Erreur API INSEE pour SIREN %s : %s", siren, e)
    return None
