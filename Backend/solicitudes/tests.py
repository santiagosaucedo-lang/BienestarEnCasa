import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Servicio
from usuarios.models import (
    DisponibilidadProveedor, PerfilProveedor, PerfilUsuario, PeriodoNoDisponible,
)

from .models import SolicitudReserva

User = get_user_model()


def proximo_dia_habil(dias_minimos=1):
    fecha = timezone.localdate() + datetime.timedelta(days=dias_minimos)
    while fecha.weekday() >= 5:
        fecha += datetime.timedelta(days=1)
    return fecha


class BaseSolicitudesTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = cls._usuario('cliente@test.com', PerfilUsuario.Rol.CLIENTE)
        cls.otro_cliente = cls._usuario('otro@test.com', PerfilUsuario.Rol.CLIENTE)
        cls.user_prov = cls._usuario('prov@test.com', PerfilUsuario.Rol.PROVEEDOR)
        cls.user_prov2 = cls._usuario('prov2@test.com', PerfilUsuario.Rol.PROVEEDOR)
        cls.proveedor = PerfilProveedor.objects.create(
            perfil_usuario=cls.user_prov.perfil, descripcion_profesional='Masajista')
        cls.proveedor2 = PerfilProveedor.objects.create(
            perfil_usuario=cls.user_prov2.perfil, descripcion_profesional='Peluquero')
        cls.categoria = Categoria.objects.create(nombre='Masajes')
        cls.servicio = Servicio.objects.create(
            proveedor=cls.proveedor, categoria=cls.categoria, nombre='Masaje relajante',
            duracion_minutos=60, precio='80000')
        cls.servicio2 = Servicio.objects.create(
            proveedor=cls.proveedor2, categoria=cls.categoria, nombre='Corte',
            duracion_minutos=30, precio='20000')
        cls.servicio_inactivo = Servicio.objects.create(
            proveedor=cls.proveedor, categoria=cls.categoria, nombre='Masaje viejo',
            duracion_minutos=60, precio='50000', estado=Servicio.Estado.INACTIVO)

    @staticmethod
    def _usuario(email, rol):
        user = User.objects.create_user(
            username=email, email=email, password='x12345678', first_name=email.split('@')[0].capitalize())
        PerfilUsuario.objects.create(usuario=user, rol=rol)
        return user

    def payload(self, **extra):
        data = {
            'servicio': self.servicio.id,
            'proveedor': self.proveedor.id,  # el formulario real lo envía
            'fecha_solicitada': proximo_dia_habil().isoformat(),
            'hora_solicitada': '10:00',
            'direccion_atencion': 'Calle 1 # 2-3',
            'barrio_sector': 'San Fernando',
        }
        data.update(extra)
        return data

    def crear_solicitud(self, cliente=None, estado=SolicitudReserva.Estado.PENDIENTE,
                        hora=datetime.time(10, 0), fecha=None, servicio=None):
        servicio = servicio or self.servicio
        return SolicitudReserva.objects.create(
            cliente=cliente or self.cliente,
            proveedor=servicio.proveedor,
            servicio=servicio,
            nombre_servicio_copia=servicio.nombre,
            precio_copia=servicio.precio,
            duracion_minutos_copia=servicio.duracion_minutos,
            fecha_solicitada=fecha or proximo_dia_habil(),
            hora_solicitada=hora,
            direccion_atencion='Calle 1', barrio_sector='Centro',
            estado=estado,
        )


