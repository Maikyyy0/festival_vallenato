from django.contrib import admin

from .models import Categoria, Edicion, Opcion, Votacion, Voto

admin.site.site_header = "Festival de la Leyenda Vallenata · Administración de votaciones"
admin.site.site_title = "Votaciones Festival Vallenato"
admin.site.index_title = "Gestión de ediciones, categorías, votaciones y opciones"


class CategoriaInline(admin.TabularInline):
    model = Categoria
    extra = 0
    fields = ("nombre", "orden", "activa")
    show_change_link = True


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1
    fields = ("nombre", "descripcion", "orden", "activa")


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    list_display = ("anio", "nombre", "numero", "homenaje", "fecha_inicio", "fecha_fin", "estado", "total_categorias")
    list_filter = ("estado",)
    search_fields = ("nombre", "homenaje")
    list_editable = ("estado",)
    list_display_links = ("anio", "nombre")
    inlines = [CategoriaInline]

    @admin.display(description="categorías")
    def total_categorias(self, obj):
        return obj.categorias.count()


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edicion", "orden", "activa", "total_votaciones")
    list_filter = ("edicion", "activa")
    search_fields = ("nombre", "descripcion")
    list_editable = ("orden", "activa")
    list_select_related = ("edicion",)

    @admin.display(description="votaciones")
    def total_votaciones(self, obj):
        return obj.votaciones.count()


@admin.register(Votacion)
class VotacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "fecha_apertura", "fecha_cierre", "estado", "estado_publico", "total_opciones")
    list_filter = ("estado", "activa", "categoria__edicion", "categoria")
    search_fields = ("titulo", "descripcion")
    list_editable = ("estado",)
    list_select_related = ("categoria", "categoria__edicion")
    inlines = [OpcionInline]
    actions = ["abrir_votaciones", "cerrar_votaciones"]

    @admin.display(description="estado público")
    def estado_publico(self, obj):
        return obj.estado_publico

    @admin.display(description="opciones")
    def total_opciones(self, obj):
        return obj.opciones.count()

    @admin.action(description="Abrir las votaciones seleccionadas")
    def abrir_votaciones(self, request, queryset):
        n = queryset.update(estado=Votacion.Estado.ABIERTA)
        self.message_user(request, f"{n} votación(es) marcada(s) como abiertas.")

    @admin.action(description="Cerrar las votaciones seleccionadas")
    def cerrar_votaciones(self, request, queryset):
        n = queryset.update(estado=Votacion.Estado.CERRADA)
        self.message_user(request, f"{n} votación(es) cerrada(s).")


@admin.register(Opcion)
class OpcionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "votacion", "orden", "activa")
    list_filter = ("activa", "votacion__categoria__edicion", "votacion")
    search_fields = ("nombre", "descripcion")
    list_editable = ("orden", "activa")
    list_select_related = ("votacion",)


@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    """Registro de votos: solo lectura, para preservar la integridad del conteo."""

    list_display = ("fecha_hora", "usuario", "votacion", "opcion")
    list_filter = ("votacion__categoria__edicion", "votacion")
    search_fields = ("usuario__email", "usuario__username", "opcion__nombre")
    list_select_related = ("usuario", "votacion", "opcion")
    readonly_fields = ("usuario", "votacion", "opcion", "fecha_hora")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
