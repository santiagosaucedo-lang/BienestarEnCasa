from django.db.models import Q
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Categoria, Servicio, ContenidoMultimediaServicio, ElementoServicio
from .serializers import (
    CategoriaSerializer,
    ServicioSerializer,
    ServicioUpdateSerializer,
    ContenidoMultimediaServicioSerializer,
    ElementoServicioSerializer,
)
from .permissions import IsProveedorOwnerOrReadOnly, IsProviderOwner, es_dueno_servicio


def filtrar_visibles(queryset, user, prefijo=''):
    #cuando consulta un cliente o el proveedr que no es dueño, le muestra solo activo si no los otros
    """Servicios activos para todos; los inactivos solo para su proveedor dueño."""
    return queryset.filter(
        Q(**{f'{prefijo}estado__iexact': Servicio.Estado.ACTIVO})
        | Q(**{f'{prefijo}proveedor__perfil_usuario__usuario': user})
    )


class ServicioGestionView(generics.RetrieveUpdateAPIView):
    serializer_class = ServicioUpdateSerializer
    # CA6: IsAuthenticated deniega acceso a usuarios sin sesión
    # CA5: IsProviderOwner deniega operaciones sobre servicios ajenos
    permission_classes = [permissions.IsAuthenticated, IsProviderOwner]

    def get_queryset(self):
        """CA1 y CA5: solo servicios del proveedor autenticado."""
        return Servicio.objects.filter(proveedor__perfil_usuario__usuario=self.request.user)

class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    #sirve para traer todas las categorias y llama a serilizer


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.select_related(
        'categoria', 'proveedor__perfil_usuario__usuario'
    ).prefetch_related('multimedia', 'elementos')
    serializer_class = ServicioSerializer
    permission_classes = [permissions.IsAuthenticated, IsProveedorOwnerOrReadOnly]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categoria']
    search_fields = [
        'nombre',
        'proveedor__perfil_usuario__usuario__first_name',
        'proveedor__perfil_usuario__usuario__last_name',
        'proveedor__perfil_usuario__usuario__username',
    ]

    def get_queryset(self): #filtra
        return filtrar_visibles(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        # HU-06: Validar y asignar el perfil proveedor al registrar servicios
        user = self.request.user
        
        # 1. Asegurar que el perfil de usuario existe y tiene rol PROVEEDOR
        perfil_usuario = getattr(user, 'perfil', None)
        if not perfil_usuario:
            raise PermissionDenied("El usuario no tiene un perfil asociado.")
            
        if perfil_usuario.rol != 'PROVEEDOR':
            # Asignar rol PROVEEDOR automáticamente si está intentando crear servicios
            perfil_usuario.rol = 'PROVEEDOR'
            perfil_usuario.save()

        # 2. Obtener o crear el PerfilProveedor si no existe aún
        from usuarios.models import PerfilProveedor
        perfil_profesional, _ = PerfilProveedor.objects.get_or_create(perfil_usuario=perfil_usuario)

        # 3. Guardar asignando el proveedor
        serializer.save(proveedor=perfil_profesional)

    # HU-10: Detalle de servicio
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Http404:
            return Response(
                {"error": "El servicio solicitado no fue encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=['get'], url_path='mios',
            permission_classes=[permissions.IsAuthenticated])
    def mios(self, request):
        """Devuelve únicamente los servicios del proveedor autenticado,
        incluyendo los inactivos, sin importar los de otros proveedores."""
        
        # Nota importante: Si la función `filtrar_visibles` en `get_queryset` 
        # oculta los servicios inactivos, cambia `self.get_queryset()` por `super().get_queryset()`
        # para asegurar que el dueño pueda ver incluso sus servicios inactivos.
        qs = self.get_queryset().filter(
            proveedor__perfil_usuario__usuario=request.user
        )
        
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

class DetalleServicioViewSet(viewsets.ModelViewSet): #para traer los datos del servicio y solo el dueño puede escribir
    """Base para multimedia y elementos: solo el dueño del servicio escribe (HU-08)."""
    permission_classes = [permissions.IsAuthenticated, IsProveedorOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['servicio']

    def get_queryset(self):
        return filtrar_visibles(super().get_queryset(), self.request.user, 'servicio__')
    #de aqui pa abajo verifica que sea la persona que creo el servicio y si no es, no puede modificarlo
    def verificar_servicio(self, serializer):
        servicio = serializer.validated_data.get('servicio') or serializer.instance.servicio
        if not es_dueno_servicio(self.request.user, servicio): #verifica si el dueño 
            raise PermissionDenied("Solo el proveedor dueño del servicio puede modificar su contenido.")
    #lo manda a crear
    def perform_create(self, serializer):
        self.verificar_servicio(serializer)
        serializer.save()
    #lo manda a actualizar
    def perform_update(self, serializer):
        self.verificar_servicio(serializer)
        serializer.save()


class ContenidoMultimediaServicioViewSet(DetalleServicioViewSet):
    queryset = ContenidoMultimediaServicio.objects.select_related('servicio')
    serializer_class = ContenidoMultimediaServicioSerializer
    #para traer los datos del servicio y solo el dueño puede escribir, hereda de DetalleServicioViewSet


class ElementoServicioViewSet(DetalleServicioViewSet):
    queryset = ElementoServicio.objects.select_related('servicio')
    serializer_class = ElementoServicioSerializer
    # lo mismo de arriba pero para elementos
