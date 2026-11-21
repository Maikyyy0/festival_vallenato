from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count

from .models import Categoria, Edicion, Opcion, Votacion, Voto

admin.site.site_header = "Festival de la Leyenda Vallenata · Administración de votaciones"
admin.site.site_title = "Votaciones Festival Vallenato"
admin.site.index_title = "Gestión de ediciones, categorías, votaciones y opciones"


def un_anio_despues(fecha):
    try:
        return fecha.replace(year=fecha.year + 1)
    except ValueError:  # 29 de febrero
        return fecha.replace(year=fecha.year + 1, day=28)


@transaction.atomic
def duplicar_edicion(edicion):
    """Copia la estructura Edición → Categoría → Votación → Opción un año después."""
    nueva = Edicion.objects.create(
        nombre=edicion.nombre.replace(str(edicion.anio), str(edicion.anio + 1)),
        anio=edicion.anio + 1,
        numero=edicion.numero + 1 if edicion.numero else None,
        homenaje="",
        descripcion=edicion.descripcion,
        fecha_inicio=un_anio_despues(edicion.fecha_inicio),
        fecha_fin=un_anio_despues(edicion.fecha_fin),
        estado=Edicion.Estado.BORRADOR,
    )
    for categoria in edicion.categorias.all():
        nueva_categoria = Categoria.objects.create(
            edicion=nueva, nombre=categoria.nombre, descripcion=categoria.descripcion,
            orden=categoria.orden, activa=categoria.activa,
        )
        for votacion in categoria.votaciones.all():
            nueva_votacion = Votacion.objects.create(
                categoria=nueva_categoria, titulo=votacion.titulo, descripcion=votacion.descripcion,
                reglas=votacion.reglas, fecha_apertura=un_anio_despues(votacion.fecha_apertura),
                fecha_cierre=un_anio_despues(votacion.fecha_cierre),
                estado=Votacion.Estado.BORRADOR, activa=votacion.activa,
            )
            Opcion.objects.bulk_create(
                Opcion(votacion=nueva_votacion, nombre=o.nombre, descripcion=o.descripcion,
                       imagen=o.imagen, orden=o.orden, activa=o.activa)
                for o in votacion.opciones.all()
            )
    return nueva


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
    actions = ["duplicar_para_anio_siguiente"]

    @admin.display(description="categorías")
    def total_categorias(self, obj):
        return obj.categorias.count()

    @admin.action(description="Duplicar como edición del año siguiente (en borrador)")
    def duplicar_para_anio_siguiente(self, request, queryset):
        """Entrega 4: crea la edición siguiente (por ejemplo 2028 a partir de
        2027) copiando categorías, votaciones y opciones, sin votos. Todo queda
        en borrador para que el administrador ajuste fechas y opciones antes de
        publicar. No requiere modificar el código."""
        for edicion in queryset:
            if Edicion.objects.filter(anio=edicion.anio + 1).exists():
                self.message_user(request, f"Ya existe la edición {edicion.anio + 1}: no se duplicó {edicion.anio}.", messages.WARNING)
                continue
            nueva = duplicar_edicion(edicion)
            self.message_user(
                request,
                f"Se creó «{nueva}» en borrador con {nueva.categorias.count()} categorías, "
                f"{Votacion.objects.filter(categoria__edicion=nueva).count()} votaciones y "
                f"{Opcion.objects.filter(votacion__categoria__edicion=nueva).count()} opciones. Revise fechas y opciones antes de publicar.",
                messages.SUCCESS,
            )


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
    list_display = ("titulo", "categoria", "fecha_apertura", "fecha_cierre", "estado", "estado_publico", "total_opciones", "total_votos")
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

    @admin.display(description="votos")
    def total_votos(self, obj):
        return obj.votos.count()

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
    @admin.display(description="votos", ordering="num_votos")
    def total_votos(self, obj):
        return obj.num_votos

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_votos=Count("votos"))

    list_display = ("nombre", "votacion", "orden", "activa", "total_votos")
    list_filter = ("activa", "votacion__categoria__edicion", "votacion")
    search_fields = ("nombre", "descripcion")
    list_editable = ("orden", "activa")
    list_select_related = ("votacion",)


@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    """Consulta administrativa de votos (Entrega 3). Es de solo lectura: los
    votos se crean únicamente desde el flujo de votación, nunca a mano."""

    list_display = ("id", "fecha", "usuario", "anio", "categoria_nombre", "votacion", "opcion")
    list_display_links = ("id", "fecha")
    list_filter = ("edicion", "categoria", "votacion")
    search_fields = ("usuario__email", "usuario__first_name", "opcion__nombre", "categoria__nombre")
    list_select_related = ("usuario", "edicion", "categoria", "votacion", "opcion")
    readonly_fields = ("usuario", "edicion", "categoria", "votacion", "opcion", "fecha", "ip")
    list_per_page = 50

    @admin.display(description="edición", ordering="edicion__anio")
    def anio(self, obj):
        return obj.edicion.anio

    @admin.display(description="categoría", ordering="categoria__nombre")
    def categoria_nombre(self, obj):
        return obj.categoria.nombre

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Permite abrir el detalle, pero todos los campos son de solo lectura
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False
