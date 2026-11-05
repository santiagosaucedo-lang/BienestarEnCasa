import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from usuarios.models import PerfilProveedor, PerfilUsuario
from .models import Categoria, Servicio

MEDIA_TEMP = tempfile.mkdtemp()


def crear_proveedor(username, nombre):
    usuario = get_user_model().objects.create_user(username=username, email=username, first_name=nombre, password='x')
    perfil = PerfilUsuario.objects.create(usuario=usuario, rol=PerfilUsuario.Rol.PROVEEDOR)
    return usuario, PerfilProveedor.objects.create(perfil_usuario=perfil, descripcion_profesional='-')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class HU08HU09Tests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TEMP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.dueno, proveedor = crear_proveedor('ana@x.com', 'Ana')
        self.ajeno, _ = crear_proveedor('beto@x.com', 'Beto')
        categoria = Categoria.objects.create(nombre='Masajes')
        self.servicio = Servicio.objects.create(
            proveedor=proveedor, categoria=categoria, nombre='Masaje relajante',
            descripcion='-', duracion_minutos=60, precio=50000,
        )

    def test_sin_token_401(self):
        self.assertEqual(self.client.get('/api/catalogo/servicios/').status_code, 401)

    def test_elemento_en_servicio_ajeno_403(self):
        self.client.force_authenticate(self.ajeno)
        datos = {'servicio': self.servicio.id, 'tipo': 'EQUIPO', 'nombre': 'Camilla'}
        self.assertEqual(self.client.post('/api/catalogo/elementos/', datos).status_code, 403)

    def test_multimedia_valida_extension(self):
        self.client.force_authenticate(self.dueno)
        video = SimpleUploadedFile('clip.mp4', b'x', content_type='video/mp4')
        respuesta = self.client.post(
            '/api/catalogo/multimedia/', {'servicio': self.servicio.id, 'tipo': 'FOTO', 'archivo': video}
        )
        self.assertEqual(respuesta.status_code, 400)
        foto = SimpleUploadedFile('foto.png', b'x', content_type='image/png')
        respuesta = self.client.post(
            '/api/catalogo/multimedia/', {'servicio': self.servicio.id, 'tipo': 'FOTO', 'archivo': foto}
        )
        self.assertEqual(respuesta.status_code, 201)

    def test_busqueda(self):
        self.client.force_authenticate(self.ajeno)
        proveedores = self.client.get('/api/proveedores/?search=Ana')
        self.assertEqual(proveedores.status_code, 200)
        self.assertEqual(proveedores.data[0]['nombres'], 'Ana')
        self.assertIn('servicios', proveedores.data[0])
        self.assertEqual(len(self.client.get('/api/catalogo/servicios/?search=Ana').data), 1)
        respuesta = self.client.get('/api/catalogo/servicios/?search=inexistente')
        self.assertEqual((respuesta.status_code, respuesta.data), (200, []))

    def test_proveedor_puede_actualizar_y_cambiar_estado_de_su_servicio(self):
        self.client.force_authenticate(self.dueno)
        respuesta = self.client.patch(
            f'/api/catalogo/servicios/{self.servicio.pk}/',
            {'nombre': 'Masaje actualizado', 'precio': '60000.00', 'estado': 'inactivo'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['estado'], 'INACTIVO')
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.nombre, 'Masaje actualizado')
        self.assertEqual(self.servicio.precio, 60000)

        reactivar = self.client.patch(
            f'/api/catalogo/servicios/{self.servicio.pk}/',
            {'estado': 'ACTIVO'},
            format='json',
        )
        self.assertEqual(reactivar.status_code, 200, reactivar.data)
        self.assertEqual(reactivar.data['estado'], 'ACTIVO')

    def test_perfil_proveedor_con_catalogo(self):
        self.client.force_authenticate(self.ajeno)
        respuesta = self.client.get(f'/api/proveedores/{self.servicio.proveedor_id}/')
        self.assertEqual(respuesta.data['servicios'][0]['nombre'], 'Masaje relajante')
        self.assertIn('elementos', respuesta.data['servicios'][0])
        self.assertEqual(respuesta.data['nombres'], 'Ana')

        publico = APIClient().get(f'/api/proveedores/{self.servicio.proveedor_id}/')
        self.assertEqual(publico.status_code, 200)
        self.assertIn('zonas_atencion', publico.data)
        self.assertIn('servicios', publico.data)


