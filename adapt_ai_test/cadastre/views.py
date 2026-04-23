from django.contrib.gis.geos import Polygon
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Parcelle
from .serializers import ParcelleSerializer, ParcelleListSerializer
from .services.majic_service import get_siren_from_majic
from .services.siren_service import get_entreprise_by_siren


class ParcelleListView(APIView):
    """
    GET /api/parcelles/?bbox=xmin,ymin,xmax,ymax
    Retourne les parcelles dans la bbox donnée en GeoJSON FeatureCollection.
    Limité à 1000 entités pour éviter les surcharges.
    """

    def get(self, request):
        bbox_param = request.query_params.get("bbox")
        if not bbox_param:
            return Response(
                {"error": "Paramètre 'bbox' requis (xmin,ymin,xmax,ymax en WGS84)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coords = [float(x) for x in bbox_param.split(",")]
            if len(coords) != 4:
                raise ValueError
            xmin, ymin, xmax, ymax = coords
        except ValueError:
            return Response(
                {"error": "Format bbox invalide. Attendu : xmin,ymin,xmax,ymax"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bbox_geom = Polygon.from_bbox((xmin, ymin, xmax, ymax))
        bbox_geom.srid = 4326

        qs = Parcelle.objects.filter(geom__intersects=bbox_geom)[:1000]
        serializer = ParcelleListSerializer(qs, many=True)

        return Response(
            {
                "type": "FeatureCollection",
                "features": serializer.data["features"],
                "count": len(serializer.data["features"]),
            }
        )


class ParcelleDetailView(APIView):
    """
    GET /api/parcelles/<id>/
    Retourne le détail d'une parcelle en GeoJSON Feature.
    """

    def get(self, request, pk):
        try:
            parcelle = Parcelle.objects.get(pk=pk)
        except Parcelle.DoesNotExist:
            return Response({"error": "Parcelle non trouvée"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ParcelleSerializer(parcelle)
        return Response(serializer.data)


class ParcelleProprietaireView(APIView):
    """
    GET /api/parcelles/<id>/proprietaire/
    Récupère le SIREN du propriétaire via MAJIC/API Carto,
    puis les informations de l'entreprise via l'API SIRENE.
    """

    def get(self, request, pk):
        try:
            parcelle = Parcelle.objects.get(pk=pk)
        except Parcelle.DoesNotExist:
            return Response({"error": "Parcelle non trouvée"}, status=status.HTTP_404_NOT_FOUND)

        siren = get_siren_from_majic(
            parcelle.code_dep, parcelle.code_com, parcelle.section, parcelle.numero
        )

        if not siren:
            return Response(
                {
                    "parcelle_idu": parcelle.idu,
                    "siren": None,
                    "message": (
                        "Aucun SIREN trouvé. Ce propriétaire est probablement une personne physique "
                        "(non accessible publiquement pour des raisons CNIL) "
                        "ou les données ne sont pas disponibles via l'API."
                    ),
                    "entreprise": None,
                }
            )

        entreprise = get_entreprise_by_siren(siren)

        return Response(
            {
                "parcelle_idu": parcelle.idu,
                "siren": siren,
                "entreprise": entreprise,
            }
        )
