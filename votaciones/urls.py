from django.urls import path

from . import views

app_name = "votaciones"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ediciones/", views.ediciones, name="ediciones"),
    path("ediciones/<int:anio>/", views.edicion_detalle, name="edicion_detalle"),
    path("categorias/<int:pk>/", views.categoria_detalle, name="categoria_detalle"),
    path("votaciones/<int:pk>/", views.votacion_detalle, name="votacion_detalle"),
    path("votaciones/<int:pk>/votar/", views.votar, name="votar"),
    path("mis-votos/", views.mis_votos, name="mis_votos"),
]
