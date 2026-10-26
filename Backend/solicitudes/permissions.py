from rest_framework.permissions import BasePermission

from usuarios.models import PerfilUsuario


def _rol(user):
    perfil = getattr(user, 'perfil', None)
    return getattr(perfil, 'rol', None)


class EsCliente(BasePermission):
    """Solo usuarios autenticados con rol CLIENTE."""

    message = 'Solo un cliente puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and _rol(user) == PerfilUsuario.Rol.CLIENTE)


class EsProveedor(BasePermission):
    """Solo usuarios autenticados con rol PROVEEDOR."""

    message = 'Solo un proveedor puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and _rol(user) == PerfilUsuario.Rol.PROVEEDOR)
