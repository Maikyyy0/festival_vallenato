"""
Carga datos de prueba en MySQL para demostrar la aplicación.

    python manage.py cargar_datos_prueba            # crea o actualiza
    python manage.py cargar_datos_prueba --reiniciar  # borra y vuelve a crear

Todas las canciones, agrupaciones y personas son FICTICIAS. Las categorías
son ejemplos y no representan categorías aprobadas por el cliente.
No crea usuarios ni contraseñas: el administrador se crea con createsuperuser.
"""
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from votaciones.models import Categoria, Edicion, Opcion, Votacion

E = Edicion.Estado
V = Votacion.Estado


class Command(BaseCommand):
    help = "Carga ediciones, categorías, votaciones y opciones de prueba."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Elimina los datos existentes antes de cargar.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if opciones["reiniciar"]:
            Opcion.objects.all().delete()
            Votacion.objects.all().delete()
            Categoria.objects.all().delete()
            Edicion.objects.all().delete()
            self.stdout.write("Datos anteriores eliminados.")

        ahora = timezone.now().replace(minute=0, second=0, microsecond=0)

        # ---------------- Ediciones ----------------
        e2027 = self.edicion(
            2027, "Festival de la Leyenda Vallenata 2027", 60,
            "Homenaje por confirmar con la Fundación (dato de prueba)",
            date(2027, 4, 28), date(2027, 5, 1), E.PUBLICADA,
            "Edición de referencia del proyecto. Número de edición y fechas pendientes de validación con el cliente.",
        )
        e2026 = self.edicion(
            2026, "Festival de la Leyenda Vallenata 2026", 59, "",
            date(2026, 4, 29), date(2026, 5, 2), E.BORRADOR,
            "Edición en borrador: no debe aparecer en la interfaz pública.",
        )
        e2025 = self.edicion(
            2025, "Festival de la Leyenda Vallenata 2025", 58, "Homenaje al Rey Vallenato Omar Geles",
            date(2025, 4, 30), date(2025, 5, 3), E.PUBLICADA,
            "Edición anterior, usada para mostrar votaciones cerradas.",
        )

        # ---------------- Categorías 2027 ----------------
        c_cancion = self.categoria(e2027, "Canción inédita favorita del público", 1,
            "El público elige su canción inédita preferida entre las preseleccionadas.")
        c_piloneras = self.categoria(e2027, "Piloneras: grupo favorito del público", 2,
            "Votación del público para los grupos de piloneras de la categoría mayores.")
        c_vestuario = self.categoria(e2027, "Mejor vestuario del desfile", 3,
            "Reconocimiento del público al vestuario de comparsas y piloneras.")
        c_revelacion = self.categoria(e2027, "Acordeonero aficionado revelación", 4,
            "El público destaca al acordeonero aficionado con mejor presentación.")
        self.categoria(e2027, "Categoría inactiva de prueba", 9,
            "Categoría desactivada: no debe mostrarse al público.", activa=False)
        self.categoria(e2026, "Canción favorita 2026", 1, "Categoría de una edición en borrador.")
        c_2025 = self.categoria(e2025, "Canción favorita del público 2025", 1,
            "Votación ya finalizada de la edición anterior.")

        # ---------------- Votaciones ----------------
        v1 = self.votacion(c_cancion, "Canción inédita favorita · Preselección", V.ABIERTA,
            ahora - timedelta(days=2), ahora + timedelta(days=30),
            "Elija la canción inédita que más le guste entre las preseleccionadas por el jurado.",
            "Un voto por persona registrada (RN-02, pendiente de validación).")
        self.opciones(v1, [
            ("Brisas del Guatapurí", "Paseo · autor ficticio: Compositor de prueba A"),
            ("Sabana adentro", "Merengue · autor ficticio: Compositor de prueba B"),
            ("Carta para mi pueblo", "Son · autor ficticio: Compositor de prueba C"),
            ("El acordeón del abuelo", "Puya · autor ficticio: Compositor de prueba D"),
        ])

        v2 = self.votacion(c_piloneras, "Grupo de piloneras favorito · Mayores", V.ABIERTA,
            ahora - timedelta(days=1), ahora + timedelta(days=20),
            "Vote por el grupo de piloneras mayores que más le haya gustado.")
        self.opciones(v2, [
            ("Piloneras Alma de Pilón (ejemplo)", "Grupo ficticio de 12 integrantes."),
            ("Piloneras Raíces del Cesar (ejemplo)", "Grupo ficticio de 15 integrantes."),
            ("Piloneras Flor de Mayo (ejemplo)", "Grupo ficticio de 10 integrantes."),
        ])

        v3 = self.votacion(c_vestuario, "Mejor vestuario del desfile de piloneras", V.ABIERTA,
            ahora + timedelta(days=60), ahora + timedelta(days=75),
            "Se abrirá después del desfile. Programada: aparece como Próxima.")
        self.opciones(v3, [
            ("Comparsa Colores del Valle (ejemplo)", "Vestuario inspirado en la flor de cayena."),
            ("Comparsa Tradición Viva (ejemplo)", "Vestuario de polleras en tonos tierra."),
        ])

        v4 = self.votacion(c_revelacion, "Acordeonero aficionado revelación", V.ABIERTA,
            ahora + timedelta(days=90), ahora + timedelta(days=100),
            "Votación programada para los días del Festival.")
        self.opciones(v4, [
            ("Concursante aficionado 1 (ficticio)", "Municipio de prueba: Valledupar."),
            ("Concursante aficionado 2 (ficticio)", "Municipio de prueba: La Paz."),
            ("Concursante aficionado 3 (ficticio)", "Municipio de prueba: San Juan del Cesar."),
        ])

        self.votacion(c_revelacion, "Votación en borrador (no visible)", V.BORRADOR,
            ahora + timedelta(days=120), ahora + timedelta(days=130),
            "Votación en construcción: no debe mostrarse al público.")

        v5 = self.votacion(c_2025, "Canción favorita del público 2025", V.CERRADA,
            timezone.make_aware(datetime(2025, 4, 30, 8, 0)),
            timezone.make_aware(datetime(2025, 5, 3, 18, 0)),
            "Votación finalizada (datos de prueba).")
        self.opciones(v5, [
            ("Canción de prueba 2025 · A", "Dato ficticio."),
            ("Canción de prueba 2025 · B", "Dato ficticio."),
        ])

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {Edicion.objects.count()} ediciones, {Categoria.objects.count()} categorías, "
            f"{Votacion.objects.count()} votaciones y {Opcion.objects.count()} opciones en MySQL."
        ))

    # ------------------------------------------------------------------
    def edicion(self, anio, nombre, numero, homenaje, inicio, fin, estado, descripcion):
        obj, _ = Edicion.objects.update_or_create(
            anio=anio,
            defaults=dict(nombre=nombre, numero=numero, homenaje=homenaje, fecha_inicio=inicio,
                          fecha_fin=fin, estado=estado, descripcion=descripcion),
        )
        return obj

    def categoria(self, edicion, nombre, orden, descripcion, activa=True):
        obj, _ = Categoria.objects.update_or_create(
            edicion=edicion, nombre=nombre,
            defaults=dict(orden=orden, descripcion=descripcion, activa=activa),
        )
        return obj

    def votacion(self, categoria, titulo, estado, apertura, cierre, descripcion, reglas=""):
        obj, _ = Votacion.objects.update_or_create(
            categoria=categoria, titulo=titulo,
            defaults=dict(estado=estado, fecha_apertura=apertura, fecha_cierre=cierre,
                          descripcion=descripcion, reglas=reglas, activa=True),
        )
        return obj

    def opciones(self, votacion, datos):
        for i, (nombre, descripcion) in enumerate(datos, start=1):
            Opcion.objects.update_or_create(
                votacion=votacion, nombre=nombre, defaults=dict(descripcion=descripcion, orden=i, activa=True)
            )