class HU12CrearSolicitudTests(BaseSolicitudesTest):
    url = '/api/solicitudes/'

    def test_cliente_crea_solicitud_pendiente_con_copia_del_servicio(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        s = SolicitudReserva.objects.get(pk=r.data['id'])
        self.assertEqual(s.estado, SolicitudReserva.Estado.PENDIENTE)
        self.assertEqual(s.cliente, self.cliente)
        self.assertEqual(s.proveedor, self.proveedor)
        self.assertEqual(s.nombre_servicio_copia, 'Masaje relajante')
        self.assertEqual(s.duracion_minutos_copia, 60)

    def test_el_cliente_no_puede_fijar_proveedor_ni_estado(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(self.url, self.payload(
            proveedor=self.proveedor2.id, estado='ACEPTADA'), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        s = SolicitudReserva.objects.get(pk=r.data['id'])
        self.assertEqual(s.proveedor, self.proveedor)
        self.assertEqual(s.estado, SolicitudReserva.Estado.PENDIENTE)

    def test_proveedor_no_puede_crear_solicitudes(self):
        self.client.force_authenticate(self.user_prov)
        r = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(r.status_code, 403)

    def test_requiere_autenticacion(self):
        r = self.client.post(self.url, self.payload(), format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_rechaza_servicio_inactivo(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(self.url, self.payload(servicio=self.servicio_inactivo.id), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('servicio', r.data)

    def test_servicio_es_obligatorio(self):
        self.client.force_authenticate(self.cliente)
        data = self.payload()
        data.pop('servicio')
        r = self.client.post(self.url, data, format='json')
        self.assertEqual(r.status_code, 400)

    def test_rechaza_fecha_pasada_y_fin_de_semana(self):
        self.client.force_authenticate(self.cliente)
        ayer = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        r = self.client.post(self.url, self.payload(fecha_solicitada=ayer), format='json')
        self.assertEqual(r.status_code, 400)

        sabado = timezone.localdate()
        while sabado.weekday() != 5:
            sabado += datetime.timedelta(days=1)
        r = self.client.post(self.url, self.payload(fecha_solicitada=sabado.isoformat()), format='json')
        self.assertEqual(r.status_code, 400)

    def test_rechaza_periodo_no_disponible(self):
        fecha = proximo_dia_habil()
        PeriodoNoDisponible.objects.create(
            proveedor=self.proveedor, fecha_inicio=fecha, fecha_fin=fecha, motivo='Vacaciones')
        self.client.force_authenticate(self.cliente)
        r = self.client.post(self.url, self.payload(fecha_solicitada=fecha.isoformat()), format='json')
        self.assertEqual(r.status_code, 400)

    def test_respeta_horario_semanal_configurado(self):
        fecha = proximo_dia_habil()
        DisponibilidadProveedor.objects.create(
            proveedor=self.proveedor, dia_semana=fecha.weekday(),
            hora_inicio=datetime.time(14, 0), hora_fin=datetime.time(18, 0))
        self.client.force_authenticate(self.cliente)
        r = self.client.post(self.url, self.payload(
            fecha_solicitada=fecha.isoformat(), hora_solicitada='10:00'), format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(self.url, self.payload(
            fecha_solicitada=fecha.isoformat(), hora_solicitada='15:00'), format='json')
        self.assertEqual(r.status_code, 201, r.data)


class HU13ConsultaClienteTests(BaseSolicitudesTest):
    url = '/api/solicitudes/'

    def test_cliente_solo_ve_sus_solicitudes(self):
        mia = self.crear_solicitud()
        self.crear_solicitud(cliente=self.otro_cliente)
        self.client.force_authenticate(self.cliente)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x['id'] for x in r.data], [mia.id])

    def test_lista_vacia_devuelve_mensaje(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['resultados'], [])

    def test_detalle_solo_del_dueno(self):
        s = self.crear_solicitud()
        self.client.force_authenticate(self.otro_cliente)
        self.assertEqual(self.client.get(f'{self.url}{s.id}/').status_code, 404)
        self.client.force_authenticate(self.cliente)
        r = self.client.get(f'{self.url}{s.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nombre_servicio_copia'], 'Masaje relajante')


class HU14SolicitudesRecibidasTests(BaseSolicitudesTest):
    url = '/api/solicitudes/recibidas/'

    def test_proveedor_ve_solo_las_suyas_con_resumen(self):
        s1 = self.crear_solicitud()
        self.crear_solicitud(estado='ACEPTADA', hora=datetime.time(14, 0))
        s_ajena = self.crear_solicitud(servicio=self.servicio2)
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        ids = {x['id'] for x in r.data['resultados']}
        self.assertIn(s1.id, ids)
        self.assertNotIn(s_ajena.id, ids)
        self.assertEqual(r.data['resumen']['PENDIENTE'], 1)
        self.assertEqual(r.data['resumen']['ACEPTADA'], 1)
        self.assertEqual(r.data['resultados'][0]['cliente_nombre'], 'Cliente')

    def test_filtra_por_estado(self):
        self.crear_solicitud()
        self.crear_solicitud(estado='ACEPTADA', hora=datetime.time(14, 0))
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url, {'estado': 'PENDIENTE'})
        self.assertEqual(len(r.data['resultados']), 1)
        self.assertEqual(self.client.get(self.url, {'estado': 'NOEXISTE'}).status_code, 400)

    def test_cliente_no_accede(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_requiere_autenticacion(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))


class HU19AgendaProveedorTests(BaseSolicitudesTest):
    url = '/api/solicitudes/agenda/'

    def test_agenda_solo_con_reservas_aceptadas_ordenadas(self):
        fecha = proximo_dia_habil()
        tarde = self.crear_solicitud(estado='ACEPTADA', hora=datetime.time(15, 0), fecha=fecha)
        manana = self.crear_solicitud(estado='ACEPTADA', hora=datetime.time(9, 0), fecha=fecha)
        self.crear_solicitud(estado='PENDIENTE', hora=datetime.time(12, 0), fecha=fecha)
        self.crear_solicitud(estado='CANCELADA', hora=datetime.time(13, 0), fecha=fecha)
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url, {'desde': fecha.isoformat(), 'hasta': fecha.isoformat()})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([x['id'] for x in r.data['reservas']], [manana.id, tarde.id])

    def test_agenda_no_incluye_reservas_de_otros_proveedores(self):
        fecha = proximo_dia_habil()
        self.crear_solicitud(estado='ACEPTADA', fecha=fecha, servicio=self.servicio2)
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url, {'desde': fecha.isoformat(), 'hasta': fecha.isoformat()})
        self.assertEqual(r.data['reservas'], [])

    def test_agenda_incluye_periodos_y_horario(self):
        fecha = proximo_dia_habil()
        PeriodoNoDisponible.objects.create(
            proveedor=self.proveedor, fecha_inicio=fecha, fecha_fin=fecha, motivo='Cita médica')
        DisponibilidadProveedor.objects.create(
            proveedor=self.proveedor, dia_semana=fecha.weekday(),
            hora_inicio=datetime.time(8, 0), hora_fin=datetime.time(12, 0))
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url, {'desde': fecha.isoformat(), 'hasta': fecha.isoformat()})
        self.assertEqual(r.data['periodos_no_disponibles'][0]['motivo'], 'Cita médica')
        self.assertEqual(r.data['horario_semanal'][0]['hora_fin'], '12:00')

    def test_rango_por_defecto_y_validaciones(self):
        self.client.force_authenticate(self.user_prov)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['desde'], timezone.localdate().isoformat())
        self.assertEqual(self.client.get(self.url, {'desde': '2026-01-10', 'hasta': '2026-01-01'}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'desde': '2026-01-01', 'hasta': '2027-01-01'}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'desde': 'hoy'}).status_code, 400)

    def test_cliente_no_accede_a_la_agenda(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_paginas_html_registradas(self):
        self.assertEqual(reverse('pagina-solicitudes-recibidas'), '/solicitudes-recibidas/')
        self.assertEqual(reverse('pagina-agenda'), '/agenda/')
