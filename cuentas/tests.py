from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Perfil

User = get_user_model()
CLAVE = "Acordeon#2027Seguro"


class RegistroTests(TestCase):
    def datos(self, **extra):
        d = {"first_name": "Ana Prueba", "email": "ana@ejemplo.com", "password1": CLAVE,
             "password2": CLAVE, "acepta_datos": "on"}
        d.update(extra)
        return d

    def test_registro_crea_usuario_perfil_e_inicia_sesion(self):
        r = self.client.post(reverse("cuentas:registro"), self.datos(), follow=True)
        u = User.objects.get(email="ana@ejemplo.com")
        self.assertTrue(u.check_password(CLAVE))
        self.assertNotEqual(u.password, CLAVE)  # guardada con hash (RNF01)
        self.assertTrue(u.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(Perfil.objects.get(usuario=u).acepta_tratamiento_datos)
        self.assertTrue(r.context["user"].is_authenticated)

    def test_sin_aceptar_datos_no_crea_cuenta(self):
        # CU-01, flujo 2b / RN-09.
        d = self.datos(); d.pop("acepta_datos")
        r = self.client.post(reverse("cuentas:registro"), d)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="ana@ejemplo.com").exists())

    def test_correo_duplicado(self):
        # CU-01, flujo 2a.
        User.objects.create_user("ana@ejemplo.com", "ana@ejemplo.com", CLAVE)
        r = self.client.post(reverse("cuentas:registro"), self.datos(email="ANA@ejemplo.com"))
        self.assertContains(r, "Ya existe una cuenta con este correo")
        self.assertEqual(User.objects.count(), 1)

    def test_contrasenas_distintas(self):
        # CU-01, flujo 3a.
        r = self.client.post(reverse("cuentas:registro"), self.datos(password2="Otra#Clave2027"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 0)


class SesionTests(TestCase):
    def setUp(self):
        User.objects.create_user("luis@ejemplo.com", "luis@ejemplo.com", CLAVE, first_name="Luis")

    def test_login_con_correo(self):
        r = self.client.post(reverse("cuentas:login"), {"username": "luis@ejemplo.com", "password": CLAVE}, follow=True)
        self.assertTrue(r.context["user"].is_authenticated)
        self.assertContains(r, "Hola, Luis")

    def test_login_credenciales_incorrectas(self):
        # CU-02, flujo 3a.
        r = self.client.post(reverse("cuentas:login"), {"username": "luis@ejemplo.com", "password": "incorrecta"})
        self.assertContains(r, "Correo o contraseña incorrectos")

    def test_logout_por_post(self):
        self.client.login(username="luis@ejemplo.com", password=CLAVE)
        r = self.client.post(reverse("cuentas:logout"), follow=True)
        self.assertFalse(r.context["user"].is_authenticated)
        self.assertContains(r, "Sesión cerrada correctamente")
