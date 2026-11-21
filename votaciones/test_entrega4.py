"""Pruebas de la Entrega 4: resultados y duplicación de edición."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import duplicar_edicion
from .models import Categoria, Edicion, Opcion, Votacion, Voto


class ResultadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ahora = timezone.now()
        cls.ed = Edicion.objects.create(nombre="Festival 2027", anio=2027, numero=60, fecha_inicio=date(2027, 4, 28),
                                        fecha_fin=date(2027, 5, 1), estado=Edicion.Estado.PUBLICADA)
        cat = Categoria.objects.create(edicion=cls.ed, nombre="Canción")
        cat2 = Categoria.objects.create(edicion=cls.ed, nombre="Piloneras")
        cls.abierta = Votacion.objects.create(categoria=cat, titulo="Abierta", estado=Votacion.Estado.ABIERTA,
                                              fecha_apertura=ahora - timedelta(days=1), fecha_cierre=ahora + timedelta(days=5))
        cls.cerrada = Votacion.objects.create(categoria=cat2, titulo="Cerrada", estado=Votacion.Estado.CERRADA,
                                              fecha_apertura=ahora - timedelta(days=9), fecha_cierre=ahora - timedelta(days=2))
        a = Opcion.objects.create(votacion=cls.cerrada, nombre="Grupo A", orden=1)
        b = Opcion.objects.create(votacion=cls.cerrada, nombre="Grupo B", orden=2)
        x = Opcion.objects.create(votacion=cls.abierta, nombre="Canción X")
        for i, op in enumerate([a, a, b]):
            u = User.objects.create_user(f"u{i}", f"u{i}@ejemplo.com", "x")
            Voto.objects.create(usuario=u, edicion=cls.ed, categoria=cat2, votacion=cls.cerrada, opcion=op)
        Voto.objects.create(usuario=User.objects.get(username="u0"), edicion=cls.ed, categoria=cat,
                            votacion=cls.abierta, opcion=x)
        cls.admin = User.objects.create_user("admin", "admin@ejemplo.com", "x", is_staff=True)

    def conteo(self, resp, titulo):
        for b in resp.context["bloques"]:
            for v in b["votaciones"]:
                if v.titulo == titulo:
                    return {o.nombre: o.num_votos for o in v.conteo}
        return None

    def test_conteo_desde_mysql(self):
        resp = self.client.get(reverse("votaciones:resultados"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.conteo(resp, "Cerrada"), {"Grupo A": 2, "Grupo B": 1})
        self.assertEqual(resp.context["total_votos"], 4)
        self.assertEqual(resp.context["participantes"], 3)

    def test_publico_no_ve_votacion_abierta(self):
        resp = self.client.get(reverse("votaciones:resultados"))
        self.assertIsNone(self.conteo(resp, "Abierta"))
        self.assertEqual(resp.context["ocultas"], 1)

    def test_administrador_ve_resultados_parciales(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("votaciones:resultados"))
        self.assertEqual(self.conteo(resp, "Abierta"), {"Canción X": 1})

    def test_edicion_inexistente(self):
        self.assertEqual(self.client.get(reverse("votaciones:resultados"), {"edicion": 1990}).status_code, 404)


class DuplicarEdicionTests(TestCase):
    def test_duplica_estructura_sin_votos(self):
        ahora = timezone.now()
        ed = Edicion.objects.create(nombre="Festival de la Leyenda Vallenata 2027", anio=2027, numero=60,
                                    fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1), estado=Edicion.Estado.PUBLICADA)
        cat = Categoria.objects.create(edicion=ed, nombre="Canción")
        v = Votacion.objects.create(categoria=cat, titulo="Preselección", estado=Votacion.Estado.ABIERTA,
                                    fecha_apertura=ahora, fecha_cierre=ahora + timedelta(days=3))
        op = Opcion.objects.create(votacion=v, nombre="A")
        Opcion.objects.create(votacion=v, nombre="B")
        u = User.objects.create_user("u", "u@ejemplo.com", "x")
        Voto.objects.create(usuario=u, edicion=ed, categoria=cat, votacion=v, opcion=op)

        nueva = duplicar_edicion(ed)
        self.assertEqual((nueva.anio, nueva.numero, nueva.estado), (2028, 61, Edicion.Estado.BORRADOR))
        self.assertEqual(nueva.nombre, "Festival de la Leyenda Vallenata 2028")
        nv = Votacion.objects.get(categoria__edicion=nueva)
        self.assertEqual(nv.estado, Votacion.Estado.BORRADOR)
        self.assertEqual(nv.fecha_apertura.year, v.fecha_apertura.year + 1)
        self.assertEqual(nv.opciones.count(), 2)
        self.assertEqual(Voto.objects.filter(edicion=nueva).count(), 0)

    def test_accion_admin(self):
        admin = User.objects.create_superuser("admin", "admin@ejemplo.com", "x")
        ed = Edicion.objects.create(nombre="Festival 2027", anio=2027, fecha_inicio=date(2027, 4, 28),
                                    fecha_fin=date(2027, 5, 1))
        self.client.force_login(admin)
        resp = self.client.post(reverse("admin:votaciones_edicion_changelist"),
                                {"action": "duplicar_para_anio_siguiente", "_selected_action": [ed.pk]}, follow=True)
        self.assertContains(resp, "en borrador")
        self.assertTrue(Edicion.objects.filter(anio=2028).exists())
        # Una segunda vez no duplica porque 2028 ya existe
        self.client.post(reverse("admin:votaciones_edicion_changelist"),
                         {"action": "duplicar_para_anio_siguiente", "_selected_action": [ed.pk]})
        self.assertEqual(Edicion.objects.filter(anio=2028).count(), 1)
