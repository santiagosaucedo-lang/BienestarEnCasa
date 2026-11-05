from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError, NotAuthenticated, AuthenticationFailed
from .models import (
    Direccion,
    DisponibilidadProveedor,
    PerfilProveedor,
    PerfilUsuario,
    PeriodoNoDisponible,
    ZonaAtencion,
    SesionActiva,
)
from .authentication import CookieJWTAuthentication  # <--- HABILITA LECTURA DE COOKIE JWT
from .forms import DIAS_SEMANA, DisponibilidadProveedorForm, PeriodoNoDisponibleForm
from .permissions import EsProveedorRegistrado

from rest_framework.permissions import AllowAny, IsAuthenticated
from catalogo.models import Servicio
from django.db.models import Q
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from .serializers import (
    ProveedorPublicoSerializer, ZonaAtencionSerializer, PerfilProveedorSerializer,
    ActualizarPerfilSerializer, DireccionSerializer, InicioSesionSerializer,
    PerfilSerializer, RegistroSerializer, DisponibilidadProveedorSerializer,
    PeriodoNoDisponibleProveedorSerializer
)
from catalogo.serializers import ServicioSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

class RegistroView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = RegistroSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perfil = serializer.save() 
        return Response(PerfilSerializer(perfil).data, status=status.HTTP_201_CREATED)


def poner_cookies(response):
    for nombre, vida in (('access', jwt_settings.ACCESS_TOKEN_LIFETIME), ('refresh', jwt_settings.REFRESH_TOKEN_LIFETIME)):
        if nombre in response.data:
            response.set_cookie(nombre, response.data.pop(nombre), max_age=int(vida.total_seconds()),
                                httponly=True, secure=not settings.DEBUG, samesite='Lax')
    return response


