"""
API de consulta (Entrega 3, ampliada para el panel de datos).

    GET /api/categorias/                        → categorías con sus votaciones y opciones
    GET /api/categorias/?edicion=2027           → solo las de una edición
    GET /api/resumen/                           → cifras generales y participación por votación
    GET /api/ediciones/                         → ediciones publicadas
    GET /api/ediciones/<año>/categorias/        → categorías activas de una edición
    GET /api/categorias/<id>/votaciones/        → votaciones visibles de una categoría
    GET /api/votaciones/<id>/                   → detalle y opciones activas
    GET /api/votaciones/<id>/resultados/        → votos por opción (ver regla abajo)
    GET /api/mis-votos/                         → votos del usuario con sesión (401 si no)

Devuelve JSON con datos consultados en MySQL con el ORM de Django. Es solo de
lectura: cualquier otro método HTTP responde 405 (por eso se marca csrf_exempt:
un POST debe recibir 405 y no 403).

Regla de resultados (la misma de la página /resultados/): se publican cuando la
votación está cerrada; mientras está abierta o próxima solo los ve el personal
(is_staff), para que el conteo parcial no influya en quienes aún no han votado.
Ningún endpoint expone datos de otros usuarios.
"""
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import Categoria, Edicion, Opcion, Votacion, Voto
from .servicios import votacion_habilitada, voto_en_categoria
from .views import ediciones_publicadas, puede_ver_resultados, votaciones_visibles


@csrf_exempt  # solo lectura: así un POST recibe 405 (método no permitido) y no 403
@require_GET
def api_categorias(request):
    opciones = Opcion.objects.filter(activa=True).order_by("orden", "nombre")
    votaciones = (
        Votacion.objects.filter(activa=True)
        .exclude(estado=Votacion.Estado.BORRADOR)
        .order_by("fecha_apertura", "titulo")
        .prefetch_related(Prefetch("opciones", queryset=opciones, to_attr="opciones_activas"))
    )
    categorias = (
        Categoria.objects.filter(activa=True, edicion__estado=Edicion.Estado.PUBLICADA)
        .select_related("edicion")
        .prefetch_related(Prefetch("votaciones", queryset=votaciones, to_attr="votaciones_visibles"))
        .order_by("-edicion__anio", "orden", "nombre")
    )

    anio = request.GET.get("edicion")
    if anio:
        if not anio.isdigit():
            return JsonResponse(
                {"error": "El parámetro 'edicion' debe ser un año, por ejemplo 2027."},
                status=400, json_dumps_params={"ensure_ascii": False},
            )
        categorias = categorias.filter(edicion__anio=int(anio))

    datos = []
    for c in categorias:
        lista_votaciones = []
        for v in c.votaciones_visibles:
            lista_votaciones.append({
                "id": v.pk,
                "titulo": v.titulo,
                "estado": v.estado_publico,
                "fecha_apertura": timezone.localtime(v.fecha_apertura).isoformat(),
                "fecha_cierre": timezone.localtime(v.fecha_cierre).isoformat(),
                "opciones": [
                    {"id": o.pk, "nombre": o.nombre, "descripcion": o.descripcion}
                    for o in v.opciones_activas
                ],
            })
        datos.append({
            "id": c.pk,
            "nombre": c.nombre,
            "descripcion": c.descripcion,
            "edicion": {"id": c.edicion.pk, "anio": c.edicion.anio, "nombre": c.edicion.nombre},
            "total_opciones": sum(len(v["opciones"]) for v in lista_votaciones),
            "votaciones": lista_votaciones,
        })

    return JsonResponse(
        {
            "generado": timezone.localtime().isoformat(timespec="seconds"),
            "total_categorias": len(datos),
            "categorias": datos,
        },
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )


# ---------------------------------------------------------------------------
# Endpoints adicionales para el panel de datos y otros clientes
# ---------------------------------------------------------------------------
def _json(datos, estado=200):
    return JsonResponse(datos, status=estado, json_dumps_params={"ensure_ascii": False})


def _error(mensaje, estado):
    return _json({"error": mensaje}, estado)


def _edicion_dict(e, num_categorias=None):
    datos = {
        "id": e.pk,
        "anio": e.anio,
        "nombre": e.nombre,
        "numero": e.numero,
        "homenaje": e.homenaje,
        "fecha_inicio": e.fecha_inicio.isoformat(),
        "fecha_fin": e.fecha_fin.isoformat(),
    }
    if num_categorias is not None:
        datos["num_categorias"] = num_categorias
    return datos


def _votacion_dict(v):
    return {
        "id": v.pk,
        "titulo": v.titulo,
        "descripcion": v.descripcion,
        "categoria_id": v.categoria_id,
        "categoria": v.categoria.nombre,
        "edicion": v.categoria.edicion.anio,
        "fecha_apertura": timezone.localtime(v.fecha_apertura).isoformat(),
        "fecha_cierre": timezone.localtime(v.fecha_cierre).isoformat(),
        "estado": v.estado_publico,
        "abierta": v.esta_abierta,
    }


@csrf_exempt
@require_GET
def ediciones(request):
    lista = ediciones_publicadas().annotate(
        num_categorias=Count("categorias", filter=Q(categorias__activa=True))
    )
    return _json({"ediciones": [_edicion_dict(e, e.num_categorias) for e in lista]})


