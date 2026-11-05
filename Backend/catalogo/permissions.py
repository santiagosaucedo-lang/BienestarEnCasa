from rest_framework import permissions
from usuarios.models import PerfilUsuario

class IsProviderOwner(permissions.BasePermission):
    """
    Permite el acceso solo al proveedor dueño del servicio.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        if hasattr(obj, 'proveedor') and hasattr(obj.proveedor, 'perfil_usuario'):
            return obj.proveedor.perfil_usuario.usuario == request.user
        return True


class IsProveedor(permissions.BasePermission):
    """
    Verifica que el usuario autenticado sea un Proveedor con perfil activo.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        perfil = getattr(request.user, 'perfil', None)
        if perfil is not None:
            return str(getattr(perfil, 'rol', '')).upper() in ['PROVEEDOR', 'PRO']
        return False


class IsProveedorOwnerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        # Lectura permitida a cualquiera
        if request.method in permissions.SAFE_METHODS:
            return True

        # Para modificar/eliminar debe estar autenticado
        if not request.user or not request.user.is_authenticated:
            return False

        # Si es admin o staff, tiene acceso total
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Verificar rol de proveedor
        perfil = getattr(request.user, 'perfil', None)
        if perfil is not None:
            return str(getattr(perfil, 'rol', '')).upper() in ['PROVEEDOR', 'PRO']

        return False

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user.is_staff or request.user.is_superuser:
            return True

        # Los servicios guardan el proveedor directamente; los archivos y
        # elementos lo heredan mediante su relación con el servicio.
        servicio = getattr(obj, 'servicio', obj)
        proveedor = getattr(servicio, 'proveedor', None)

        # 1. Comprobar por perfil profesional
        perfil = getattr(request.user, 'perfil', None)
        if perfil and hasattr(perfil, 'perfil_profesional'):
            if getattr(servicio, 'proveedor_id', None) == perfil.perfil_profesional.id:
                return True

        # 2. Comprobar por relación directa con el usuario
        if proveedor and hasattr(proveedor, 'perfil_usuario'):
            if proveedor.perfil_usuario.usuario == request.user:
                return True

        
        return False


def es_dueno_servicio(user, servicio):
    """
    Función auxiliar para validar si un usuario es dueño de un servicio o tiene rol de proveedor.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True

    perfil = getattr(user, 'perfil', None)
    if perfil and hasattr(perfil, 'perfil_profesional'):
        if hasattr(servicio, 'proveedor_id') and servicio.proveedor_id == perfil.perfil_profesional.id:
            return True

    if hasattr(servicio, 'proveedor') and hasattr(servicio.proveedor, 'perfil_usuario'):
        if servicio.proveedor.perfil_usuario.usuario == user:
            return True

    return False
