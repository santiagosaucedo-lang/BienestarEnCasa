import datetime as dt
from datetime import date, datetime, time
from unittest import mock
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Servicio
from usuarios.models import DisponibilidadProveedor, PerfilProveedor, PerfilUsuario
from . import limites
from .models import SolicitudReserva

User = get_user_model()
Estado = SolicitudReserva.Estado


class ReservaMismoDiaTests(APITestCase):
    def setUp(self):
        usuario_proveedor = get_user_model().objects.create_user(
            username='proveedor-horario@example.com', email='proveedor-horario@example.com', password='x'
        )
        perfil_proveedor = PerfilUsuario.objects.create(
            usuario=usuario_proveedor, rol=PerfilUsuario.Rol.PROVEEDOR
        )
        self.proveedor = PerfilProveedor.objects.create(
            perfil_usuario=perfil_proveedor, descripcion_profesional='Proveedor de pruebas'
        )
        self.cliente = get_user_model().objects.create_user(
            username='cliente-horario@example.com', email='cliente-horario@example.com', password='x'
        )
        PerfilUsuario.objects.create(usuario=self.cliente, rol=PerfilUsuario.Rol.CLIENTE)
        categoria = Categoria.objects.create(nombre='Servicios de prueba')
        self.servicio = Servicio.objects.create(
            proveedor=self.proveedor,
            categoria=categoria,
            nombre='Servicio de prueba',
            duracion_minutos=60,
            precio=25000,
        )
        DisponibilidadProveedor.objects.create(
            proveedor=self.proveedor,
            dia_semana=5,
            hora_inicio=time(8),
            hora_fin=time(17),
        )
        self.client.force_authenticate(self.cliente)

    def test_rechaza_horas_pasadas_y_la_hora_actual_del_dia(self):
        hoy = date(2026, 10, 31)
        ahora = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo('America/Bogota'))
        with patch('usuarios.validators.timezone.localdate', return_value=hoy), patch(
            'usuarios.validators.timezone.localtime', return_value=ahora
        ):
            for hora in ('11:00:00', '12:00:00'):
                respuesta = self.client.post('/api/solicitudes/', {
                    'servicio': self.servicio.pk,
                    'proveedor': self.proveedor.pk,
                    'fecha_solicitada': hoy.isoformat(),
                    'hora_solicitada': hora,
                    'direccion_atencion': 'Calle de prueba 123',
                    'barrio_sector': 'Centro',
                }, format='json')
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('hora_solicitada', respuesta.data)

            futura = self.client.post('/api/solicitudes/', {
                'servicio': self.servicio.pk,
                'proveedor': self.proveedor.pk,
                'fecha_solicitada': hoy.isoformat(),
                'hora_solicitada': '13:00:00',
                'direccion_atencion': 'Calle de prueba 123',
                'barrio_sector': 'Centro',
            }, format='json')

        self.assertEqual(futura.status_code, 201, futura.data)
        self.assertEqual(futura.data['hora_solicitada'], '13:00:00')

        self.client.force_authenticate(self.proveedor.perfil_usuario.usuario)
        actualizacion = self.client.patch(f'/api/catalogo/servicios/{self.servicio.pk}/', {
            'nombre': 'Servicio actualizado',
            'precio': '40000.00',
            'duracion_minutos': 90,
        }, format='json')
        self.assertEqual(actualizacion.status_code, 200, actualizacion.data)

        solicitud = SolicitudReserva.objects.get(pk=futura.data['id'])
        self.assertEqual(solicitud.nombre_servicio_copia, 'Servicio de prueba')
        self.assertEqual(str(solicitud.precio_copia), '25000.00')
        self.assertEqual(solicitud.duracion_minutos_copia, 60)

        desactivacion = self.client.patch(f'/api/catalogo/servicios/{self.servicio.pk}/', {
            'estado': 'INACTIVO',
        }, format='json')
        self.assertEqual(desactivacion.status_code, 200, desactivacion.data)
        self.client.force_authenticate(self.cliente)
        solicitud_inactiva = self.client.post('/api/solicitudes/', {
            'servicio': self.servicio.pk,
            'proveedor': self.proveedor.pk,
            'fecha_solicitada': '2026-11-02',
            'hora_solicitada': '13:00:00',
            'direccion_atencion': 'Calle de prueba 123',
            'barrio_sector': 'Centro',
        }, format='json')
        self.assertEqual(solicitud_inactiva.status_code, 400)
        self.assertIn('servicio', solicitud_inactiva.data)


MSG_CRUCE = 'Ya tienes una solicitud en ese horario. Elige otra hora.'
MSG_LIMITE = 'Solo puedes hacer hasta 3 solicitudes por día.'


def dia_habil(posicion=1):
    """Devuelve el n-ésimo día hábil (lunes a viernes) después de hoy."""
    fecha = timezone.localdate()
    while posicion > 0:
        fecha += dt.timedelta(days=1)
        if fecha.weekday() < 5:
            posicion -= 1
    return fecha


