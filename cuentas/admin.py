from django.contrib import admin

from .models import Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "acepta_tratamiento_datos", "fecha_autorizacion")
    list_filter = ("acepta_tratamiento_datos",)
    search_fields = ("usuario__email", "usuario__first_name")
    readonly_fields = ("usuario", "acepta_tratamiento_datos", "fecha_autorizacion")
