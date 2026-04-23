from django.urls import path
from .views import ParcelleListView, ParcelleDetailView, ParcelleProprietaireView, SirenSearchView

urlpatterns = [
    path("parcelles/", ParcelleListView.as_view(), name="parcelles-list"),
    path("parcelles/<int:pk>/", ParcelleDetailView.as_view(), name="parcelles-detail"),
    path("parcelles/<int:pk>/proprietaire/", ParcelleProprietaireView.as_view(), name="parcelles-proprietaire"),
    path("siren/<str:siren>/", SirenSearchView.as_view(), name="siren-search"),
]
