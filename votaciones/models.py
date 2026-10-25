"""
Modelos de la jerarquía configurable definida en la Entrega 1 (RN-01):

    Edición  1 ── N  Categoría  1 ── N  Votación  1 ── N  Opción

El modelo Voto (con la restricción única usuario + votación, RN-02) se
incorporará en la siguiente entrega; esta estructura ya lo permite porque
cada Opción conoce su Votación.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Edicion(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        PUBLICADA = "PUBLICADA", "Publicada"
        INACTIVA = "INACTIVA", "Inactiva"

    nombre = models.CharField("nombre", max_length=150)
    anio = models.PositiveSmallIntegerField("año", unique=True)
    numero = models.PositiveSmallIntegerField("número de edición", null=True, blank=True)
    homenaje = models.CharField("homenaje", max_length=150, blank=True)
    descripcion = models.TextField("descripción", blank=True)
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField("fecha de fin")
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "edición"
        verbose_name_plural = "ediciones"
        ordering = ["-anio"]

    def __str__(self):
        return f"{self.nombre} ({self.anio})"

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin no puede ser anterior a la fecha de inicio."})

    def get_absolute_url(self):
        return reverse("votaciones:edicion_detalle", args=[self.anio])


class Categoria(models.Model):
    edicion = models.ForeignKey(
        Edicion, on_delete=models.PROTECT, related_name="categorias", verbose_name="edición"
    )
    nombre = models.CharField("nombre", max_length=150)
    descripcion = models.TextField("descripción", blank=True)
    orden = models.PositiveSmallIntegerField("orden", default=0)
    activa = models.BooleanField("activa", default=True)
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["edicion", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["edicion", "nombre"], name="categoria_unica_por_edicion"),
        ]

    def __str__(self):
        return f"{self.nombre} · {self.edicion.anio}"

    def get_absolute_url(self):
        return reverse("votaciones:categoria_detalle", args=[self.pk])


class Votacion(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        ABIERTA = "ABIERTA", "Abierta"
        CERRADA = "CERRADA", "Cerrada"

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="votaciones", verbose_name="categoría"
    )
    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    reglas = models.TextField("reglas para el votante", blank=True)
    fecha_apertura = models.DateTimeField("fecha de apertura")
    fecha_cierre = models.DateTimeField("fecha de cierre")
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    activa = models.BooleanField("activa", default=True)
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "votación"
        verbose_name_plural = "votaciones"
        ordering = ["fecha_apertura", "titulo"]

    def __str__(self):
        return self.titulo

    def clean(self):
        # CU-06, flujo 4a: la fecha de cierre debe ser posterior a la de apertura
        if self.fecha_apertura and self.fecha_cierre and self.fecha_cierre <= self.fecha_apertura:
            raise ValidationError({"fecha_cierre": "La fecha de cierre debe ser posterior a la fecha de apertura."})

    @property
    def esta_abierta(self):
        """RN-03: solo se vota con estado Abierta y dentro de las fechas."""
        ahora = timezone.now()
        return (
            self.activa
            and self.estado == self.Estado.ABIERTA
            and self.fecha_apertura <= ahora <= self.fecha_cierre
        )

    @property
    def estado_publico(self):
        """Estado que ve el público: Abierta, Próxima o Cerrada."""
        ahora = timezone.now()
        if self.estado == self.Estado.BORRADOR or not self.activa:
            return "No publicada"
        if self.esta_abierta:
            return "Abierta"
        if self.estado != self.Estado.CERRADA and ahora < self.fecha_apertura:
            return "Próxima"
        return "Cerrada"

    def get_absolute_url(self):
        return reverse("votaciones:votacion_detalle", args=[self.pk])


class Opcion(models.Model):
    votacion = models.ForeignKey(
        Votacion, on_delete=models.PROTECT, related_name="opciones", verbose_name="votación"
    )
    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    imagen = models.ImageField("imagen", upload_to="opciones/", blank=True)
    orden = models.PositiveSmallIntegerField("orden", default=0)
    activa = models.BooleanField("activa", default=True)
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "opción"
        verbose_name_plural = "opciones"
        ordering = ["votacion", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["votacion", "nombre"], name="opcion_unica_por_votacion"),
        ]

    def __str__(self):
        return self.nombre
