"""
Perfil del votante. Se usa el modelo User de Django (django.contrib.auth)
para la autenticación y se guarda aparte la autorización de tratamiento de
datos personales exigida por la Ley 1581 de 2012 (RN-09, RNF07).
"""
from django.conf import settings
from django.db import models


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil", verbose_name="usuario"
    )
    acepta_tratamiento_datos = models.BooleanField("acepta tratamiento de datos", default=False)
    fecha_autorizacion = models.DateTimeField("fecha de autorización", null=True, blank=True)

    class Meta:
        verbose_name = "perfil de votante"
        verbose_name_plural = "perfiles de votantes"

    def __str__(self):
        return f"Perfil de {self.usuario.get_full_name() or self.usuario.username}"
