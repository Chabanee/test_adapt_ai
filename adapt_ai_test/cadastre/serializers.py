from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Parcelle


class ParcelleSerializer(GeoFeatureModelSerializer):
    """Sérialise une parcelle en GeoJSON Feature."""

    class Meta:
        model = Parcelle
        geo_field = "geom"
        fields = ["id", "idu", "code_dep", "code_com", "nom_com", "section", "numero", "contenance"]


class ParcelleListSerializer(GeoFeatureModelSerializer):
    """Version allégée pour les listes (bbox) sans les données administratives détaillées."""

    class Meta:
        model = Parcelle
        geo_field = "geom"
        fields = ["id", "idu", "code_com", "nom_com", "section", "numero", "contenance"]
