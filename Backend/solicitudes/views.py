from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db.models import Q

from .models import SolicitudReserva
from .serializers import SolicitudReservaSerializer
from usuarios.authentication import CookieJWTAuthentication
from usuarios.models import PerfilUsuario

class ClienteSolicitudesViewSet(viewsets.ModelViewSet):
    """
    Vista para la gestión y consulta de solicitudes/reservas (Clientes y Proveedores)
    """
    serializer_class = SolicitudReservaSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        usuario = self.request.user
        if not usuario or not usuario.is_authenticated:
            return SolicitudReserva.objects.none()

        perfil = getattr(usuario, 'perfil', None)
        rol = str(getattr(perfil, 'rol', '')).upper()

        # Si el usuario es PROVEEDOR, obtiene las solicitudes dirigidas a sus servicios o a su perfil
        if rol in ['PROVEEDOR', 'PRO'] or usuario.is_staff:
            perfil_profesional = getattr(perfil, 'perfil_profesional', None)
            
            # Construir filtro flexible para proveedores
            filtro_proveedor = Q(servicio__proveedor__perfil_usuario__usuario=usuario) | Q(proveedor__perfil_usuario__usuario=usuario)
            if perfil_profesional:
                filtro_proveedor |= Q(proveedor=perfil_profesional)
                
            return SolicitudReserva.objects.filter(filtro_proveedor).distinct().order_by('-creado_en')

        # Si es CLIENTE, retorna únicamente sus solicitudes creadas
        return SolicitudReserva.objects.filter(cliente=usuario).order_by('-creado_en')

    def perform_create(self, serializer):
        servicio = serializer.validated_data.get('servicio')
        proveedor_obj = None

        # 1. Obtener el proveedor desde el servicio de forma segura
        if servicio:
            if hasattr(servicio, 'proveedor') and servicio.proveedor:
                proveedor_obj = servicio.proveedor

        # 2. Asignar el User autenticado como cliente y el proveedor identificado
        serializer.save(
            cliente=self.request.user,
            proveedor=proveedor_obj
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"mensaje": "No tienes solicitudes o reservas registradas.", "resultados": []},
                status=status.HTTP_200_OK
            )
        return super().list(request, *args, **kwargs)