class CatalogoPaginasFrontendTests(TestCase):
    def test_paginas_de_gestion_catalogo_y_perfil_renderizan(self):
        rutas = (
            '/mis-servicios/',
            '/mis-servicios/nuevo/',
            '/mis-servicios/1/editar/',
            '/catalogo/',
            '/catalogo/1/',
            '/proveedor/1/',
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_base_template_no_incrusta_codigo_javascript(self):
        from pathlib import Path

        plantilla_base = Path(__file__).resolve().parents[2] / 'frontend' / 'templates' / 'base.html'
        contenido = plantilla_base.read_text(encoding='utf-8')
        self.assertNotIn('<script', contenido.lower())


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class FlujoCompletoURLsTests(APITestCase):
    """Recorre por HTTP todas las URLs de HU-08/HU-09 con login JWT real."""
    resultados = []

    @classmethod
    def tearDownClass(cls):
        print('\n| # | Actor | Método | URL | Esperado | Obtenido |')
        for i, fila in enumerate(cls.resultados, 1):
            print(f'| {i} | ' + ' | '.join(str(v) for v in fila) + ' |')
        super().tearDownClass()

    def llamar(self, actor, metodo, url, esperado, token=None, **kwargs):
        self.client.cookies.clear()
        if token:
            self.client.cookies['access'] = token  # el access viaja en cookie httponly
        respuesta = getattr(self.client, metodo)(url, **kwargs)
        self.resultados.append((actor, metodo.upper(), url, esperado, respuesta.status_code))
        self.assertEqual(respuesta.status_code, esperado, getattr(respuesta, 'data', None))
        return respuesta

    def registrar_y_login(self, email, nombre, rol):
        datos = {
            'nombres': nombre, 'apellidos': 'Prueba', 'email': email, 'rol': rol,
            'password': 'ClaveSegura123!', 'password_confirmacion': 'ClaveSegura123!',
        }
        self.llamar(nombre, 'post', '/api/auth/registro/', 201, data=datos, format='json')
        login = self.llamar(nombre, 'post', '/api/auth/iniciar-sesion/', 200,
                            data={'email': email, 'password': 'ClaveSegura123!'}, format='json')
        return login.cookies['access'].value

    def test_flujo_proveedor_cliente_y_anonimo(self):
        # Proveedor dueño arma su catálogo
        ana = self.registrar_y_login('ana@spa.com', 'Ana', 'PROVEEDOR')
        perfil = self.llamar('Ana', 'post', '/api/proveedores/mi-perfil/', 201, ana,
                             data={'descripcion_profesional': 'Masajista'}, format='json').data
        cat = self.llamar('Ana', 'post', '/api/catalogo/categorias/', 201, ana,
                          data={'nombre': 'Masajes'}, format='json').data['id']
        cat2 = self.llamar('Ana', 'post', '/api/catalogo/categorias/', 201, ana,
                           data={'nombre': 'Uñas'}, format='json').data['id']
        base = {'descripcion': '-', 'duracion_minutos': 60, 'precio': '50000.00'}
        srv = self.llamar('Ana', 'post', '/api/catalogo/servicios/', 201, ana,
                          data={**base, 'nombre': 'Masaje relajante', 'categoria': cat}, format='json').data['id']
        self.llamar('Ana', 'post', '/api/catalogo/servicios/', 201, ana,
                    data={**base, 'nombre': 'Manicure', 'categoria': cat2}, format='json')
        inactivo = self.llamar('Ana', 'post', '/api/catalogo/servicios/', 201, ana,
                               data={**base, 'nombre': 'Masaje piedras', 'categoria': cat, 'estado': 'INACTIVO'},
                               format='json').data['id']

        foto = SimpleUploadedFile('foto.png', b'x', content_type='image/png')
        media = self.llamar('Ana', 'post', '/api/catalogo/multimedia/', 201, ana,
                            data={'servicio': srv, 'tipo': 'FOTO', 'archivo': foto, 'descripcion': 'Sala'},
                            format='multipart').data['id']
        video = SimpleUploadedFile('clip.mp4', b'x', content_type='video/mp4')
        self.llamar('Ana', 'post', '/api/catalogo/multimedia/', 201, ana,
                    data={'servicio': srv, 'tipo': 'VIDEO', 'archivo': video}, format='multipart')
        malo = SimpleUploadedFile('clip.mp4', b'x', content_type='video/mp4')
        self.llamar('Ana', 'post', '/api/catalogo/multimedia/', 400, ana,
                    data={'servicio': srv, 'tipo': 'FOTO', 'archivo': malo}, format='multipart')
        self.llamar('Ana', 'patch', f'/api/catalogo/multimedia/{media}/', 200, ana,
                    data={'descripcion': 'Sala principal'}, format='json')
        self.llamar('Ana', 'patch', f'/api/catalogo/multimedia/{media}/', 400, ana,
                    data={'tipo': 'VIDEO'}, format='json')
        elem = self.llamar('Ana', 'post', '/api/catalogo/elementos/', 201, ana,
                           data={'servicio': srv, 'tipo': 'EQUIPO', 'nombre': 'Camilla', 'especificaciones': 'Plegable'},
                           format='json').data['id']
        borrar = self.llamar('Ana', 'post', '/api/catalogo/elementos/', 201, ana,
                             data={'servicio': srv, 'tipo': 'INSUMO', 'nombre': 'Aceite'}, format='json').data['id']
        self.llamar('Ana', 'post', '/api/catalogo/elementos/', 400, ana,
                    data={'servicio': srv, 'tipo': 'OTRO', 'nombre': 'X'}, format='json')
        self.llamar('Ana', 'put', f'/api/catalogo/elementos/{elem}/', 200, ana,
                    data={'servicio': srv, 'tipo': 'EQUIPO', 'nombre': 'Camilla', 'especificaciones': 'Fija'},
                    format='json')
        self.llamar('Ana', 'delete', f'/api/catalogo/elementos/{borrar}/', 204, ana)
        propios = self.llamar('Ana', 'get', '/api/catalogo/servicios/', 200, ana).data
        self.assertEqual(len(propios), 3)  # el dueño ve también su servicio inactivo

        # Otro proveedor no puede tocar el catálogo ajeno
        beto = self.registrar_y_login('beto@spa.com', 'Beto', 'PROVEEDOR')
        self.llamar('Beto', 'post', '/api/proveedores/mi-perfil/', 201, beto,
                    data={'descripcion_profesional': 'Estilista'}, format='json')
        self.llamar('Beto', 'post', '/api/catalogo/elementos/', 403, beto,
                    data={'servicio': srv, 'tipo': 'EQUIPO', 'nombre': 'Silla'}, format='json')
        foto2 = SimpleUploadedFile('f.jpg', b'x', content_type='image/jpeg')
        self.llamar('Beto', 'post', '/api/catalogo/multimedia/', 403, beto,
                    data={'servicio': srv, 'tipo': 'FOTO', 'archivo': foto2}, format='multipart')
        self.llamar('Beto', 'patch', f'/api/catalogo/multimedia/{media}/', 403, beto,
                    data={'descripcion': 'hack'}, format='json')
        self.llamar('Beto', 'delete', f'/api/catalogo/elementos/{elem}/', 403, beto)
        self.llamar('Beto', 'patch', f'/api/catalogo/servicios/{srv}/', 403, beto,
                    data={'precio': '1.00'}, format='json')
        self.llamar('Beto', 'get', f'/api/catalogo/servicios/{inactivo}/', 404, beto)

        # Cliente inicia sesión y consulta servicios
        cli = self.registrar_y_login('carla@correo.com', 'Carla', 'CLIENTE')
        lista = self.llamar('Carla', 'get', '/api/catalogo/servicios/', 200, cli).data
        self.assertEqual({s['nombre'] for s in lista}, {'Masaje relajante', 'Manicure'})
        detalle = self.llamar('Carla', 'get', f'/api/catalogo/servicios/{srv}/', 200, cli).data
        self.assertEqual(len(detalle['multimedia']), 2)
        self.assertEqual(detalle['elementos'][0]['especificaciones'], 'Fija')
        self.assertTrue(detalle['multimedia'][0]['archivo'].startswith('http://testserver/media/servicios/multimedia/'))
        self.llamar('Carla', 'get', f'/api/catalogo/servicios/{inactivo}/', 404, cli)
        por_nombre = self.llamar('Carla', 'get', '/api/catalogo/servicios/?search=masaje', 200, cli).data
        self.assertEqual([s['id'] for s in por_nombre], [srv])
        por_proveedor = self.llamar('Carla', 'get', '/api/catalogo/servicios/?search=Ana', 200, cli).data
        self.assertEqual(len(por_proveedor), 2)
        por_categoria = self.llamar('Carla', 'get', f'/api/catalogo/servicios/?categoria={cat2}', 200, cli).data
        self.assertEqual([s['nombre'] for s in por_categoria], ['Manicure'])
        combinado = self.llamar('Carla', 'get', f'/api/catalogo/servicios/?search=Ana&categoria={cat}', 200, cli).data
        self.assertEqual([s['id'] for s in combinado], [srv])
        vacio = self.llamar('Carla', 'get', '/api/catalogo/servicios/?search=yoga', 200, cli).data
        self.assertEqual(vacio, [])
        self.llamar('Carla', 'get', '/api/catalogo/servicios/?categoria=9999', 400, cli)
        self.assertEqual(len(self.llamar('Carla', 'get', f'/api/catalogo/multimedia/?servicio={srv}', 200, cli).data), 2)
        self.assertEqual(len(self.llamar('Carla', 'get', '/api/catalogo/elementos/', 200, cli).data), 1)
        self.llamar('Carla', 'get', f'/api/catalogo/elementos/{elem}/', 200, cli)
        publico = self.llamar('Carla', 'get', f"/api/proveedores/{perfil['id']}/", 200, cli).data
        self.assertEqual(publico['nombres'], 'Ana')
        self.assertEqual({s['nombre'] for s in publico['servicios']}, {'Masaje relajante', 'Manicure'})
        self.llamar('Carla', 'get', '/api/proveedores/9999/', 404, cli)
        self.llamar('Carla', 'post', '/api/catalogo/servicios/', 403, cli,
                    data={**base, 'nombre': 'X', 'categoria': cat}, format='json')
        self.llamar('Carla', 'post', '/api/catalogo/elementos/', 403, cli, data={}, format='json')
        self.llamar('Carla', 'post', '/api/catalogo/multimedia/', 403, cli, data={}, format='multipart')
        self.llamar('Carla', 'patch', f'/api/catalogo/servicios/{srv}/', 403, cli,
                    data={'precio': '1.00'}, format='json')
        self.llamar('Carla', 'delete', f'/api/catalogo/multimedia/{media}/', 403, cli)

        # Sin sesión
        for url in ('/api/catalogo/servicios/', f'/api/catalogo/servicios/{srv}/', '/api/catalogo/multimedia/',
                    '/api/catalogo/elementos/'):
            self.llamar('Anónimo', 'get', url, 401)
        self.llamar('Anónimo', 'get', f"/api/proveedores/{perfil['id']}/", 200)
        self.llamar('Anónimo', 'post', '/api/catalogo/elementos/', 401,
                    data={'servicio': srv, 'tipo': 'EQUIPO', 'nombre': 'X'}, format='json')
        self.llamar('Anónimo', 'get', '/api/catalogo/servicios/', 401, token='token-invalido')
