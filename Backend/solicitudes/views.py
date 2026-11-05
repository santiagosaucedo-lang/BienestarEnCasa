import datetime

from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import SolicitudReserva
from .serializers import SolicitudReservaSerializer
from usuarios.authentication import CookieJWTAuthentication
from usuarios.models import PerfilUsuario, PeriodoNoDisponible
from .permissions import EsCliente, EsProveedor

class ClienteSolicitudesViewSet(viewsets.ModelViewSet):
    """
    Vista para la gestión y consulta de solicitudes/reservas (Clientes y Proveedores)
    """
    serializer_class = SolicitudReservaSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # HU-12: solo un cliente crea solicitudes
        if self.action == 'create':
            return [permissions.IsAuthenticated(), EsCliente()]
        # HU-14 y HU-19: solo el proveedor consulta lo recibido y su agenda
        if self.action in ('recibidas', 'agenda'):
            return [permissions.IsAuthenticated(), EsProveedor()]
        return super().get_permissions()

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

    # HU-14: solicitudes recibidas por el proveedor
    @action(detail=False, methods=['get'], url_path='recibidas')
    def recibidas(self, request):
        queryset = SolicitudReserva.objects.filter(
            proveedor__perfil_usuario__usuario=request.user
        ).order_by('-creado_en')

        estado = (request.query_params.get('estado') or '').upper()
        if estado:
            if estado not in SolicitudReserva.Estado.values:
                raise ValidationError({'estado': 'Estado no válido.'})
            queryset = queryset.filter(estado=estado)

        return Response({
            'resumen': {
                e: SolicitudReserva.objects.filter(
                    proveedor__perfil_usuario__usuario=request.user, estado=e
                ).count()
                for e in SolicitudReserva.Estado.values
            },
            'resultados': self.get_serializer(queryset, many=True).data,
        })

    # HU-19: agenda del proveedor (reservas aceptadas, bloqueos y horario semanal)
    @action(detail=False, methods=['get'], url_path='agenda')
    def agenda(self, request):
        def fecha_param(nombre):
            valor = request.query_params.get(nombre)
            if not valor:
                return None
            fecha = parse_date(valor)
            if fecha is None:
                raise ValidationError({nombre: 'Usa el formato AAAA-MM-DD.'})
            return fecha

        desde = fecha_param('desde') or timezone.localdate()
        hasta = fecha_param('hasta') or (desde + datetime.timedelta(days=30))
        if hasta < desde:
            raise ValidationError({'hasta': 'La fecha final no puede ser anterior a la inicial.'})
        if (hasta - desde).days > 92:
            raise ValidationError({'hasta': 'El rango máximo es de 92 días.'})

        reservas = SolicitudReserva.objects.filter(
            proveedor__perfil_usuario__usuario=request.user,
            estado=SolicitudReserva.Estado.ACEPTADA,
            fecha_solicitada__gte=desde,
            fecha_solicitada__lte=hasta,
        ).order_by('fecha_solicitada', 'hora_solicitada')

        perfil_proveedor = getattr(request.user.perfil, 'perfil_profesional', None)
        periodos, horario = [], []
        if perfil_proveedor:
            periodos = [
                {
                    'id': p.id,
                    'fecha_inicio': p.fecha_inicio.isoformat(),
                    'fecha_fin': p.fecha_fin.isoformat(),
                    'motivo': p.motivo,
                }
                for p in PeriodoNoDisponible.objects.filter(
                    proveedor=perfil_proveedor, fecha_inicio__lte=hasta, fecha_fin__gte=desde
                )
            ]
            horario = [
                {
                    'dia_semana': d.dia_semana,
                    'dia': d.get_dia_semana_display(),
                    'hora_inicio': d.hora_inicio.strftime('%H:%M'),
                    'hora_fin': d.hora_fin.strftime('%H:%M'),
                }
                for d in perfil_proveedor.disponibilidades.all()
            ]

        return Response({
            'desde': desde.isoformat(),
            'hasta': hasta.isoformat(),
            'reservas': self.get_serializer(reservas, many=True).data,
            'periodos_no_disponibles': periodos,
            'horario_semanal': horario,
        })
