import datetime
from rest_framework import serializers
from .models import SolicitudReserva
from catalogo.models import Servicio  # Ajusta la importación según la ubicación de tu modelo Servicio
from usuarios.disponibilidad import validar_horario_reserva

class SolicitudReservaSerializer(serializers.ModelSerializer):
    nombre_proveedor = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudReserva
        fields = [
            'id', 'cliente', 'cliente_nombre', 'proveedor', 'nombre_proveedor', 'servicio',
            'nombre_servicio_copia', 'precio_copia', 'duracion_minutos_copia',
            'fecha_solicitada', 'hora_solicitada', 'direccion_atencion',
            'barrio_sector', 'informacion_complementaria', 'observaciones',
            'estado', 'motivo_rechazo_cancelacion', 'creado_en', 'actualizado_en'
        ]
        read_only_fields = [
            'cliente', 'nombre_servicio_copia', 'precio_copia',
            'duracion_minutos_copia', 'estado', 'motivo_rechazo_cancelacion',
            'creado_en', 'actualizado_en'
        ]

    def get_cliente_nombre(self, obj):
        if not obj.cliente:
            return "Usuario"

        # 1. Nombre completo desde el modelo User de Django
        first_name = getattr(obj.cliente, 'first_name', '')
        last_name = getattr(obj.cliente, 'last_name', '')
        nombre_completo = f"{first_name} {last_name}".strip()
        if nombre_completo:
            return nombre_completo

        # 2. Nombre completo desde PerfilUsuario si existe
        perfil = getattr(obj.cliente, 'perfil', None)
        if perfil:
            nom_p = getattr(perfil, 'nombres', '')
            ape_p = getattr(perfil, 'apellidos', '')
            completo_perfil = f"{nom_p} {ape_p}".strip()
            if completo_perfil:
                return completo_perfil

        # 3. Nombre basado en email
        email = getattr(obj.cliente, 'email', '')
        if email:
            return email.split('@')[0].capitalize()

        return getattr(obj.cliente, 'username', 'Usuario')

    def get_nombre_proveedor(self, obj):
        if not obj.proveedor or not hasattr(obj.proveedor, 'perfil_usuario'):
            return "Proveedor no asignado"
        u = obj.proveedor.perfil_usuario.usuario
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def validate_servicio(self, servicio):
        # HU-12: solo se puede solicitar un servicio activo del catálogo
        if servicio is not None and servicio.estado != Servicio.Estado.ACTIVO:
            raise serializers.ValidationError('El servicio seleccionado no está disponible.')
        return servicio

    def validate(self, attrs):
        fecha = attrs.get('fecha_solicitada')
        hora = attrs.get('hora_solicitada')

        # 1. Validación de Días (Lunes a Viernes)
        if fecha:
            if fecha.weekday() in [5, 6]:
                raise serializers.ValidationError({
                    "fecha_solicitada": "El servicio solo atiende de Lunes a Viernes."
                })
            
            if fecha < datetime.date.today():
                raise serializers.ValidationError({
                    "fecha_solicitada": "No se pueden agendar solicitudes para fechas pasadas."
                })

        # 2. Validación de Horario (8:00 AM a 5:00 PM)
        if hora:
            hora_inicio = datetime.time(8, 0, 0)
            hora_fin = datetime.time(17, 0, 0)

            if not (hora_inicio <= hora <= hora_fin):
                raise serializers.ValidationError({
                    "hora_solicitada": "El horario de atención es únicamente de 8:00 AM a 5:00 PM."
                })

        return super().validate(attrs)

    def validate(self, attrs):
        if self.instance is None and not attrs.get('servicio'):
            raise serializers.ValidationError({'servicio': 'Debes seleccionar un servicio.'})

        campos_horario = {'fecha_solicitada', 'hora_solicitada', 'servicio'}
        if self.instance is None or campos_horario.intersection(attrs):
            fecha = attrs.get('fecha_solicitada', getattr(self.instance, 'fecha_solicitada', None))
            hora = attrs.get('hora_solicitada', getattr(self.instance, 'hora_solicitada', None))
            servicio = attrs.get('servicio', getattr(self.instance, 'servicio', None))
            proveedor = (
                servicio.proveedor if servicio
                else getattr(self.instance, 'proveedor', None)
            )
            if self.instance and 'servicio' not in attrs:
                duracion = self.instance.duracion_minutos_copia
            else:
                duracion = servicio.duracion_minutos if servicio else 0
            validar_horario_reserva(proveedor, fecha, hora, duracion)

        return super().validate(attrs)

    def create(self, validated_data):
        servicio = validated_data.get('servicio')

        # Si el campo servicio vino como un entero/ID, obtenemos el objeto de la BD
        if isinstance(servicio, int):
            servicio = Servicio.objects.filter(id=servicio).first()

        # Si el objeto servicio existe, copiamos sus atributos; de lo contrario asignamos valores por defecto no nulos
        if servicio:
            validated_data['nombre_servicio_copia'] = getattr(servicio, 'nombre', 'Servicio General')
            validated_data['precio_copia'] = getattr(servicio, 'precio', 0.00)
            validated_data['duracion_minutos_copia'] = getattr(servicio, 'duracion_minutos', 60)
        else:
            validated_data['nombre_servicio_copia'] = 'Servicio General'
            validated_data['precio_copia'] = 0.00
            validated_data['duracion_minutos_copia'] = 60

        return super().create(validated_data)