class LimitesSolicitudesClienteTests(APITestCase):
    url = '/api/solicitudes/'

    @classmethod
    def setUpTestData(cls):
        cls.cliente = cls._usuario('cliente@test.com', PerfilUsuario.Rol.CLIENTE)
        cls.otro_cliente = cls._usuario('otro@test.com', PerfilUsuario.Rol.CLIENTE)
        user_prov = cls._usuario('prov@test.com', PerfilUsuario.Rol.PROVEEDOR)
        user_prov2 = cls._usuario('prov2@test.com', PerfilUsuario.Rol.PROVEEDOR)
        cls.proveedor = PerfilProveedor.objects.create(
            perfil_usuario=user_prov.perfil, descripcion_profesional='Masajista')
        cls.proveedor2 = PerfilProveedor.objects.create(
            perfil_usuario=user_prov2.perfil, descripcion_profesional='Peluquero')
        categoria = Categoria.objects.create(nombre='Bienestar')
        cls.servicio = Servicio.objects.create(
            proveedor=cls.proveedor, categoria=categoria, nombre='Masaje',
            duracion_minutos=60, precio='80000')
        cls.servicio2 = Servicio.objects.create(
            proveedor=cls.proveedor2, categoria=categoria, nombre='Corte',
            duracion_minutos=30, precio='20000')
        cls.fecha = dia_habil(1)

    @staticmethod
    def _usuario(email, rol):
        user = User.objects.create_user(username=email, email=email, password='x12345678')
        PerfilUsuario.objects.create(usuario=user, rol=rol)
        return user

    # ----------------------------------------------------------------- helpers
    def existente(self, hora, estado=Estado.PENDIENTE, cliente=None, fecha=None, servicio=None):
        """Crea directamente en la base una solicitud previa del cliente."""
        servicio = servicio or self.servicio
        return SolicitudReserva.objects.create(
            cliente=cliente or self.cliente,
            proveedor=servicio.proveedor,
            servicio=servicio,
            nombre_servicio_copia=servicio.nombre,
            precio_copia=servicio.precio,
            duracion_minutos_copia=servicio.duracion_minutos,
            fecha_solicitada=fecha or self.fecha,
            hora_solicitada=hora,
            direccion_atencion='Calle 1',
            barrio_sector='Centro',
            estado=estado,
        )

    def crear(self, hora, cliente=None, fecha=None, servicio=None):
        """Crea una solicitud por la API, como lo hace el formulario."""
        servicio = servicio or self.servicio
        self.client.force_authenticate(cliente or self.cliente)
        return self.client.post(self.url, {
            'servicio': servicio.id,
            'proveedor': servicio.proveedor.id,
            'fecha_solicitada': (fecha or self.fecha).isoformat(),
            'hora_solicitada': hora,
            'direccion_atencion': 'Calle 1 # 2-3',
            'barrio_sector': 'Centro',
        }, format='json')

    def assertRechazo(self, respuesta, campo, mensaje):
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual([str(m) for m in respuesta.data[campo]], [mensaje])

    def total_del_cliente(self):
        return SolicitudReserva.objects.filter(cliente=self.cliente).count()

    # ---------------------------------------------- Regla 1: sin cruces de hora
    def test_segunda_solicitud_a_la_misma_hora_da_400(self):
        self.assertEqual(self.crear('10:00').status_code, 201)
        self.assertRechazo(self.crear('10:00'), 'hora_solicitada', MSG_CRUCE)
        self.assertEqual(self.total_del_cliente(), 1)

    def test_solapamiento_parcial_da_400(self):
        self.existente(dt.time(10, 0))  # 10:00 a 11:00
        self.assertRechazo(self.crear('10:30'), 'hora_solicitada', MSG_CRUCE)

    def test_nueva_que_empieza_antes_y_termina_dentro_da_400(self):
        self.existente(dt.time(10, 0))  # 10:00 a 11:00
        # servicio2 dura 30 min: 09:45 a 10:15 se cruza con las 10:00
        self.assertRechazo(self.crear('09:45', servicio=self.servicio2), 'hora_solicitada', MSG_CRUCE)

    def test_solicitudes_consecutivas_se_permiten(self):
        self.existente(dt.time(10, 0))  # termina a las 11:00
        self.assertEqual(self.crear('11:00').status_code, 201)
        # y la que termina justo cuando empieza la existente (09:00 + 60 min = 10:00)
        self.assertEqual(self.crear('09:00').status_code, 201)

    def test_mismo_horario_con_otro_proveedor_da_400(self):
        self.existente(dt.time(10, 0))  # con proveedor 1
        self.assertRechazo(
            self.crear('10:00', servicio=self.servicio2), 'hora_solicitada', MSG_CRUCE)

    def test_dos_clientes_a_la_misma_hora_se_permiten(self):
        self.existente(dt.time(10, 0), cliente=self.otro_cliente)
        self.assertEqual(self.crear('10:00').status_code, 201)

    def test_cuentan_pendiente_sugerida_y_aceptada(self):
        for estado in (Estado.PENDIENTE, Estado.SUGERIDA, Estado.ACEPTADA):
            with self.subTest(estado=estado):
                SolicitudReserva.objects.all().delete()
                self.existente(dt.time(10, 0), estado=estado)
                self.assertRechazo(self.crear('10:00'), 'hora_solicitada', MSG_CRUCE)

    def test_canceladas_y_completadas_no_cuentan_para_el_cruce(self):
        for estado in (Estado.CANCELADA, Estado.COMPLETADA):
            with self.subTest(estado=estado):
                SolicitudReserva.objects.all().delete()
                self.existente(dt.time(10, 0), estado=estado)
                self.assertEqual(self.crear('10:00').status_code, 201)

    def test_mismo_horario_en_otro_dia_se_permite(self):
        self.existente(dt.time(10, 0), fecha=dia_habil(2))
        self.assertEqual(self.crear('10:00').status_code, 201)

    # ------------------------------------- Regla 2: máximo 3 solicitudes por día
    def test_la_tercera_se_permite_y_la_cuarta_da_400(self):
        self.existente(dt.time(9, 0))
        self.existente(dt.time(10, 0))
        self.assertEqual(self.crear('11:00').status_code, 201)  # la tercera
        self.assertRechazo(self.crear('12:00'), 'fecha_solicitada', MSG_LIMITE)
        self.assertEqual(self.total_del_cliente(), 3)

    def test_limite_aplica_con_proveedores_distintos(self):
        self.existente(dt.time(9, 0))
        self.existente(dt.time(10, 0), servicio=self.servicio2)
        self.existente(dt.time(11, 0))
        self.assertRechazo(
            self.crear('13:00', servicio=self.servicio2), 'fecha_solicitada', MSG_LIMITE)

    def test_cancelada_no_cuenta_para_el_limite(self):
        self.existente(dt.time(9, 0))
        self.existente(dt.time(10, 0))
        self.existente(dt.time(11, 0), estado=Estado.CANCELADA)  # no cuenta: 2 activas
        self.assertEqual(self.crear('12:00').status_code, 201)         # llega a 3 activas
        self.assertRechazo(self.crear('13:00'), 'fecha_solicitada', MSG_LIMITE)

    def test_completada_no_cuenta_para_el_limite(self):
        self.existente(dt.time(9, 0))
        self.existente(dt.time(10, 0))
        self.existente(dt.time(11, 0), estado=Estado.COMPLETADA)
        self.assertEqual(self.crear('12:00').status_code, 201)

    def test_solicitudes_de_otro_dia_no_cuentan_para_el_limite(self):
        otro_dia = dia_habil(2)
        for hora in (9, 10, 11):
            self.existente(dt.time(hora, 0), fecha=otro_dia)
        self.assertEqual(self.crear('09:00').status_code, 201)

    def test_el_limite_es_por_cliente(self):
        for hora in (9, 10, 11):
            self.existente(dt.time(hora, 0), cliente=self.otro_cliente)
        self.assertEqual(self.crear('09:00').status_code, 201)

    def test_si_hay_cruce_y_limite_a_la_vez_se_informa_el_cruce(self):
        for hora in (9, 10, 11):
            self.existente(dt.time(hora, 0))
        self.assertRechazo(self.crear('10:00'), 'hora_solicitada', MSG_CRUCE)

    # --------------------------------------------------- Solo al crear / carrera
    def test_las_reglas_no_se_aplican_al_editar(self):
        for hora in (9, 10, 11):
            self.existente(dt.time(hora, 0))
        solicitud = SolicitudReserva.objects.get(hora_solicitada=dt.time(11, 0))
        self.client.force_authenticate(self.cliente)
        r = self.client.patch(
            f'{self.url}{solicitud.id}/', {'hora_solicitada': '13:00'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_al_guardar_se_vuelven_a_validar_las_reglas_dentro_de_la_transaccion(self):
        """Simula una petición concurrente: la validación inicial pasó con datos viejos
        (primera llamada sin efecto) y la solicitud rival ya está guardada al momento de crear."""
        self.existente(dt.time(10, 0))
        llamadas = []

        def validacion_desactualizada(*args, **kwargs):
            llamadas.append(1)
            if len(llamadas) > 1:
                return limites.validar_limites_cliente(*args, **kwargs)

        with mock.patch('solicitudes.serializers.validar_limites_cliente',
                        side_effect=validacion_desactualizada):
            respuesta = self.crear('10:00')

        self.assertEqual(len(llamadas), 2)  # validate() y create()
        self.assertRechazo(respuesta, 'hora_solicitada', MSG_CRUCE)
        self.assertEqual(self.total_del_cliente(), 1)

    def test_la_cuarta_tambien_se_rechaza_al_guardar_aunque_validate_no_la_detecte(self):
        for hora in (9, 10, 11):
            self.existente(dt.time(hora, 0))
        llamadas = []

        def validacion_desactualizada(*args, **kwargs):
            llamadas.append(1)
            if len(llamadas) > 1:
                return limites.validar_limites_cliente(*args, **kwargs)

        with mock.patch('solicitudes.serializers.validar_limites_cliente',
                        side_effect=validacion_desactualizada):
            respuesta = self.crear('13:00')

        self.assertRechazo(respuesta, 'fecha_solicitada', MSG_LIMITE)
        self.assertEqual(self.total_del_cliente(), 3)
