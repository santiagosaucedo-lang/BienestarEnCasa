from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
import uuid
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from catalogo.serializers import ServicioSerializer
from .models import Direccion, DisponibilidadProveedor, PerfilProveedor, PerfilUsuario, PeriodoNoDisponible, ZonaAtencion

Usuario = get_user_model()


class RegistroSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=150)
    apellidos = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmacion = serializers.CharField(write_only=True, trim_whitespace=False)
    rol = serializers.ChoiceField(choices=PerfilUsuario.Rol.choices)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmacion']:
            raise serializers.ValidationError({'password_confirmacion': 'Las contraseñas no coinciden.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password_confirmacion')
        password = validated_data.pop('password')
        rol = validated_data.pop('rol')
        telefono = validated_data.pop('telefono', '')
        email = validated_data.pop('email')
        usuario = Usuario.objects.create_user(
            username=email,
            email=email,
            first_name=validated_data['nombres'],
            last_name=validated_data['apellidos'],
            password=password,
        )
        return PerfilUsuario.objects.create(usuario=usuario, rol=rol, telefono=telefono)


class PerfilSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='usuario.email', read_only=True)
    nombres = serializers.CharField(source='usuario.first_name', read_only=True)
    apellidos = serializers.CharField(source='usuario.last_name', read_only=True)
    direccion_principal = serializers.SerializerMethodField()

    class Meta:
        model = PerfilUsuario
        fields = (
            'id', 'email', 'nombres', 'apellidos', 'rol', 'telefono',
            'direccion_principal', 'creado_en', 'actualizado_en',
        )
        read_only_fields = ('id', 'rol', 'creado_en', 'actualizado_en')

    def get_direccion_principal(self, obj):
        direccion = obj.usuario.direcciones.filter(es_principal=True).first()
        if direccion:
            return DireccionSerializer(direccion).data
        return None


class ActualizarPerfilSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(
        source='usuario.first_name',
        max_length=150,
        required=False,
    )
    apellidos = serializers.CharField(
        source='usuario.last_name',
        max_length=150,
        required=False,
    )
    email = serializers.EmailField(
        source='usuario.email',
        required=False,
    )

    class Meta:
        model = PerfilUsuario
        fields = ('nombres', 'apellidos', 'email', 'telefono')

    def validate_email(self, value):
        email = value.lower()
        usuario_actual = self.instance.usuario
        if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario_actual.pk).exists():
            raise serializers.ValidationError('Este correo ya está registrado por otro usuario.')
        return email

    def update(self, instance, validated_data):
        datos_usuario = validated_data.pop('usuario', {})

        if 'email' in datos_usuario:
            nuevo_email = datos_usuario['email'].lower()
            instance.usuario.email = nuevo_email
            instance.usuario.username = nuevo_email

        if 'first_name' in datos_usuario:
            instance.usuario.first_name = datos_usuario['first_name']

        if 'last_name' in datos_usuario:
            instance.usuario.last_name = datos_usuario['last_name']

        if datos_usuario:
            instance.usuario.save()

        return super().update(instance, validated_data)


class InicioSesionSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['sid'] = str(uuid.uuid4())
        return token

    def validate(self, attrs):
        try:
            usuario = Usuario.objects.get(email__iexact=attrs['email'].lower())
        except Usuario.DoesNotExist:
            raise AuthenticationFailed('Correo o contraseña incorrectos.')

        usuario = authenticate(username=usuario.username, password=attrs['password'])
        if usuario is None or not usuario.is_active:
            raise AuthenticationFailed('Correo o contraseña incorrectos.')

        refresh = self.get_token(usuario)
        return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direccion
        fields = (
            'id',
            'direccion',
            'ciudad',
            'barrio',
            'complemento',
            'es_principal',
            'creado_en',
        )
        read_only_fields = ('id', 'creado_en')
        extra_kwargs = {
            'barrio': {'required': False, 'allow_blank': True},
            'complemento': {'required': False, 'allow_blank': True, 'allow_null': True},
        }


class PerfilProveedorSerializer(serializers.ModelSerializer):
    zonas_atencion = serializers.SerializerMethodField()

    class Meta:
        model = PerfilProveedor
        fields = (
            'id',
            'descripcion_profesional',
            'zonas_atencion',
            'creado_en',
            'actualizado_en',
        )
        read_only_fields = ('id', 'creado_en', 'actualizado_en')

    def get_zonas_atencion(self, obj):
        zonas = obj.zonas_atencion.all()
        return ZonaAtencionSerializer(zonas, many=True).data

class ZonaAtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZonaAtencion
        fields = ('id', 'ciudad', 'barrio_sector')
        read_only_fields = ('id',)



class DisponibilidadProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisponibilidadProveedor
        fields = ('id', 'dia_semana', 'hora_inicio', 'hora_fin')
        read_only_fields = ('id',)

    def validate(self, attrs):
        inicio = attrs.get('hora_inicio', getattr(self.instance, 'hora_inicio', None))
        fin = attrs.get('hora_fin', getattr(self.instance, 'hora_fin', None))
        dia = attrs.get('dia_semana', getattr(self.instance, 'dia_semana', None))
        if inicio and fin and inicio >= fin:
            raise serializers.ValidationError({
                'hora_fin': 'La hora inicial debe ser anterior a la hora final.'
            })
        request = self.context.get('request')
        perfil = getattr(getattr(request, 'user', None), 'perfil', None)
        if perfil and dia is not None:
            existentes = DisponibilidadProveedor.objects.filter(
                proveedor__perfil_usuario=perfil,
                dia_semana=dia,
            )
            if self.instance:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                raise serializers.ValidationError({
                    'dia_semana': 'Ya existe un horario para este día; actualízalo desde su registro.'
                })
        return attrs


class PeriodoNoDisponibleProveedorSerializer(serializers.ModelSerializer):
    fecha_fin = serializers.DateField(required=False)

    class Meta:
        model = PeriodoNoDisponible
        fields = ('id', 'fecha_inicio', 'fecha_fin', 'motivo')
        read_only_fields = ('id',)
        extra_kwargs = {'motivo': {'required': False, 'allow_blank': True}}

    def validate(self, attrs):
        inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fin = attrs.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if inicio and fin and inicio > fin:
            raise serializers.ValidationError({
                'fecha_fin': 'La fecha de inicio no puede ser posterior a la fecha de fin.'
            })
        if inicio and not fin:
            attrs['fecha_fin'] = inicio
        return attrs


class ProveedorPublicoSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source='perfil_usuario.usuario.first_name', read_only=True)
    apellidos = serializers.CharField(source='perfil_usuario.usuario.last_name', read_only=True)
    zonas_atencion = ZonaAtencionSerializer(many=True, read_only=True)
    servicios = ServicioSerializer(many=True, read_only=True)

    class Meta:
        model = PerfilProveedor
        fields = (
            'id',
            'nombres',
            'apellidos',
            'descripcion_profesional',
            'zonas_atencion',
            'servicios',
        )