from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import Perfil

User = get_user_model()


class RegistroForm(UserCreationForm):
    """RF01 / CU-01: nombre, correo, contraseña y aceptación de datos."""

    first_name = forms.CharField(label="Nombre completo", max_length=150)
    email = forms.EmailField(label="Correo electrónico")
    acepta_datos = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales según la Ley 1581 de 2012",
        required=True,
        error_messages={"required": "Debe aceptar el tratamiento de datos para crear la cuenta."},
    )

    class Meta:
        model = User
        fields = ("first_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"
        for nombre, campo in self.fields.items():
            if nombre != "acepta_datos":
                campo.widget.attrs.setdefault("class", "form-control")
        self.fields["acepta_datos"].widget.attrs["class"] = "form-check-input"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            # CU-01, flujo 2a
            raise forms.ValidationError("Ya existe una cuenta con este correo. Puede iniciar sesión.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.username = self.cleaned_data["email"]
        usuario.email = self.cleaned_data["email"]
        usuario.first_name = self.cleaned_data["first_name"].strip()
        if commit:
            usuario.save()
            Perfil.objects.create(
                usuario=usuario, acepta_tratamiento_datos=True, fecha_autorizacion=timezone.now()
            )
        return usuario


class IngresoForm(AuthenticationForm):
    """CU-02: el votante ingresa con su correo y contraseña."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Correo electrónico"
        self.fields["password"].label = "Contraseña"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control"

    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos. Verifique e intente de nuevo.",
        "inactive": "Esta cuenta está inactiva.",
    }
