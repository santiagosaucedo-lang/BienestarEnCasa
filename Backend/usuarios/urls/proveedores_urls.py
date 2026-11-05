from django.urls import path

from ..views import (
    MiPerfilProveedorView, 
    MisZonasAtencionView, 
    ZonaAtencionDetalleView,  
    ProveedorDetalleView,
    ProveedorListaView,  # Importamos la vista de lista/búsqueda
    DisponibilidadProveedorDetailView,
    DisponibilidadProveedorListCreateView,
    DisponibilidadPublicaView,
    PeriodoNoDisponibleDetailView,
    PeriodoNoDisponibleListCreateView,
)

urlpatterns = [
    path('mi-perfil/', MiPerfilProveedorView.as_view(), name='mi-perfil-proveedor'),
    path('mis-zonas/', MisZonasAtencionView.as_view(), name='mis-zonas-atencion'),
    path('mis-zonas/<int:pk>/', ZonaAtencionDetalleView.as_view(), name='detalle-zona-atencion'),

    # HU-11: disponibilidad y periodos no disponibles del proveedor autenticado
    path('disponibilidad/', DisponibilidadProveedorListCreateView.as_view(), name='disponibilidad-proveedor'),
    path('disponibilidad/<int:pk>/', DisponibilidadProveedorDetailView.as_view(), name='detalle-disponibilidad-proveedor'),
    path('periodos-no-disponibles/', PeriodoNoDisponibleListCreateView.as_view(), name='periodos-no-disponibles'),
    path('periodos-no-disponibles/<int:pk>/', PeriodoNoDisponibleDetailView.as_view(), name='detalle-periodo-no-disponible'),
    
    # HU-09 / HU-10: perfil público del proveedor con su catálogo activo
    path('<int:pk>/disponibilidad-publica/', DisponibilidadPublicaView.as_view(), name='disponibilidad-publica'),
    path('<int:pk>/', ProveedorDetalleView.as_view(), name='detalle-proveedor'),
    
    # HU-10: Buscar proveedores por nombre 
    path('', ProveedorListaView.as_view(), name='api-proveedores-lista'),
]
