from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, Edicion, Opcion, Votacion


class BaseDatos(TestCase):
    @classmethod
    def setUpTestData(cls):
        ahora = timezone.now()
        cls.edicion = Edicion.objects.create(
            nombre="Festival 2027", anio=2027, numero=60, fecha_inicio=date(2027, 4, 28),
            fecha_fin=date(2027, 5, 1), estado=Edicion.Estado.PUBLICADA,
        )
        cls.borrador = Edicion.objects.create(
            nombre="Festival 2026", anio=2026, fecha_inicio=date(2026, 4, 29),
            fecha_fin=date(2026, 5, 2), estado=Edicion.Estado.BORRADOR,
        )
        cls.categoria = Categoria.objects.create(edicion=cls.edicion, nombre="Canción inédita")
        cls.cat_inactiva = Categoria.objects.create(edicion=cls.edicion, nombre="Oculta", activa=False)
        cls.abierta = Votacion.objects.create(
            categoria=cls.categoria, titulo="Votación abierta", estado=Votacion.Estado.ABIERTA,
            fecha_apertura=ahora - timedelta(days=1), fecha_cierre=ahora + timedelta(days=5),
        )
        cls.proxima = Votacion.objects.create(
            categoria=cls.categoria, titulo="Votación próxima", estado=Votacion.Estado.ABIERTA,
            fecha_apertura=ahora + timedelta(days=10), fecha_cierre=ahora + timedelta(days=12),
        )
        cls.oculta = Votacion.objects.create(
            categoria=cls.categoria, titulo="Votación borrador", estado=Votacion.Estado.BORRADOR,
            fecha_apertura=ahora, fecha_cierre=ahora + timedelta(days=1),
        )
        Opcion.objects.create(votacion=cls.abierta, nombre="Opción A")
        Opcion.objects.create(votacion=cls.abierta, nombre="Opción inactiva", activa=False)


class ModelosTests(BaseDatos):
    def test_jerarquia_edicion_categoria_votacion_opcion(self):
        # RN-01: cada nivel pertenece al anterior.
        opcion = Opcion.objects.get(nombre="Opción A")
        self.assertEqual(opcion.votacion.categoria.edicion, self.edicion)
        self.assertEqual(self.edicion.categorias.count(), 2)
        self.assertEqual(self.categoria.votaciones.count(), 3)

    def test_estado_publico(self):
        self.assertTrue(self.abierta.esta_abierta)
        self.assertEqual(self.abierta.estado_publico, "Abierta")
        self.assertEqual(self.proxima.estado_publico, "Próxima")
        self.assertFalse(self.proxima.esta_abierta)
        self.assertEqual(self.oculta.estado_publico, "No publicada")

    def test_fecha_cierre_anterior_es_invalida(self):
        # CU-06, flujo 4a.
        v = Votacion(categoria=self.categoria, titulo="Mal", fecha_apertura=timezone.now(),
                     fecha_cierre=timezone.now() - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_fecha_fin_edicion_invalida(self):
        e = Edicion(nombre="X", anio=2030, fecha_inicio=date(2030, 5, 2), fecha_fin=date(2030, 5, 1))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_anio_de_edicion_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Edicion.objects.create(nombre="Duplicada", anio=2027, fecha_inicio=date(2027, 1, 1), fecha_fin=date(2027, 1, 2))

    def test_categoria_unica_por_edicion(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(edicion=self.edicion, nombre="Canción inédita")

    def test_no_se_borra_votacion_con_opciones(self):
        # RN-07: lo que tiene datos asociados se desactiva, no se elimina.
        with self.assertRaises(ProtectedError):
            self.abierta.delete()


class InterfazPublicaTests(BaseDatos):
    def test_inicio_muestra_datos_de_mysql(self):
        r = self.client.get(reverse("votaciones:inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Festival 2027")
        self.assertContains(r, "Votación abierta")
        self.assertContains(r, "Votación próxima")
        self.assertNotContains(r, "Votación borrador")

    def test_lista_ediciones_solo_publicadas(self):
        r = self.client.get(reverse("votaciones:ediciones"))
        self.assertContains(r, "Festival 2027")
        self.assertNotContains(r, "Festival 2026")

    def test_edicion_en_borrador_da_404(self):
        r = self.client.get(reverse("votaciones:edicion_detalle", args=[2026]))
        self.assertEqual(r.status_code, 404)

    def test_detalle_edicion_lista_categorias_activas(self):
        r = self.client.get(reverse("votaciones:edicion_detalle", args=[2027]))
        self.assertContains(r, "Canción inédita")
        self.assertNotContains(r, "Oculta")

    def test_categoria_inactiva_da_404(self):
        r = self.client.get(reverse("votaciones:categoria_detalle", args=[self.cat_inactiva.pk]))
        self.assertEqual(r.status_code, 404)

    def test_detalle_votacion_muestra_opciones_activas(self):
        r = self.client.get(reverse("votaciones:votacion_detalle", args=[self.abierta.pk]))
        self.assertContains(r, "Opción A")
        self.assertNotContains(r, "Opción inactiva")
        self.assertContains(r, "Iniciar sesión")  # visitante sin sesión

    def test_votacion_borrador_da_404(self):
        r = self.client.get(reverse("votaciones:votacion_detalle", args=[self.oculta.pk]))
        self.assertEqual(r.status_code, 404)


class AdminTests(BaseDatos):
    def test_admin_exige_staff(self):
        r = self.client.get(reverse("admin:votaciones_votacion_changelist"))
        self.assertEqual(r.status_code, 302)
        votante = get_user_model().objects.create_user("v@ejemplo.com", "v@ejemplo.com", "ClaveSegura#2027")
        self.client.force_login(votante)
        r = self.client.get(reverse("admin:votaciones_votacion_changelist"))
        self.assertEqual(r.status_code, 302)

    def test_admin_lista_y_crea(self):
        admin = get_user_model().objects.create_superuser("admin", "admin@ejemplo.com", "ClaveSegura#2027")
        self.client.force_login(admin)
        for nombre in ("edicion", "categoria", "votacion", "opcion"):
            r = self.client.get(reverse(f"admin:votaciones_{nombre}_changelist"))
            self.assertEqual(r.status_code, 200, nombre)
        r = self.client.post(reverse("admin:votaciones_categoria_add"), {
            "edicion": self.edicion.pk, "nombre": "Nueva desde admin", "descripcion": "", "orden": 5, "activa": "on",
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nombre="Nueva desde admin").exists())
