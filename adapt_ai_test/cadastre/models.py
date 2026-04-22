from django.contrib.gis.db import models


class Parcelle(models.Model):
    """
    Représente une parcelle cadastrale issue des données PCI (Parcellaire Express IGN).
    La géométrie est stockée en WGS84 (EPSG:4326) pour faciliter l'affichage web.
    """

    # Identifiant cadastral unique (code INSEE + section + numéro)
    idu = models.CharField(max_length=20, unique=True, db_index=True)

    # Découpage administratif
    code_dep = models.CharField(max_length=3, db_index=True)
    code_com = models.CharField(max_length=5, db_index=True)
    nom_com = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=2, db_index=True)
    numero = models.CharField(max_length=4)
    feuille = models.IntegerField(default=0)

    # Superficie en m²
    contenance = models.FloatField(null=True, blank=True)

    # Géométrie (polygone en WGS84)
    geom = models.MultiPolygonField(srid=4326, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["code_dep", "code_com"]),
        ]
        verbose_name = "Parcelle cadastrale"

    @property
    def code_insee(self) -> str:
        """Code INSEE complet sur 5 chiffres (ex: '02478')."""
        return self.code_dep + self.code_com.zfill(3)

    def __str__(self):
        return self.idu
