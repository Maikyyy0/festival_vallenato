"""
Vistas de la aplicación votaciones.

- Interfaz pública (Entrega 2): inicio, ediciones, categorías y votaciones.
  Todas consultan MySQL con el ORM y solo muestran lo publicado y activo.
- Módulo de votación (Entrega 3): seleccionar opción → confirmar → registrar,
  y consulta de participación del usuario ("Mis votos").

Flujo: Iniciar sesión → Elegir categoría → Seleccionar una opción →
       Confirmar → Validar en Django → Registrar en MySQL

- Resultados (Entrega 4): conteo de votos por opción calculado en MySQL.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Categoria, Edicion, Opcion, Votacion, Voto
from .servicios import (
    VotoRechazado,
    registrar_voto,
    validar_voto,
    votacion_habilitada,
    voto_en_categoria,
)


def ediciones_publicadas():
    return Edicion.objects.filter(estado=Edicion.Estado.PUBLICADA)


def votaciones_visibles():
    """Votaciones activas de categorías activas en ediciones publicadas.
    Las que están en borrador no se muestran al público."""
    return (
        Votacion.objects.filter(
            activa=True,
            categoria__activa=True,
            categoria__edicion__estado=Edicion.Estado.PUBLICADA,
        )
        .exclude(estado=Votacion.Estado.BORRADOR)
        .select_related("categoria", "categoria__edicion")
    )


def categorias_votadas_ids(usuario):
    if not usuario.is_authenticated:
        return set()
    return set(Voto.objects.filter(usuario=usuario).values_list("categoria_id", flat=True))


# ---------------------------------------------------------------------------
# Interfaz pública
# ---------------------------------------------------------------------------
def inicio(request):
    ahora = timezone.now()
    visibles = votaciones_visibles()
    abiertas = visibles.filter(
        estado=Votacion.Estado.ABIERTA, fecha_apertura__lte=ahora, fecha_cierre__gte=ahora
    )
    proximas = visibles.filter(fecha_apertura__gt=ahora).exclude(estado=Votacion.Estado.CERRADA)
    contexto = {
        "edicion": ediciones_publicadas().first(),
        "abiertas": abiertas,
        "proximas": proximas[:5],
        "votadas": categorias_votadas_ids(request.user),
    }
    return render(request, "votaciones/inicio.html", contexto)


def ediciones(request):
    lista = ediciones_publicadas().annotate(
        num_categorias=Count("categorias", filter=Q(categorias__activa=True))
    )
    return render(request, "votaciones/ediciones.html", {"ediciones": lista})


def edicion_detalle(request, anio):
    edicion = get_object_or_404(ediciones_publicadas(), anio=anio)
    categorias = edicion.categorias.filter(activa=True).annotate(
        num_votaciones=Count(
            "votaciones",
            filter=Q(votaciones__activa=True) & ~Q(votaciones__estado=Votacion.Estado.BORRADOR),
        )
    )
    contexto = {"edicion": edicion, "categorias": categorias, "votadas": categorias_votadas_ids(request.user)}
    return render(request, "votaciones/edicion_detalle.html", contexto)


def categoria_detalle(request, pk):
    categoria = get_object_or_404(
        Categoria.objects.select_related("edicion"),
        pk=pk,
        activa=True,
        edicion__estado=Edicion.Estado.PUBLICADA,
    )
    votaciones = votaciones_visibles().filter(categoria=categoria).annotate(
        num_opciones=Count("opciones", filter=Q(opciones__activa=True))
    )
    contexto = {
        "categoria": categoria,
        "votaciones": votaciones,
        "voto_previo": voto_en_categoria(request.user, categoria),
    }
    return render(request, "votaciones/categoria_detalle.html", contexto)


def obtener_votacion_visible(pk):
    return get_object_or_404(
        votaciones_visibles().prefetch_related(
            Prefetch("opciones", queryset=Opcion.objects.filter(activa=True), to_attr="opciones_activas")
        ),
        pk=pk,
    )


def votacion_detalle(request, pk):
    votacion = obtener_votacion_visible(pk)
    voto_previo = voto_en_categoria(request.user, votacion.categoria)
    contexto = {
        "votacion": votacion,
        "voto_previo": voto_previo,
        "habilitada": votacion_habilitada(votacion),
        "puede_votar": request.user.is_authenticated and votacion_habilitada(votacion) and not voto_previo,
    }
    return render(request, "votaciones/votacion_detalle.html", contexto)


# ---------------------------------------------------------------------------
# Módulo de votación (Entrega 3)
# ---------------------------------------------------------------------------
@login_required
@require_http_methods(["GET", "POST"])
def seleccionar_opcion(request, pk):
    """Paso 1 (POST): recibe la opción elegida, la valida y muestra la confirmación.
    Todavía no guarda nada en la base de datos."""
    votacion = obtener_votacion_visible(pk)
    if request.method == "GET":
        return redirect(votacion)
    try:
        opcion = validar_voto(request.user, votacion, request.POST.get("opcion"))
    except VotoRechazado as error:
        messages.error(request, error.mensaje)
        return redirect(votacion)
    return render(request, "votaciones/confirmar_voto.html", {"votacion": votacion, "opcion": opcion})


@login_required
@require_http_methods(["POST"])
def confirmar_voto(request, pk):
    """Paso 2 (POST con CSRF): vuelve a validar en el servidor y registra el voto en MySQL."""
    votacion = obtener_votacion_visible(pk)
    try:
        voto = registrar_voto(request.user, votacion.pk, request.POST.get("opcion"), ip=request.META.get("REMOTE_ADDR"))
    except VotoRechazado as error:
        messages.error(request, error.mensaje)
        return redirect(votacion)
    messages.success(
        request,
        f"¡Voto registrado! Eligió «{voto.opcion.nombre}» en la categoría «{voto.categoria.nombre}». "
        f"Comprobante n.º {voto.pk}.",
    )
    return redirect("votaciones:mis_votos")


@login_required
def mis_votos(request):
    """Participación del usuario: categorías votadas y categorías pendientes."""
    votos = (
        Voto.objects.filter(usuario=request.user)
        .select_related("edicion", "categoria", "votacion", "opcion")
        .order_by("edicion__anio", "categoria__orden", "fecha")
    )
    votadas = {v.categoria_id for v in votos}
    ahora = timezone.now()
    abiertas = votaciones_visibles().filter(
        estado=Votacion.Estado.ABIERTA, fecha_apertura__lte=ahora, fecha_cierre__gte=ahora
    )
    pendientes = {}
    for v in abiertas.exclude(categoria_id__in=votadas).order_by("categoria__orden", "fecha_apertura"):
        pendientes.setdefault(v.categoria, []).append(v)
    contexto = {"votos": votos, "pendientes": pendientes}
    return render(request, "votaciones/mis_votos.html", contexto)


# ---------------------------------------------------------------------------
# Resultados (Entrega 4)
# ---------------------------------------------------------------------------
def puede_ver_resultados(usuario, votacion):
    """El administrador (is_staff) ve los resultados en cualquier momento.
    El público y los votantes solo los ven cuando la votación ya cerró,
    para que el conteo parcial no influya en quienes aún no han votado."""
    return usuario.is_staff or votacion.estado_publico == "Cerrada"


def resultados(request):
    """Conteo de votos por opción, agrupado por categoría.

    Los datos salen de la tabla de votos en MySQL: el ORM genera un
    SELECT ... COUNT(voto.id) ... GROUP BY opcion.id (annotate + Count)."""
    lista_ediciones = ediciones_publicadas()
    anio = request.GET.get("edicion")
    if anio and anio.isdigit():
        edicion = get_object_or_404(lista_ediciones, anio=int(anio))
    else:
        edicion = lista_ediciones.first()

    bloques, ocultas = [], 0
    if edicion:
        opciones_con_votos = Opcion.objects.annotate(num_votos=Count("votos")).order_by("-num_votos", "orden", "nombre")
        votaciones = (
            votaciones_visibles()
            .filter(categoria__edicion=edicion)
            .order_by("categoria__orden", "categoria__nombre", "fecha_apertura")
            .prefetch_related(Prefetch("opciones", queryset=opciones_con_votos, to_attr="conteo"))
        )
        por_categoria = {}
        for votacion in votaciones:
            if not puede_ver_resultados(request.user, votacion):
                ocultas += 1
                continue
            total = sum(o.num_votos for o in votacion.conteo)
            maximo = max((o.num_votos for o in votacion.conteo), default=0)
            for o in votacion.conteo:
                o.porcentaje = round(o.num_votos * 100 / total, 1) if total else 0.0
                o.ganadora = total > 0 and o.num_votos == maximo
            votacion.total_votos = total
            votacion.empate = sum(1 for o in votacion.conteo if o.ganadora) > 1
            por_categoria.setdefault(votacion.categoria, []).append(votacion)
        for categoria, lista in por_categoria.items():
            bloques.append({"categoria": categoria, "votaciones": lista,
                            "total": sum(v.total_votos for v in lista)})

    contexto = {
        "ediciones": lista_ediciones,
        "edicion": edicion,
        "bloques": bloques,
        "ocultas": ocultas,
        "total_votos": Voto.objects.filter(edicion=edicion).count() if edicion else 0,
        "participantes": Voto.objects.filter(edicion=edicion).values("usuario").distinct().count() if edicion else 0,
    }
    return render(request, "votaciones/resultados.html", contexto)


# ---------------------------------------------------------------------------
# Panel de visualización dinámica (consume la API JSON con JavaScript)
# ---------------------------------------------------------------------------
def panel(request):
    """La página es estática: static/js/panel.js consulta /api/resumen/ y
    /api/votaciones/<id>/resultados/ y dibuja los gráficos."""
    return render(request, "votaciones/panel.html")