@csrf_exempt
@require_GET
def edicion_categorias(request, anio):
    edicion = ediciones_publicadas().filter(anio=anio).first()
    if edicion is None:
        return _error("La edición no existe o no está publicada.", 404)
    categorias = edicion.categorias.filter(activa=True).annotate(
        num_votaciones=Count(
            "votaciones",
            filter=Q(votaciones__activa=True) & ~Q(votaciones__estado=Votacion.Estado.BORRADOR),
        )
    )
    return _json({
        "edicion": _edicion_dict(edicion),
        "categorias": [
            {"id": c.pk, "nombre": c.nombre, "descripcion": c.descripcion, "orden": c.orden,
             "num_votaciones": c.num_votaciones}
            for c in categorias
        ],
    })


@csrf_exempt
@require_GET
def categoria_votaciones(request, pk):
    categoria = Categoria.objects.filter(
        pk=pk, activa=True, edicion__estado=Edicion.Estado.PUBLICADA
    ).select_related("edicion").first()
    if categoria is None:
        return _error("La categoría no existe o no está disponible.", 404)
    votaciones = votaciones_visibles().filter(categoria=categoria)
    return _json({
        "categoria": {"id": categoria.pk, "nombre": categoria.nombre, "edicion": categoria.edicion.anio},
        "votaciones": [_votacion_dict(v) for v in votaciones],
    })


@csrf_exempt
@require_GET
def votacion_detalle(request, pk):
    votacion = votaciones_visibles().filter(pk=pk).first()
    if votacion is None:
        return _error("La votación no existe o no está publicada.", 404)
    datos = _votacion_dict(votacion)
    datos["reglas"] = votacion.reglas
    datos["habilitada"] = votacion_habilitada(votacion)
    datos["opciones"] = [
        {"id": o.pk, "nombre": o.nombre, "descripcion": o.descripcion, "orden": o.orden}
        for o in votacion.opciones.filter(activa=True)
    ]
    if request.user.is_authenticated:
        # La regla de unicidad es por categoría: votar en cualquier subevento cuenta.
        datos["ya_voto_en_categoria"] = voto_en_categoria(request.user, votacion.categoria) is not None
    return _json(datos)


@csrf_exempt
@require_GET
def votacion_resultados(request, pk):
    votacion = votaciones_visibles().filter(pk=pk).first()
    if votacion is None:
        return _error("La votación no existe o no está publicada.", 404)
    if not puede_ver_resultados(request.user, votacion):
        return _error("Los resultados se publican cuando la votación esté cerrada.", 403)

    # Se cuentan los votos de la votación (no solo de la opción) y se incluyen
    # opciones desactivadas que ya recibieron votos, para que el total cuadre.
    opciones = list(
        Opcion.objects.filter(votacion=votacion)
        .filter(Q(activa=True) | Q(votos__isnull=False))
        .annotate(total=Count("votos", distinct=True))
        .order_by("-total", "orden", "nombre")
    )
    total_votos = sum(o.total for o in opciones)
    lider = opciones[0].total if opciones else 0
    return _json({
        "votacion": _votacion_dict(votacion),
        "total_votos": total_votos,
        "parcial": votacion.estado_publico != "Cerrada",  # solo ocurre para el personal
        "resultados": [
            {
                "opcion_id": o.pk,
                "nombre": o.nombre,
                "votos": o.total,
                "porcentaje": round(o.total * 100 / total_votos, 1) if total_votos else 0.0,
                "lider": bool(total_votos) and o.total == lider,
            }
            for o in opciones
        ],
    })


@csrf_exempt
@require_GET
def resumen(request):
    """Cifras generales y participación por votación, para el panel dinámico."""
    visibles = list(
        votaciones_visibles()
        .annotate(
            total_votos=Count("votos", distinct=True),
            total_opciones=Count("opciones", filter=Q(opciones__activa=True), distinct=True),
        )
        .order_by("fecha_apertura", "titulo")
    )
    por_estado = {"Abierta": 0, "Próxima": 0, "Cerrada": 0}
    lista = []
    for v in visibles:
        estado = v.estado_publico
        por_estado[estado] = por_estado.get(estado, 0) + 1
        datos = _votacion_dict(v)
        datos["total_votos"] = v.total_votos
        datos["total_opciones"] = v.total_opciones
        datos["resultados_disponibles"] = puede_ver_resultados(request.user, v)
        lista.append(datos)

    ids = [v.pk for v in visibles]
    return _json({
        "totales": {
            "ediciones": ediciones_publicadas().count(),
            "categorias": Categoria.objects.filter(
                activa=True, edicion__estado=Edicion.Estado.PUBLICADA
            ).count(),
            "votaciones": len(lista),
            "opciones": Opcion.objects.filter(votacion_id__in=ids, activa=True).count(),
            "votos": sum(v.total_votos for v in visibles),
            "participantes": Voto.objects.filter(votacion_id__in=ids).values("usuario").distinct().count(),
        },
        "votaciones_por_estado": por_estado,
        "votaciones": lista,
    })


@csrf_exempt
@require_GET
def mis_votos(request):
    if not request.user.is_authenticated:
        return _error("Debe iniciar sesión para consultar sus votos.", 401)
    votos = Voto.objects.filter(usuario=request.user).select_related("votacion", "opcion", "categoria", "edicion")
    return _json({
        "votos": [
            {
                "edicion": v.edicion.anio,
                "categoria": v.categoria.nombre,
                "votacion_id": v.votacion_id,
                "votacion": v.votacion.titulo,
                "opcion": v.opcion.nombre,
                "fecha": timezone.localtime(v.fecha).isoformat(),
            }
            for v in votos
        ]
    })
