"""Pruebas de la API JSON ampliada y del panel de visualización dinámica."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, Edicion, Opcion, Votacion, Voto

CLAVE = "Clave-segura-123"


def votar(usuario, votacion, opcion):
    return Voto.objects.create(
        usuario=usuario, edicion=votacion.categoria.edicion, categoria=votacion.categoria,
        votacion=votacion, opcion=opcion,
    )


class ApiPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ahora = timezone.now()
        cls.ed = Edicion.objects.create(
            nombre="Festival 2027", anio=2027, numero=60, fecha_inicio=date(2027, 4, 28),
            fecha_fin=date(2027, 5, 1), estado=Edicion.Estado.PUBLICADA)
        cls.ed_borrador = Edicion.objects.create(
            nombre="Festival 2026", anio=2026, fecha_inicio=date(2026, 4, 29),
            fecha_fin=date(2026, 5, 2), estado=Edicion.Estado.BORRADOR)
        cls.cat_a = Categoria.objects.create(edicion=cls.ed, nombre="Canción inédita")
        cls.cat_b = Categoria.objects.create(edicion=cls.ed, nombre="Piloneras")
        cls.cat_off = Categoria.objects.create(edicion=cls.ed, nombre="Oculta", activa=False)

        cls.abierta = Votacion.objects.create(
            categoria=cls.cat_a, titulo="Abierta", estado=Votacion.Estado.ABIERTA,
            fecha_apertura=ahora - timedelta(days=1), fecha_cierre=ahora + timedelta(days=5))
        cls.hermana = Votacion.objects.create(  # otro subevento de la MISMA categoría
            categoria=cls.cat_a, titulo="Hermana", estado=Votacion.Estado.ABIERTA,
            fecha_apertura=ahora - timedelta(days=1), fecha_cierre=ahora + timedelta(days=5))
        cls.proxima = Votacion.objects.create(
            categoria=cls.cat_a, titulo="Próxima", estado=Votacion.Estado.ABIERTA,
            fecha_apertura=ahora + timedelta(days=10), fecha_cierre=ahora + timedelta(days=12))
        cls.borrador = Votacion.objects.create(
            categoria=cls.cat_a, titulo="Borrador", estado=Votacion.Estado.BORRADOR,
            fecha_apertura=ahora, fecha_cierre=ahora + timedelta(days=1))
        cls.cerrada = Votacion.objects.create(
            categoria=cls.cat_b, titulo="Cerrada", estado=Votacion.Estado.CERRADA,
            fecha_apertura=ahora - timedelta(days=9), fecha_cierre=ahora - timedelta(days=2))

        cls.op_a = Opcion.objects.create(votacion=cls.abierta, nombre="Opción A")
        cls.op_b = Opcion.objects.create(votacion=cls.abierta, nombre="Opción B")
        Opcion.objects.create(votacion=cls.abierta, nombre="Inactiva", activa=False)
        cls.op_h = Opcion.objects.create(votacion=cls.hermana, nombre="Opción H")
        cls.c1 = Opcion.objects.create(votacion=cls.cerrada, nombre="C1", orden=1)
        cls.c2 = Opcion.objects.create(votacion=cls.cerrada, nombre="C2", orden=2)

        cls.u1 = User.objects.create_user("u1", "u1@x.co", CLAVE)
        cls.u2 = User.objects.create_user("u2", "u2@x.co", CLAVE)
        cls.staff = User.objects.create_user("adm", "adm@x.co", CLAVE, is_staff=True)
        votar(cls.u1, cls.cerrada, cls.c1)
        votar(cls.u2, cls.cerrada, cls.c1)
        votar(cls.staff, cls.cerrada, cls.c2)
        votar(cls.u1, cls.abierta, cls.op_a)

    # ---- catálogo ---------------------------------------------------------
    def test_ediciones_solo_publicadas(self):
        r = self.client.get(reverse("votaciones:api_ediciones"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual([e["anio"] for e in r.json()["ediciones"]], [2027])
        self.assertEqual(r.json()["ediciones"][0]["num_categorias"], 2)

    def test_categorias_de_edicion(self):
        r = self.client.get(reverse("votaciones:api_edicion_categorias", args=[2027]))
        por_nombre = {c["nombre"]: c for c in r.json()["categorias"]}
        self.assertEqual(set(por_nombre), {"Canción inédita", "Piloneras"})
        self.assertEqual(por_nombre["Canción inédita"]["num_votaciones"], 3)  # sin la de borrador

    def test_edicion_en_borrador_da_404_json(self):
        r = self.client.get(reverse("votaciones:api_edicion_categorias", args=[2026]))
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.json())

    def test_categoria_inactiva_da_404(self):
        self.assertEqual(self.client.get(reverse("votaciones:api_categoria_votaciones", args=[self.cat_off.pk])).status_code, 404)

    def test_votaciones_de_categoria_ocultan_borrador(self):
        r = self.client.get(reverse("votaciones:api_categoria_votaciones", args=[self.cat_a.pk]))
        self.assertEqual({v["titulo"] for v in r.json()["votaciones"]}, {"Abierta", "Hermana", "Próxima"})

    def test_detalle_votacion_solo_opciones_activas(self):
        r = self.client.get(reverse("votaciones:api_votacion_detalle", args=[self.abierta.pk]))
        self.assertEqual({o["nombre"] for o in r.json()["opciones"]}, {"Opción A", "Opción B"})
        self.assertTrue(r.json()["habilitada"])
        self.assertNotIn("ya_voto_en_categoria", r.json())  # anónimo

    def test_ya_voto_cuenta_toda_la_categoria(self):
        # u1 votó en "Abierta"; la regla es por categoría, así que en "Hermana" también figura como votado.
        self.client.force_login(self.u1)
        self.assertTrue(self.client.get(reverse("votaciones:api_votacion_detalle", args=[self.hermana.pk])).json()["ya_voto_en_categoria"])
        self.client.force_login(self.u2)
        self.assertFalse(self.client.get(reverse("votaciones:api_votacion_detalle", args=[self.hermana.pk])).json()["ya_voto_en_categoria"])

    def test_votacion_borrador_da_404(self):
        self.assertEqual(self.client.get(reverse("votaciones:api_votacion_detalle", args=[self.borrador.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("votaciones:api_votacion_resultados", args=[self.borrador.pk])).status_code, 404)

    # ---- resultados -------------------------------------------------------
    def test_resultados_de_votacion_cerrada_son_publicos(self):
        r = self.client.get(reverse("votaciones:api_votacion_resultados", args=[self.cerrada.pk]))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["total_votos"], 3)
        self.assertFalse(d["parcial"])
        self.assertEqual([x["nombre"] for x in d["resultados"]], ["C1", "C2"])
        self.assertEqual([x["votos"] for x in d["resultados"]], [2, 1])
        self.assertEqual(d["resultados"][0]["porcentaje"], 66.7)
        self.assertEqual([x["lider"] for x in d["resultados"]], [True, False])

    def test_resultados_de_votacion_abierta_solo_para_personal(self):
        url = reverse("votaciones:api_votacion_resultados", args=[self.abierta.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.u1)                       # votante normal tampoco
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["parcial"])
        self.assertEqual(r.json()["total_votos"], 1)

    def test_resultados_sin_votos_no_dividen_por_cero(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("votaciones:api_votacion_resultados", args=[self.hermana.pk]))
        self.assertEqual(r.json()["total_votos"], 0)
        self.assertTrue(all(x["porcentaje"] == 0.0 and not x["lider"] for x in r.json()["resultados"]))

    def test_resultados_api_coinciden_con_la_pagina_de_resultados(self):
        r = self.client.get(reverse("votaciones:resultados"))
        self.assertContains(r, "Cerrada")  # misma regla de visibilidad que la API
        self.assertNotContains(r, "Opción A")

    # ---- resumen ----------------------------------------------------------
    def test_resumen(self):
        d = self.client.get(reverse("votaciones:api_resumen")).json()
        t = d["totales"]
        self.assertEqual((t["ediciones"], t["categorias"], t["votaciones"], t["votos"]), (1, 2, 4, 4))
        self.assertEqual(t["participantes"], 3)  # u1, u2, staff (u1 votó dos veces en categorías distintas)
        self.assertEqual(d["votaciones_por_estado"], {"Abierta": 2, "Próxima": 1, "Cerrada": 1})
        por_id = {v["id"]: v for v in d["votaciones"]}
        self.assertEqual(por_id[self.cerrada.pk]["total_votos"], 3)
        self.assertTrue(por_id[self.cerrada.pk]["resultados_disponibles"])
        self.assertFalse(por_id[self.abierta.pk]["resultados_disponibles"])

    def test_resumen_para_personal_habilita_resultados(self):
        self.client.force_login(self.staff)
        d = self.client.get(reverse("votaciones:api_resumen")).json()
        self.assertTrue(all(v["resultados_disponibles"] for v in d["votaciones"]))

    # ---- sesión, métodos y datos sensibles ---------------------------------
    def test_mis_votos_requiere_sesion(self):
        self.assertEqual(self.client.get(reverse("votaciones:api_mis_votos")).status_code, 401)
        self.client.force_login(self.u1)
        d = self.client.get(reverse("votaciones:api_mis_votos")).json()
        self.assertEqual({v["categoria"] for v in d["votos"]}, {"Canción inédita", "Piloneras"})

    def test_la_api_es_de_solo_lectura_y_post_da_405_incluso_con_csrf_activo(self):
        cliente = Client(enforce_csrf_checks=True)
        for nombre, args in [("api_resumen", []), ("api_ediciones", []), ("api_categorias", []),
                             ("api_votacion_detalle", [self.abierta.pk]), ("api_mis_votos", [])]:
            self.assertEqual(cliente.post(reverse(f"votaciones:{nombre}", args=args)).status_code, 405, nombre)

    def test_la_api_no_expone_datos_de_usuarios(self):
        for nombre, args in [("api_resumen", []), ("api_categorias", []), ("api_votacion_detalle", [self.abierta.pk]),
                             ("api_votacion_resultados", [self.cerrada.pk])]:
            texto = self.client.get(reverse(f"votaciones:{nombre}", args=args)).content.decode()
            for dato in ("u1@x.co", "u2@x.co", "adm@x.co", '"ip"', '"usuario"'):
                self.assertNotIn(dato, texto, nombre)

    # ---- panel ------------------------------------------------------------
    def test_panel_se_renderiza_y_apunta_a_la_api(self):
        r = self.client.get(reverse("votaciones:panel"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse("votaciones:api_resumen"))
        self.assertContains(r, "js/panel.js")

    def test_enlace_al_panel_en_el_menu(self):
        self.assertContains(self.client.get(reverse("votaciones:inicio")), reverse("votaciones:panel"))