class InicioSesionView(TokenObtainPairView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = InicioSesionSerializer

    def post(self, request, *args, **kwargs):
        # 1. Obtener los tokens de SimpleJWT
        response = super().post(request, *args, **kwargs)
        refresh = RefreshToken(response.data['refresh'])
        usuario_id = refresh[jwt_settings.USER_ID_CLAIM]

        # 2. Invalida tokens anteriores y registra sesión activa
        for t in OutstandingToken.objects.filter(user_id=usuario_id).exclude(jti=refresh['jti']):
            BlacklistedToken.objects.get_or_create(token=t)

        SesionActiva.objects.update_or_create(
            usuario_id=usuario_id,
            defaults={
                'session_id': refresh['sid'],
                'refresh_jti': refresh['jti'],
                'dispositivo': request.META.get('HTTP_USER_AGENT', '')[:255],
                'ip': request.META.get('REMOTE_ADDR'),
            }
        )

        # 3. PRIMERO PONER COOKIES (Estarán disponibles en las cabeceras HTTP Set-Cookie)
        response = poner_cookies(response)

        # 4. LUEGO Adjuntar el perfil/rol al JSON de respuesta
        try:
            perfil_obj = PerfilUsuario.objects.get(usuario_id=usuario_id)
            response.data = PerfilSerializer(perfil_obj).data
        except PerfilUsuario.DoesNotExist:
            pass

        return response


class RenovarTokenView(TokenRefreshView):
    authentication_classes = ()
    def get_serializer(self, *args, **kwargs):
        kwargs['data'] = {'refresh': self.request.COOKIES.get('refresh', '')}
        return super().get_serializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        return poner_cookies(super().post(request, *args, **kwargs))


class CerrarSesionView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        refresh = request.COOKIES.get('refresh')
        if refresh:
            try:
                token = RefreshToken(refresh)
                SesionActiva.objects.filter(usuario_id=token[jwt_settings.USER_ID_CLAIM], session_id=token.get('sid')).delete()
                token.blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie('access', samesite='Lax')
        response.delete_cookie('refresh', samesite='Lax')
        return response


class MiPerfilView(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'patch', 'head', 'options']
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return ActualizarPerfilSerializer
        return PerfilSerializer

    def get_object(self):
        return self.request.user.perfil


class DireccionListCreateView(generics.ListCreateAPIView):
    serializer_class = DireccionSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.perfil.rol != PerfilUsuario.Rol.CLIENTE:
            raise PermissionDenied('Solo los clientes pueden consultar direcciones.')

        return Direccion.objects.filter(
            usuario=self.request.user
        ).order_by('-es_principal', '-creado_en')

    def perform_create(self, serializer):
        if self.request.user.perfil.rol != PerfilUsuario.Rol.CLIENTE:
            raise PermissionDenied('Solo los clientes pueden registrar direcciones.')

        es_principal = serializer.validated_data.get('es_principal', False)
        if es_principal:
            Direccion.objects.filter(
                usuario=self.request.user,
                es_principal=True,
            ).update(es_principal=False)

        existe_direccion = Direccion.objects.filter(usuario=self.request.user).exists()
        if not existe_direccion:
            es_principal = True

        serializer.save(
            usuario=self.request.user,
            es_principal=es_principal,
        )


class DireccionDetalleView(generics.RetrieveUpdateDestroyAPIView):  # <-- aquí el cambio
    serializer_class = DireccionSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.perfil.rol != PerfilUsuario.Rol.CLIENTE:
            raise PermissionDenied('Solo los clientes pueden consultar direcciones.')

        return Direccion.objects.filter(usuario=self.request.user)

    def perform_update(self, serializer):
        direccion = self.get_object()
        es_principal = serializer.validated_data.get('es_principal')

        if es_principal is True:
            Direccion.objects.filter(
                usuario=self.request.user,
                es_principal=True,
            ).exclude(pk=direccion.pk).update(es_principal=False)

        if es_principal is False and direccion.es_principal:
            existe_otra_principal = Direccion.objects.filter(
                usuario=self.request.user,
                es_principal=True,
            ).exclude(pk=direccion.pk).exists()

            if not existe_otra_principal:
                raise ValidationError(
                    {'es_principal': 'Debe existir al menos una dirección principal.'}
                )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.es_principal:
            siguiente = Direccion.objects.filter(
                usuario=self.request.user
            ).exclude(pk=instance.pk).order_by('-creado_en').first()
            if siguiente:
                siguiente.es_principal = True
                siguiente.save(update_fields=['es_principal'])
        instance.delete()


class MiPerfilProveedorView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def verificar_proveedor(self, request):
        perfil = getattr(request.user, 'perfil', None)
        rol = str(getattr(perfil, 'rol', '')).upper()
        if rol not in ['PROVEEDOR', 'PRO'] and not request.user.is_staff:
            raise PermissionDenied(
                'Solo los proveedores pueden gestionar su perfil profesional.'
            )

    def obtener_perfil(self, request):
        try:
            return request.user.perfil.perfil_profesional
        except PerfilProveedor.DoesNotExist:
            raise NotFound('Aún no has creado tu perfil profesional.')

    def get(self, request):
        self.verificar_proveedor(request)
        perfil = self.obtener_perfil(request)
        return Response(PerfilProveedorSerializer(perfil).data)

    def post(self, request):
        self.verificar_proveedor(request)

        if hasattr(request.user.perfil, 'perfil_profesional'):
            raise ValidationError(
                'Ya existe un perfil profesional para este proveedor.'
            )

        serializer = PerfilProveedorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perfil = serializer.save(perfil_usuario=request.user.perfil)

        return Response(
            PerfilProveedorSerializer(perfil).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        self.verificar_proveedor(request)
        perfil = self.obtener_perfil(request)

        serializer = PerfilProveedorSerializer(
            perfil,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class MisZonasAtencionView(generics.ListCreateAPIView):
    """Gestión de zonas de atención para el proveedor logueado (Listar y Crear)."""
    serializer_class = ZonaAtencionSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def obtener_perfil_proveedor(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            raise PermissionDenied('No existe un perfil asociado a este usuario.')

        rol = str(getattr(perfil, 'rol', '')).upper()
        if rol not in ['PROVEEDOR', 'PRO'] and not self.request.user.is_staff:
            raise PermissionDenied('Solo los proveedores pueden gestionar zonas de atención.')

        try:
            return perfil.perfil_profesional
        except Exception:
            perfil_prof, _ = PerfilProveedor.objects.get_or_create(perfil_usuario=perfil)
            return perfil_prof

    def get_queryset(self):
        perfil_proveedor = self.obtener_perfil_proveedor()
        return ZonaAtencion.objects.filter(
            perfil_proveedor=perfil_proveedor
        ) if hasattr(ZonaAtencion, 'perfil_proveedor') else ZonaAtencion.objects.filter(proveedor=perfil_proveedor)

    def perform_create(self, serializer):
        perfil_proveedor = self.obtener_perfil_proveedor()
        if hasattr(ZonaAtencion, 'perfil_proveedor'):
            serializer.save(perfil_proveedor=perfil_proveedor)
        else:
            serializer.save(proveedor=perfil_proveedor)


class ZonaAtencionDetalleView(generics.RetrieveDestroyAPIView):
    """Gestión de zona individual (Eliminar / Consultar por ID)."""
    serializer_class = ZonaAtencionSerializer
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        perfil_proveedor = getattr(perfil, 'perfil_profesional', None)

        if hasattr(ZonaAtencion, 'perfil_proveedor'):
            return ZonaAtencion.objects.filter(perfil_proveedor=perfil_proveedor)
        return ZonaAtencion.objects.filter(proveedor=perfil_proveedor)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({"mensaje": "Zona eliminada con éxito"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Error al eliminar la zona: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class ProveedorDetalleView(generics.RetrieveAPIView):
    """Perfil público del proveedor con su catálogo activo (HU-09, HU-10)."""
    serializer_class = ProveedorPublicoSerializer
    permission_classes = [permissions.AllowAny]
    queryset = PerfilProveedor.objects.select_related('perfil_usuario__usuario').prefetch_related(
        'zonas_atencion',
        Prefetch(
            'servicios',
            queryset=Servicio.objects.filter(estado__iexact=Servicio.Estado.ACTIVO)
            .select_related('categoria', 'proveedor__perfil_usuario__usuario')
            .prefetch_related('multimedia', 'elementos'),
        ),
    )


class ProveedorListaView(generics.ListAPIView):
    """
    Lista y busca proveedores por nombre, apellido o descripción profesional
    para alimentar la sección de búsqueda en el catálogo del cliente.
    """
    serializer_class = ProveedorPublicoSerializer
    queryset = PerfilProveedor.objects.select_related('perfil_usuario__usuario').prefetch_related(
        'zonas_atencion',
        Prefetch(
            'servicios',
            queryset=Servicio.objects.filter(estado__iexact=Servicio.Estado.ACTIVO)
            .select_related('categoria', 'proveedor__perfil_usuario__usuario')
            .prefetch_related('multimedia', 'elementos'),
        ),
    )
    permission_classes = [permissions.AllowAny] 

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '').strip()
        
        if search_query:
            # Permite buscar por nombre y apellido por separado (ej: "Manuel Pérez")
            terminos = search_query.split()
            q_filters = Q()
            for termino in terminos:
                q_filters &= (
                    Q(perfil_usuario__usuario__first_name__icontains=termino) |
                    Q(perfil_usuario__usuario__last_name__icontains=termino) |
                    Q(descripcion_profesional__icontains=termino)
                )
            queryset = queryset.filter(q_filters)
            
        return queryset

    def retrieve(self, request, *args, **kwargs):
        try:
            perfil = self.get_object()
        except Http404:
            return Response(
                {'error': 'El proveedor solicitado no fue encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        data = self.get_serializer(perfil).data
        data['email'] = perfil.perfil_usuario.usuario.email
        data['telefono'] = perfil.perfil_usuario.telefono
        data['tiene_zonas_registradas'] = bool(data['zonas_atencion'])
        if not data['zonas_atencion']:
            data['mensaje_zonas'] = 'El proveedor no tiene zonas generales de atención registradas.'
        return Response(data)


class DisponibilidadProveedorListCreateView(generics.ListCreateAPIView):
    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated, EsProveedorRegistrado)
    serializer_class = DisponibilidadProveedorSerializer

    def get_queryset(self):
        return DisponibilidadProveedor.objects.filter(
            proveedor__perfil_usuario=self.request.user.perfil
        )

    def perform_create(self, serializer):
        serializer.save(proveedor=self.get_perfil_proveedor())

    def get_perfil_proveedor(self):
        proveedor, _ = PerfilProveedor.objects.get_or_create(
            perfil_usuario=self.request.user.perfil,
            defaults={'descripcion_profesional': ''},
        )
        return proveedor


class DisponibilidadProveedorDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated, EsProveedorRegistrado)
    serializer_class = DisponibilidadProveedorSerializer

    def get_queryset(self):
        return DisponibilidadProveedor.objects.filter(
            proveedor__perfil_usuario=self.request.user.perfil
        )


class PeriodoNoDisponibleListCreateView(generics.ListCreateAPIView):
    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated, EsProveedorRegistrado)
    serializer_class = PeriodoNoDisponibleProveedorSerializer

    def get_queryset(self):
        return PeriodoNoDisponible.objects.filter(
            proveedor__perfil_usuario=self.request.user.perfil
        )

    def perform_create(self, serializer):
        proveedor, _ = PerfilProveedor.objects.get_or_create(
            perfil_usuario=self.request.user.perfil,
            defaults={'descripcion_profesional': ''},
        )
        serializer.save(proveedor=proveedor)


class PeriodoNoDisponibleDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated, EsProveedorRegistrado)
    serializer_class = PeriodoNoDisponibleProveedorSerializer

    def get_queryset(self):
        return PeriodoNoDisponible.objects.filter(
            proveedor__perfil_usuario=self.request.user.perfil
        )


class GestionarDisponibilidadPageView(APIView):
    """Página HTML con formularios Django; no necesita JavaScript en el navegador."""

    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated, EsProveedorRegistrado)
    template_name = 'users/disponibilidad-proveedor.html'

    def obtener_horarios(self, user):
        return DisponibilidadProveedor.objects.filter(proveedor__perfil_usuario=user.perfil)

    def obtener_periodos(self, user):
        return PeriodoNoDisponible.objects.filter(proveedor__perfil_usuario=user.perfil)

    def obtener_perfil_proveedor(self, user):
        proveedor, _ = PerfilProveedor.objects.get_or_create(
            perfil_usuario=user.perfil,
            defaults={'descripcion_profesional': ''},
        )
        return proveedor

    def contexto(self, request, disponibilidad_form=None, periodo_form=None, periodo_editando=None):
        horarios = list(self.obtener_horarios(request.user))
        horarios_por_dia = {horario.dia_semana: horario for horario in horarios}
        disponibilidad_form = disponibilidad_form or DisponibilidadProveedorForm(horarios=horarios)
        dias_seleccionados = set(disponibilidad_form['dias'].value() or [])
        return {
            'disponibilidad_form': disponibilidad_form,
            'periodo_form': periodo_form or PeriodoNoDisponibleForm(),
            'periodo_editando': periodo_editando,
            'dias': [
                {
                    'valor': valor,
                    'etiqueta': etiqueta,
                    'horario': horarios_por_dia.get(valor),
                    'activo': str(valor) in dias_seleccionados,
                    'hora_inicio': disponibilidad_form[f'hora_inicio_{valor}'],
                    'hora_fin': disponibilidad_form[f'hora_fin_{valor}'],
                }
                for valor, etiqueta in DisponibilidadProveedor.DIAS_SEMANA
            ],
            'periodos': self.obtener_periodos(request.user),
        }

    def get(self, request):
        periodo_editando = None
        periodo_form = None
        periodo_id = request.query_params.get('editar_periodo')
        if periodo_id:
            periodo_editando = get_object_or_404(
                PeriodoNoDisponible,
                pk=periodo_id,
                proveedor__perfil_usuario=request.user.perfil,
            )
            periodo_form = PeriodoNoDisponibleForm(initial={
                'fecha_inicio': periodo_editando.fecha_inicio,
                'fecha_fin': periodo_editando.fecha_fin,
                'motivo': periodo_editando.motivo,
            })
        return render(
            request._request,
            self.template_name,
            self.contexto(request, periodo_form=periodo_form, periodo_editando=periodo_editando),
        )

    def post(self, request):
        form_data = request._request.POST
        accion = form_data.get('accion')

        if accion == 'guardar_disponibilidad':
            form = DisponibilidadProveedorForm(form_data, horarios=self.obtener_horarios(request.user))
            if form.is_valid():
                proveedor = self.obtener_perfil_proveedor(request.user)
                seleccionados = set(form.cleaned_data['dias'])
                with transaction.atomic():
                    for dia, _ in DIAS_SEMANA:
                        if dia in seleccionados:
                            DisponibilidadProveedor.objects.update_or_create(
                                proveedor=proveedor,
                                dia_semana=int(dia),
                                defaults={
                                    'hora_inicio': form.cleaned_data[f'hora_inicio_{dia}'],
                                    'hora_fin': form.cleaned_data[f'hora_fin_{dia}'],
                                },
                            )
                        else:
                            DisponibilidadProveedor.objects.filter(
                                proveedor=proveedor,
                                dia_semana=int(dia),
                            ).delete()
                messages.success(request._request, 'La disponibilidad fue guardada correctamente.')
                return redirect('pagina-disponibilidad')

            return render(
                request._request,
                self.template_name,
                self.contexto(request, disponibilidad_form=form),
                status=400,
            )

        if accion == 'crear_periodo':
            form = PeriodoNoDisponibleForm(form_data)
            if form.is_valid():
                proveedor = self.obtener_perfil_proveedor(request.user)
                PeriodoNoDisponible.objects.create(
                    proveedor=proveedor,
                    **form.cleaned_data,
                )
                messages.success(request._request, 'El periodo no disponible fue registrado correctamente.')
                return redirect('pagina-disponibilidad')

            return render(
                request._request,
                self.template_name,
                self.contexto(request, periodo_form=form),
                status=400,
            )

        if accion == 'actualizar_periodo':
            periodo = get_object_or_404(
                PeriodoNoDisponible,
                pk=form_data.get('periodo_id'),
                proveedor__perfil_usuario=request.user.perfil,
            )
            form = PeriodoNoDisponibleForm(form_data)
            if form.is_valid():
                for campo, valor in form.cleaned_data.items():
                    setattr(periodo, campo, valor)
                periodo.save(update_fields=('fecha_inicio', 'fecha_fin', 'motivo'))
                messages.success(request._request, 'El periodo no disponible fue actualizado correctamente.')
                return redirect('pagina-disponibilidad')

            return render(
                request._request,
                self.template_name,
                self.contexto(request, periodo_form=form, periodo_editando=periodo),
                status=400,
            )

        if accion == 'eliminar_periodo':
            proveedor = self.obtener_perfil_proveedor(request.user)
            periodo = get_object_or_404(
                PeriodoNoDisponible,
                pk=form_data.get('periodo_id'),
                proveedor=proveedor,
            )
            periodo.delete()
            messages.success(request._request, 'El periodo no disponible fue eliminado.')
            return redirect('pagina-disponibilidad')

        messages.error(request._request, 'La operación solicitada no es válida.')
        return redirect('pagina-disponibilidad')


class DisponibilidadPublicaView(APIView):
    """Horario que el cliente puede consultar para armar la solicitud. Solo lectura."""
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, pk):
        proveedor = get_object_or_404(PerfilProveedor, pk=pk)
        dias = [
            {
                'dia_semana': d.dia_semana,
                'hora_inicio': d.hora_inicio.strftime('%H:%M'),
                'hora_fin': d.hora_fin.strftime('%H:%M'),
            }
            for d in proveedor.disponibilidades.all().order_by('dia_semana', 'hora_inicio')
        ]
        periodos = [
            {
                'fecha_inicio': p.fecha_inicio.isoformat(),
                'fecha_fin': p.fecha_fin.isoformat(),
            }
            for p in proveedor.periodos_no_disponibles.all().order_by('fecha_inicio')
        ]
        return Response({'configurado': bool(dias), 'dias': dias, 'periodos': periodos})
