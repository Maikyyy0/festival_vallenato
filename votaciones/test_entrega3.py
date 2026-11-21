"""
Pruebas funcionales obligatorias de la Entrega 3 (CP-01 a CP-10).

Se ejecutan contra MySQL con:  python manage.py test votaciones.test_entrega3 -v 2
"""
import json
import threading
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, Edicion, Opcion, Votacion, Voto
from .servicios import VotoRechazado, registrar_voto

User = get_user_model()
CLAVE = "Acordeon#2027Prueba"


def crear_escenario():
    """Edición publicada con:
    - Categoría A con DOS votaciones abiertas (subeventos A1 y A2)
    - Categoría B con una votación abierta
    - Categoría C con una votación que aún no abre (no habilitada)
    - Categoría D con una votación cerrada
    """
    ahora = timezone.now()
    e = Edicion.objects.create(
        nombre="Festival 2027", anio=2027, fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1),
        estado=Edicion.Estado.PUBLICADA,
    )
    abierta = dict(estado=Votacion.Estado.ABIERTA, fecha_apertura=ahora - timedelta(days=1),
                   fecha_cierre=ahora + timedelta(days=5))
    cat_a = Categoria.objects.create(edicion=e, nombre="Piloneras", orden=1)
    cat_b = Categoria.objects.create(edicion=e, nombre="Canción inédita", orden=2)
    cat_c = Categoria.objects.create(edicion=e, nombre="Vestuario", orden=3)
    cat_d = Categoria.objects.create(edicion=e, nombre="Revelación", orden=4)
    a1 = Votacion.objects.create(categoria=cat_a, titulo="Piloneras mayores", **abierta)
    a2 = Votacion.objects.create(categoria=cat_a, titulo="Piloneras infantiles", **abierta)
    b1 = Votacion.objects.create(categoria=cat_b, titulo="Canción favorita", **abierta)
    c1 = Votacion.objects.create(
        categoria=cat_c, titulo="Vestuario", estado=Votacion.Estado.ABIERTA,
        fecha_apertura=ahora + timedelta(days=10), fecha_cierre=ahora + timedelta(days=12),
    )
    d1 = Votacion.objects.create(
        categoria=cat_d, titulo="Revelación", estado=Votacion.Estado.CERRADA,
        fecha_apertura=ahora - timedelta(days=10), fecha_cierre=ahora - timedelta(days=5),
    )
    opciones = {}
    for v, nombres in ((a1, ["Grupo A", "Grupo B"]), (a2, ["Semillero 1", "Semillero 2"]),
                       (b1, ["Canción 1", "Canción 2"]), (c1, ["Comparsa 1"]), (d1, ["Acordeonero 1"])):
        for i, n in enumerate(nombres):
            opciones[n] = Opcion.objects.create(votacion=v, nombre=n, orden=i)
    Votacion.objects.create(  # borrador: no debe salir en la API
        categoria=cat_b, titulo="Votación en borrador", estado=Votacion.Estado.BORRADOR,
        fecha_apertura=ahora, fecha_cierre=ahora + timedelta(days=1),
    )
    return dict(edicion=e, cat_a=cat_a, cat_b=cat_b, a1=a1, a2=a2, b1=b1, c1=c1, d1=d1, op=opciones)


class FlujoVotacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = crear_escenario()
        cls.usuario = User.objects.create_user("ana@ejemplo.com", "ana@ejemplo.com", CLAVE, first_name="Ana")

    def setUp(self):
        self.client.login(username="ana@ejemplo.com", password=CLAVE)

    def votar(self, votacion, opcion):
        return self.client.post(reverse("votaciones:confirmar_voto", args=[votacion.pk]),
                                {"opcion": opcion.pk}, follow=True)

    def test_cp01_voto_valido(self):
        """CP-01 Usuario autenticado selecciona una opción válida: se registra el voto en MySQL."""
        a1, op = self.d["a1"], self.d["op"]["Grupo A"]
        # Paso 1: seleccionar → pantalla de confirmación (todavía no guarda)
        r = self.client.post(reverse("votaciones:seleccionar_opcion", args=[a1.pk]), {"opcion": op.pk})
        self.assertContains(r, "Confirme su voto")
        self.assertContains(r, "Grupo A")
        self.assertEqual(Voto.objects.count(), 0)
        # Paso 2: confirmar → se registra
        r = self.votar(a1, op)
        self.assertRedirects(r, reverse("votaciones:mis_votos"))
        self.assertContains(r, "Voto registrado")
        voto = Voto.objects.get()
        self.assertEqual((voto.usuario, voto.edicion, voto.categoria, voto.votacion, voto.opcion),
                         (self.usuario, self.d["edicion"], self.d["cat_a"], a1, op))

    def test_cp02_segundo_voto_misma_categoria(self):
        """CP-02 Intenta votar otra vez en la misma categoría (otra opción u otro subevento): se rechaza."""
        self.votar(self.d["a1"], self.d["op"]["Grupo A"])
        r = self.votar(self.d["a1"], self.d["op"]["Grupo B"])            # otra opción, mismo subevento
        self.assertContains(r, "Ya votó en la categoría")
        r = self.votar(self.d["a2"], self.d["op"]["Semillero 1"])        # otro subevento, misma categoría
        self.assertContains(r, "Ya votó en la categoría")
        self.assertEqual(Voto.objects.count(), 1)
        self.assertEqual(Voto.objects.get().opcion.nombre, "Grupo A")

    def test_cp03_voto_en_otra_categoria(self):
        """CP-03 Vota en una categoría diferente: se permite el voto."""
        self.votar(self.d["a1"], self.d["op"]["Grupo A"])
        r = self.votar(self.d["b1"], self.d["op"]["Canción 2"])
        self.assertContains(r, "Voto registrado")
        self.assertEqual(Voto.objects.filter(usuario=self.usuario).count(), 2)

    def test_cp04_usuario_no_autenticado(self):
        """CP-04 Usuario no autenticado intenta votar: se exige autenticación."""
        self.client.logout()
        url = reverse("votaciones:confirmar_voto", args=[self.d["a1"].pk])
        r = self.client.post(url, {"opcion": self.d["op"]["Grupo A"].pk})
        self.assertRedirects(r, f"{reverse('cuentas:login')}?next={url}", fetch_redirect_response=False)
        r = self.client.get(reverse("votaciones:mis_votos"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Voto.objects.count(), 0)
        # Aun llamando directamente al servicio, sin usuario no se registra
        with self.assertRaises(VotoRechazado):
            registrar_voto(None, self.d["a1"].pk, self.d["op"]["Grupo A"].pk)

    def test_cp05_categoria_no_habilitada(self):
        """CP-05 Intenta votar en una categoría no habilitada (aún no abre o ya cerró): se rechaza."""
        r = self.votar(self.d["c1"], self.d["op"]["Comparsa 1"])
        self.assertContains(r, "no está habilitada")
        r = self.votar(self.d["d1"], self.d["op"]["Acordeonero 1"])
        self.assertContains(r, "no está habilitada")
        # Categoría desactivada por el administrador
        Categoria.objects.filter(pk=self.d["cat_b"].pk).update(activa=False)
        r = self.client.post(reverse("votaciones:confirmar_voto", args=[self.d["b1"].pk]),
                             {"opcion": self.d["op"]["Canción 1"].pk})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Voto.objects.count(), 0)

    def test_cp06_opcion_de_otra_categoria(self):
        """CP-06 Envía una opción que pertenece a otra categoría: se rechaza la operación."""
        r = self.votar(self.d["a1"], self.d["op"]["Canción 1"])           # opción de la categoría B
        self.assertContains(r, "no pertenece a esta votación")
        r = self.client.post(reverse("votaciones:confirmar_voto", args=[self.d["a1"].pk]),
                             {"opcion": "999999"}, follow=True)          # opción inexistente
        self.assertContains(r, "no existe o no está activa")
        r = self.client.post(reverse("votaciones:confirmar_voto", args=[self.d["a1"].pk]),
                             {"opcion": "abc"}, follow=True)             # valor manipulado
        self.assertContains(r, "no existe o no está activa")
        self.assertEqual(Voto.objects.count(), 0)

    def test_cp07_consulta_categorias_votadas(self):
        """CP-07 Consulta sus categorías votadas: se muestran los registros correctos."""
        self.votar(self.d["a2"], self.d["op"]["Semillero 2"])
        self.votar(self.d["b1"], self.d["op"]["Canción 1"])
        otro = User.objects.create_user("luis@ejemplo.com", "luis@ejemplo.com", CLAVE)
        Voto.objects.create(usuario=otro, edicion=self.d["edicion"], categoria=self.d["cat_a"],
                            votacion=self.d["a1"], opcion=self.d["op"]["Grupo B"])
        r = self.client.get(reverse("votaciones:mis_votos"))
        self.assertContains(r, "Categorías votadas (2)")
        self.assertContains(r, "Semillero 2")
        self.assertContains(r, "Canción 1")
        self.assertNotContains(r, "Grupo B")                             # voto de otro usuario
        # El detalle de la votación también informa el voto
        r = self.client.get(reverse("votaciones:votacion_detalle", args=[self.d["a1"].pk]))
        self.assertContains(r, "Ya votó en esta categoría")
        self.assertNotContains(r, 'name="opcion"')                       # no se ofrece votar otra vez

    def test_cp08_administrador_consulta_votos(self):
        """CP-08 Administrador consulta los votos: los datos coinciden con MySQL."""
        self.votar(self.d["a1"], self.d["op"]["Grupo A"])
        self.votar(self.d["b1"], self.d["op"]["Canción 2"])
        admin = User.objects.create_superuser("admin", "admin@ejemplo.com", CLAVE)
        self.client.force_login(admin)
        r = self.client.get(reverse("admin:votaciones_voto_changelist"))
        self.assertEqual(r.status_code, 200)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM votaciones_voto")
            total_mysql = cursor.fetchone()[0]
        self.assertEqual(r.context["cl"].result_count, total_mysql)
        self.assertContains(r, "Grupo A")
        self.assertContains(r, "Canción 2")
        # Los votos no se pueden crear ni borrar desde el admin
        self.assertEqual(self.client.get(reverse("admin:votaciones_voto_add")).status_code, 403)

    def test_cp10_api_categorias(self):
        """CP-10 Se consulta GET /api/categorias/: devuelve JSON válido con categorías y opciones reales."""
        self.client.logout()                                             # es pública
        r = self.client.get(reverse("votaciones:api_categorias"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        datos = json.loads(r.content)
        nombres = [c["nombre"] for c in datos["categorias"]]
        self.assertEqual(datos["total_categorias"], Categoria.objects.filter(activa=True).count())
        self.assertIn("Piloneras", nombres)
        piloneras = next(c for c in datos["categorias"] if c["nombre"] == "Piloneras")
        self.assertEqual(len(piloneras["votaciones"]), 2)
        self.assertEqual({o["nombre"] for v in piloneras["votaciones"] for o in v["opciones"]},
                         {"Grupo A", "Grupo B", "Semillero 1", "Semillero 2"})
        self.assertNotIn("Votación en borrador", r.content.decode())
        # Solo lectura y validación de parámetros
        self.assertEqual(self.client.post(reverse("votaciones:api_categorias")).status_code, 405)
        self.assertEqual(self.client.get(reverse("votaciones:api_categorias"), {"edicion": "abc"}).status_code, 400)
        self.assertEqual(json.loads(self.client.get(reverse("votaciones:api_categorias"),
                                                    {"edicion": "1999"}).content)["total_categorias"], 0)

    def test_extra_csrf_obligatorio(self):
        """Extra: un POST de voto sin token CSRF es rechazado (403)."""
        cliente = Client(enforce_csrf_checks=True)
        cliente.login(username="ana@ejemplo.com", password=CLAVE)
        r = cliente.post(reverse("votaciones:confirmar_voto", args=[self.d["a1"].pk]),
                         {"opcion": self.d["op"]["Grupo A"].pk})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Voto.objects.count(), 0)

    def test_extra_restriccion_unica_en_mysql(self):
        """Extra: la restricción única de MySQL rechaza un duplicado insertado sin pasar por Django."""
        base = dict(usuario=self.usuario, edicion=self.d["edicion"], categoria=self.d["cat_a"])
        Voto.objects.create(votacion=self.d["a1"], opcion=self.d["op"]["Grupo A"], **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(votacion=self.d["a2"], opcion=self.d["op"]["Semillero 1"], **base)


class ConcurrenciaTests(TransactionTestCase):
    """CP-09 usa transacciones reales de MySQL y varios hilos al mismo tiempo."""

    def setUp(self):
        self.d = crear_escenario()
        self.usuario = User.objects.create_user("ana@ejemplo.com", "ana@ejemplo.com", CLAVE)

    def lanzar_simultaneos(self, intentos):
        barrera = threading.Barrier(len(intentos))
        resultados = []

        def votar(votacion, opcion):
            try:
                barrera.wait()                                           # todos salen a la vez
                voto = registrar_voto(self.usuario, votacion.pk, opcion.pk)
                resultados.append(("aceptado", voto.pk))
            except VotoRechazado as e:
                resultados.append(("rechazado", e.codigo))
            finally:
                connection.close()

        hilos = [threading.Thread(target=votar, args=x) for x in intentos]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        return resultados

    def test_cp09_solicitudes_simultaneas(self):
        """CP-09 Se envían dos solicitudes simultáneas a la misma categoría: solo queda un voto válido."""
        op = self.d["op"]
        resultados = self.lanzar_simultaneos([(self.d["a1"], op["Grupo A"]), (self.d["a2"], op["Semillero 1"])])
        self.assertEqual(sorted(r[0] for r in resultados), ["aceptado", "rechazado"])
        self.assertEqual(Voto.objects.filter(usuario=self.usuario, categoria=self.d["cat_a"]).count(), 1)

    def test_cp09b_diez_solicitudes_simultaneas(self):
        """CP-09b Diez solicitudes simultáneas del mismo usuario en la misma categoría: solo queda un voto."""
        op = self.d["op"]
        intentos = [(self.d["a1"], op["Grupo A"]), (self.d["a1"], op["Grupo B"]),
                    (self.d["a2"], op["Semillero 1"]), (self.d["a2"], op["Semillero 2"])] * 2
        intentos += [(self.d["a1"], op["Grupo A"])] * 2
        resultados = self.lanzar_simultaneos(intentos)
        self.assertEqual([r[0] for r in resultados].count("aceptado"), 1)
        self.assertEqual([r[0] for r in resultados].count("rechazado"), 9)
        self.assertEqual(Voto.objects.filter(usuario=self.usuario, categoria=self.d["cat_a"]).count(), 1)
