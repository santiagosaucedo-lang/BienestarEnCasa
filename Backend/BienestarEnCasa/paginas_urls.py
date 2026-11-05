"""
Rutas de las PÁGINAS (HTML) del frontend.

Estas vistas solo entregan la plantilla; los datos los cargan las plantillas
llamando a la API (/api/...) con el token JWT. No modifican ni reemplazan
ninguna ruta de la API.
"""
from django.urls import path
from django.views.generic import TemplateView
from usuarios.disponibilidad_views import GestionarDisponibilidadPageView


def pagina(plantilla):
    return TemplateView.as_view(template_name=plantilla)


urlpatterns = [
    # Página de inicio / Landing Page
    path('', pagina('inicio.html'), name='pagina-inicio'),

    # Usuarios
    path('iniciar-sesion/', pagina('users/iniciar-sesion.html'), name='pagina-login'),
    path('registro/', pagina('users/registro.html'), name='pagina-registro'),
    path('mi-perfil/', pagina('users/mi-perfil.html'), name='pagina-perfil'),
    path('mis-direcciones/', pagina('users/direcciones.html'), name='pagina-direcciones'),

    # Proveedor
    path('panel-proveedor/', pagina('users/plantilla-proveedor.html'), name='pagina-panel-proveedor'),
    path('disponibilidad/', GestionarDisponibilidadPageView.as_view(), name='pagina-disponibilidad'),
    path('agenda/', pagina('users/agenda-proveedor.html'), name='pagina-agenda'),  # HU-19
    path('solicitudes-recibidas/', pagina('solicitudes/solicitudes-recibidas.html'), name='pagina-solicitudes-recibidas'),  # HU-14
    path('perfil-profesional/', pagina('users/perfil-proveedor.html'), name='pagina-perfil-proveedor'),
    path('zonas-atencion/', pagina('users/zonas-atencion.html'), name='pagina-zonas'),
    path('mis-servicios/', pagina('catalogo/mis-servicios.html'), name='pagina-mis-servicios'),
    path('mis-servicios/nuevo/', pagina('catalogo/servicio-form.html'), name='pagina-servicio-nuevo'),
    path('mis-servicios/<int:pk>/editar/', pagina('catalogo/servicio-form.html'), name='pagina-servicio-editar'),

    # Catálogo
    path('catalogo/', pagina('catalogo/list-servicios.html'), name='pagina-catalogo'),
    path('catalogo/<int:pk>/', pagina('catalogo/detalle-servicio.html'), name='pagina-servicio'),

    # Solicitudes
    path('solicitar/<int:pk>/', pagina('solicitudes/solicitudes-crear.html'), name='pagina-solicitud-crear'),
    path('mis-solicitudes/', pagina('solicitudes/mis-solicitudes.html'), name='pagina-mis-solicitudes'),
    path('mis-solicitudes/<int:pk>/', pagina('solicitudes/detalle-solicitud.html'), name='pagina-solicitud-detalle'),
]
