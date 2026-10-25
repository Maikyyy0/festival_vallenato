"""
Interfaz pública (RF03, RF04, CU-03). Todas las vistas consultan MySQL a
través del ORM de Django y solo muestran información publicada y activa.
"""
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Categoria, Edicion, Opcion, Votacion


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
    }
    return render(request, "votaciones/inicio.html", contexto)


def ediciones(request):
    lista = ediciones_publicadas().annotate(
        num_categorias=Count("categorias", filter=Q(categorias__activa=True))
    )
    return render(request, "votaciones/ediciones.html", {"ediciones": lista})


def edicion_detalle(request, anio):
    edicion = get_object_or_404(ediciones_publicadas(), anio=anio)
    categorias = (
        edicion.categorias.filter(activa=True)
        .annotate(
            num_votaciones=Count(
                "votaciones",
                filter=Q(votaciones__activa=True) & ~Q(votaciones__estado=Votacion.Estado.BORRADOR),
            )
        )
    )
    return render(request, "votaciones/edicion_detalle.html", {"edicion": edicion, "categorias": categorias})


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
    return render(request, "votaciones/categoria_detalle.html", {"categoria": categoria, "votaciones": votaciones})


def votacion_detalle(request, pk):
    votacion = get_object_or_404(
        votaciones_visibles().prefetch_related(
            Prefetch("opciones", queryset=Opcion.objects.filter(activa=True), to_attr="opciones_activas")
        ),
        pk=pk,
    )
    return render(request, "votaciones/votacion_detalle.html", {"votacion": votacion})
