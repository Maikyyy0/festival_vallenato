from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render

from .forms import IngresoForm, RegistroForm


def registro(request):
    if request.user.is_authenticated:
        return redirect("votaciones:inicio")
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario, backend="cuentas.backends.CorreoOUsuarioBackend")
            messages.success(request, f"¡Bienvenido, {usuario.first_name}! Su cuenta fue creada correctamente.")
            return redirect("votaciones:inicio")
    else:
        form = RegistroForm()
    return render(request, "cuentas/registro.html", {"form": form})


class IngresoView(auth_views.LoginView):
    template_name = "cuentas/login.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        nombre = self.request.user.first_name or self.request.user.username
        messages.success(self.request, f"Sesión iniciada. Hola, {nombre}.")
        return respuesta


class SalidaView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        messages.info(request, "Sesión cerrada correctamente.")
        return super().post(request, *args, **kwargs)
