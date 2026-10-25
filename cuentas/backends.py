from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CorreoOUsuarioBackend(ModelBackend):
    """Permite iniciar sesión con el correo electrónico (votantes) o con el
    nombre de usuario (administradores creados con createsuperuser)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        usuario = (
            User.objects.filter(email__iexact=username).order_by("pk").first()
            or User.objects.filter(username__iexact=username).first()
        )
        if usuario is None:
            User().set_password(password)  # mitiga ataques de tiempo
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
