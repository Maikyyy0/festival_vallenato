from django.urls import path

from . import api, views

app_name = "votaciones"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ediciones/", views.ediciones, name="ediciones"),
    path("ediciones/<int:anio>/", views.edicion_detalle, name="edicion_detalle"),
    path("categorias/<int:pk>/", views.categoria_detalle, name="categoria_detalle"),
    path("votaciones/<int:pk>/", views.votacion_detalle, name="votacion_detalle"),
    # Entrega 3: módulo de votación
    path("votaciones/<int:pk>/votar/", views.seleccionar_opcion, name="seleccionar_opcion"),
    path("votaciones/<int:pk>/confirmar/", views.confirmar_voto, name="confirmar_voto"),
    path("mis-votos/", views.mis_votos, name="mis_votos"),
    # Entrega 4: resultados
    path("resultados/", views.resultados, name="resultados"),
    # Panel de visualización dinámica de datos
    path("panel/", views.panel, name="panel"),
    # API GET de consulta (solo lectura)
    path("api/categorias/", api.api_categorias, name="api_categorias"),
    path("api/resumen/", api.resumen, name="api_resumen"),
    path("api/ediciones/", api.ediciones, name="api_ediciones"),
    path("api/ediciones/<int:anio>/categorias/", api.edicion_categorias, name="api_edicion_categorias"),
    path("api/categorias/<int:pk>/votaciones/", api.categoria_votaciones, name="api_categoria_votaciones"),
    path("api/votaciones/<int:pk>/", api.votacion_detalle, name="api_votacion_detalle"),
    path("api/votaciones/<int:pk>/resultados/", api.votacion_resultados, name="api_votacion_resultados"),
    path("api/mis-votos/", api.mis_votos, name="api_mis_votos"),
]
