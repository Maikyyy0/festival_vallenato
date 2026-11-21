"""
Lógica de negocio del registro de votos (Entrega 3).

Aquí se controla la regla central del sistema:

    Un usuario puede elegir UNA sola opción por categoría y edición.
    Puede votar en otras categorías, pero no emitir un segundo voto en la
    misma categoría, aunque esta tenga varias votaciones (subeventos).

Defensa en tres capas:
    1. validar_voto(): reglas en Django (autenticación, votación habilitada,
       opción válida y voto previo en la categoría).
    2. registrar_voto(): transacción con SELECT ... FOR UPDATE sobre la fila
       del usuario, para que dos solicitudes simultáneas del mismo usuario se
       atiendan una después de la otra.
    3. Restricción única en MySQL (models.Voto.Meta.constraints): si aun así
       llegara un duplicado, la base de datos lo rechaza (IntegrityError) y se
       convierte en un mensaje controlado.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import Edicion, Opcion, Votacion, Voto


class VotoRechazado(Exception):
    """Error de negocio con un código para pruebas y un mensaje para el usuario."""

    NO_AUTENTICADO = "no_autenticado"
    NO_HABILITADA = "no_habilitada"
    OPCION_INVALIDA = "opcion_invalida"
    DUPLICADO = "duplicado"

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def votacion_habilitada(votacion):
    """La votación admite votos si está abierta por estado y fechas (RN-03),
    su categoría está activa y su edición está publicada."""
    return (
        votacion.esta_abierta
        and votacion.categoria.activa
        and votacion.categoria.edicion.estado == Edicion.Estado.PUBLICADA
    )


def voto_en_categoria(usuario, categoria):
    """Devuelve el voto del usuario en la categoría (cualquier subevento) o None."""
    if not usuario.is_authenticated:
        return None
    return (
        Voto.objects.select_related("opcion", "votacion")
        .filter(usuario=usuario, edicion_id=categoria.edicion_id, categoria=categoria)
        .first()
    )


def validar_voto(usuario, votacion, opcion_id):
    """Aplica todas las validaciones del servidor y devuelve la Opcion válida.
    No guarda nada: se usa también para mostrar la pantalla de confirmación."""
    if usuario is None or not usuario.is_authenticated:
        raise VotoRechazado(VotoRechazado.NO_AUTENTICADO, "Debe iniciar sesión para votar.")

    if not votacion_habilitada(votacion):
        raise VotoRechazado(
            VotoRechazado.NO_HABILITADA,
            "Esta votación no está habilitada: no ha abierto, ya cerró o no está publicada.",
        )

    try:
        opcion = Opcion.objects.select_related("votacion__categoria__edicion").get(pk=opcion_id, activa=True)
    except (Opcion.DoesNotExist, ValueError, TypeError):
        raise VotoRechazado(VotoRechazado.OPCION_INVALIDA, "La opción seleccionada no existe o no está activa.")

    # La opción debe pertenecer a ESTA votación, y por lo tanto a su categoría y edición
    if (
        opcion.votacion_id != votacion.pk
        or opcion.votacion.categoria_id != votacion.categoria_id
        or opcion.votacion.categoria.edicion_id != votacion.categoria.edicion_id
    ):
        raise VotoRechazado(
            VotoRechazado.OPCION_INVALIDA,
            "La opción enviada no pertenece a esta votación ni a su categoría.",
        )

    previo = voto_en_categoria(usuario, votacion.categoria)
    if previo:
        raise VotoRechazado(
            VotoRechazado.DUPLICADO,
            f"Ya votó en la categoría «{votacion.categoria.nombre}» por «{previo.opcion.nombre}». "
            "Solo se permite un voto por categoría.",
        )
    return opcion


def registrar_voto(usuario, votacion_id, opcion_id, ip=None):
    """Valida y guarda el voto en MySQL de forma atómica. Devuelve el Voto."""
    if usuario is None or not usuario.is_authenticated:
        raise VotoRechazado(VotoRechazado.NO_AUTENTICADO, "Debe iniciar sesión para votar.")

    with transaction.atomic():
        # Bloquea la fila del usuario hasta el final de la transacción: si el
        # mismo usuario envía dos votos al mismo tiempo, el segundo espera aquí
        # y luego encuentra el primer voto ya guardado.
        get_user_model().objects.select_for_update().get(pk=usuario.pk)

        votacion = Votacion.objects.select_related("categoria__edicion").get(pk=votacion_id)
        opcion = validar_voto(usuario, votacion, opcion_id)
        try:
            with transaction.atomic():
                return Voto.objects.create(
                    usuario=usuario,
                    edicion=votacion.categoria.edicion,
                    categoria=votacion.categoria,
                    votacion=votacion,
                    opcion=opcion,
                    ip=ip,
                )
        except IntegrityError:
            # Última barrera: la restricción única de MySQL detectó un duplicado
            raise VotoRechazado(
                VotoRechazado.DUPLICADO,
                "Ya existe un voto suyo en esta categoría. Solo se permite un voto por categoría.",
            )
