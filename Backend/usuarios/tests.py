from rest_framework import status
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from django.contrib.auth import get_user_model
from .models import PerfilUsuario
from usuarios.models import PerfilUsuario, Direccion 
from .models import PerfilProveedor, ZonaAtencion

Usuario = get_user_model()

class AutenticacionAPITest(APITestCase):
    datos_registro = {
        'nombres': 'Ana',
        'apellidos': 'Gomez',
        'email': 'ana@example.com',
        'password': 'ClaveSegura123!',
        'password_confirmacion': 'ClaveSegura123!',
        'rol': PerfilUsuario.Rol.CLIENTE,
        'telefono': '3001234567',
    }

    def test_registro_inicio_sesion_y_consulta_perfil(self):
        registro = self.client.post('/api/auth/registro/', self.datos_registro, format='json')
        self.assertEqual(registro.status_code, status.HTTP_201_CREATED)
        self.assertEqual(registro.data['rol'], PerfilUsuario.Rol.CLIENTE)

        inicio = self.client.post(
            '/api/auth/iniciar-sesion/',
            {'email': self.datos_registro['email'], 'password': self.datos_registro['password']},
            format='json',
        )
        self.assertEqual(inicio.status_code, status.HTTP_200_OK)
        # los tokens ya no viajan en el body (se revisa el JSON crudo que ve el navegador)
        self.assertNotIn(b'access', inicio.content)
        self.assertNotIn(b'refresh', inicio.content)
        self.assertTrue(inicio.cookies['access']['httponly'])
        self.assertTrue(inicio.cookies['refresh']['httponly'])

        perfil = self.client.get('/api/auth/mi-perfil/')  # el cliente de pruebas reenvia las cookies solo
        self.assertEqual(perfil.status_code, status.HTTP_200_OK)
        self.assertEqual(perfil.data['email'], self.datos_registro['email'])

        renovar = self.client.post('/api/auth/renovar-token/')
        self.assertEqual(renovar.status_code, status.HTTP_200_OK)
        self.assertIn('access', renovar.cookies)

        # con cookie de sesion, un PATCH sin token CSRF debe rechazarse
        sin_csrf = APIClient(enforce_csrf_checks=True)
        sin_csrf.cookies = self.client.cookies
        self.assertEqual(sin_csrf.patch('/api/auth/mi-perfil/', {}, format='json').status_code, status.HTTP_403_FORBIDDEN)

        salida = self.client.post('/api/auth/cerrar-sesion/')
        self.assertEqual(salida.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(salida.cookies['access'].value, '')
        self.assertEqual(self.client.get('/api/auth/mi-perfil/').status_code, status.HTTP_401_UNAUTHORIZED)



#Ejecución #001
#E1

    def test_registro_satisfactorio_como_cliente(self):
        """
        Escenario: Registro satisfactorio como Cliente, ingresando credenciales válidas.
        - Datos obligatorios completos
        - Formato válido
        - Contraseña válida según condiciones
        """
        datos_prueba_cliente = {
            'nombres': 'Carlos',
            'apellidos': 'Ramirez',
            'email': 'carlos.cliente@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3109876543',
        }

        # Simula la acción de "presionar registrar" enviando el payload al endpoint
        respuesta = self.client.post('/api/auth/registro/', datos_prueba_cliente, format='json')

        # Verificaciones esperadas para un registro exitoso
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['rol'], PerfilUsuario.Rol.CLIENTE)
        self.assertEqual(respuesta.data['email'], datos_prueba_cliente['email'])
        self.assertIn('id', respuesta.data) # Verifica que se haya generado y devuelto el identificador del usuario

#E2

    def test_registro_satisfactorio_como_proveedor(self):
        """
        Escenario: Registro satisfactorio como Proveedor, ingresando credenciales válidas.
        - Tipo de Usuario: Proveedor
        - Datos obligatorios completos
        - Formato válido
        - Contraseña válida según condiciones
        """
        datos_prueba_proveedor = {
            'nombres': 'Roberto',
            'apellidos': 'Fernandez',
            'email': 'roberto.proveedor@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.PROVEEDOR,
            'telefono': '3209876543',
        }

        # Simula la acción de "presionar registrar" enviando el payload al endpoint
        respuesta = self.client.post('/api/auth/registro/', datos_prueba_proveedor, format='json')

        # Verificaciones esperadas para un registro exitoso
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['rol'], PerfilUsuario.Rol.PROVEEDOR)
        self.assertEqual(respuesta.data['email'], datos_prueba_proveedor['email'])
        self.assertIn('id', respuesta.data)
        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#E3

    
    def test_registro_con_correo_invalido(self):
        """
        Escenario: Registro con correo electrónico inválido.
        """

        datos_prueba_correo_invalido = {
            'nombres': 'Laura',
            'apellidos': 'Martinez',
            'email': 'laura.martinez_sin_dominio.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3309876543',
        }

        respuesta = self.client.post(
            '/api/auth/registro/',
            datos_prueba_correo_invalido,
            format='json'
        )

        self.assertEqual(
            respuesta.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('email', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#E4

    def test_registro_con_datos_incompletos(self):
        """
        Escenario: Registro con datos obligatorios incompletos, omitiendo datos y presionando registrar.
        """

        datos_prueba_incompletos = {
            # Se omiten 'nombres' y 'email' intencionalmente
            'apellidos': 'Perez',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3409876543',
        }

        respuesta = self.client.post(
            '/api/auth/registro/',
            datos_prueba_incompletos,
            format='json'
        )

        self.assertEqual(
            respuesta.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('nombres', respuesta.data)
        self.assertIn('email', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#E5
    def test_registro_con_tipo_usuario_invalido(self):
        """
        Escenario: Selección del tipo de usuario, seleccionando un tipo no permitido.
        El sistema solo debe permitir las opciones "Cliente" y "Proveedor".
        """

        datos_prueba_rol_invalido = {
            'nombres': 'Diana',
            'apellidos': 'Rios',
            'email': 'diana.rios@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': 'ADMINISTRADOR', # Tipo de usuario no permitido o inexistente
            'telefono': '3509876543',
        }

        respuesta = self.client.post(
            '/api/auth/registro/',
            datos_prueba_rol_invalido,
            format='json'
        )

        self.assertEqual(
            respuesta.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        # Verifica que el error provenga específicamente de la validación del campo 'rol'
        self.assertIn('rol', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#E6
    def test_validacion_backend_datos_obligatorios(self):
        """
        Escenario: Validación de los datos recibidos, enviando una solicitud de registro.
        El backend debe validar los datos obligatorios y sus formatos y no depender 
        únicamente de las validaciones de la interfaz.
        """

        # Se envía un payload completamente vacío para simular una petición directa a la API
        # evadiendo cualquier validación de un formulario frontend
        datos_prueba_vacios = {}

        respuesta = self.client.post(
            '/api/auth/registro/',
            datos_prueba_vacios,
            format='json'
        )

        self.assertEqual(
            respuesta.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        
        # Se verifica que el backend responda con errores exigiendo cada campo obligatorio
        self.assertIn('nombres', respuesta.data)
        self.assertIn('apellidos', respuesta.data)
        self.assertIn('email', respuesta.data)
        self.assertIn('password', respuesta.data)
        self.assertIn('rol', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#HU-02
#E1
    def test_inicio_sesion_satisfactorio(self):
        """
        Escenario: Inicio de sesión satisfactorio, ingresando las credenciales y solicitando iniciar sesión.
        Precondiciones: El Cliente o Proveedor se encuentra registrado.
        """
        
        # 1. Precondición: Registrar al usuario en el sistema para poder iniciar sesión
        datos_registro = {
            'nombres': 'Alejandro',
            'apellidos': 'Marquez',
            'email': 'alejo@gmail.com',
            'password': 'Marquez93',
            'password_confirmacion': 'Marquez93',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3100000000',
        }
        self.client.post(
            '/api/auth/registro/', 
            datos_registro, 
            format='json'
        )

        # 2. Datos de prueba: Credenciales del usuario
        credenciales_login = {
            'email': 'alejo@gmail.com',
            'password': 'Marquez93'
        }

        # 3. Acción: Solicitando iniciar sesión
        respuesta = self.client.post(
            '/api/auth/iniciar-sesion/',
            credenciales_login,
            format='json'
        )

        # 4. Validaciones
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_200_OK
        )
        
        # Se verifica que por seguridad los tokens no vengan en el JSON
        self.assertNotIn(b'access', respuesta.content)
        self.assertNotIn(b'refresh', respuesta.content)
        
        # Se verifica que las cookies de sesión se hayan creado y sean HttpOnly
        self.assertTrue(respuesta.cookies['access']['httponly'])
        self.assertTrue(respuesta.cookies['refresh']['httponly'])

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("Cookies establecidas:", list(respuesta.cookies.keys()))
#E2
    def test_inicio_sesion_con_credenciales_incorrectas1(self):
        """
        Escenario: Rechazo de credenciales incorrectas, ingresando credenciales 
        incorrectas y solicitando iniciar sesión.
        """
        
        # 1. Precondición: Registrar al usuario en el sistema para evaluar el rechazo
        datos_registro = {
            'nombres': 'Alejandro',
            'apellidos': 'Marquez',
            'email': 'alejo@gmail.com',
            'password': 'Marquez93',
            'password_confirmacion': 'Marquez93',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3100000000',
        }
        self.client.post(
            '/api/auth/registro/', 
            datos_registro, 
            format='json'
        )

        # 2. Datos de prueba: Credenciales con contraseña incorrecta
        credenciales_incorrectas = {
            'email': 'alejo@gmail.com',
            'password': 'ClaveEquivocada2026'
        }

        # 3. Acción: Solicitando iniciar sesión
        respuesta = self.client.post(
            '/api/auth/iniciar-sesion/',
            credenciales_incorrectas,
            format='json'
        )

        # 4. Validaciones
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        
        
        self.assertIn('detail', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

    def test_inicio_sesion_con_credenciales_incorrectas2(self):
        """
        Escenario: Rechazo de credenciales incorrectas, ingresando credenciales 
        incorrectas y solicitando iniciar sesión.
        """
        
        # 1. Precondición: Registrar al usuario en el sistema para evaluar el rechazo
        datos_registro = {
            'nombres': 'Alejandro',
            'apellidos': 'Marquez',
            'email': 'alejo@gmail.com',
            'password': 'Marquez93',
            'password_confirmacion': 'Marquez93',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3100000000',
        }
        self.client.post(
            '/api/auth/registro/', 
            datos_registro, 
            format='json'
        )

        # 2. Datos de prueba: Credenciales con contraseña incorrecta
        credenciales_incorrectas = {
            'email': 'equivocado@gmail.com',
            'password': 'Marquez93'
        }

        # 3. Acción: Solicitando iniciar sesión
        respuesta = self.client.post(
            '/api/auth/iniciar-sesion/',
            credenciales_incorrectas,
            format='json'
        )

        # 4. Validaciones
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        
        # Verifica que el backend retorne un mensaje de error (usualmente bajo la llave 'detail' en DRF/SimpleJWT)
        self.assertIn('detail', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("HTML de respuesta:", respuesta.content.decode('utf-8'))

#E3
    def test_inicio_sesion_con_datos_incompletos(self):
        """
        Escenario: Validación de campos obligatorios, omitiendo datos y 
        solicitando iniciar sesión.
        El sistema no debe procesar satisfactoriamente la autenticación, 
        debe indicar los campos obligatorios pendientes y no debe crear 
        una sesión autenticada.
        """

        # Datos de prueba: Se envían credenciales vacías, omitiendo email y password
        credenciales_incompletas = {}

        # Acción: Solicitando iniciar sesión
        respuesta = self.client.post(
            '/api/auth/iniciar-sesion/',
            credenciales_incompletas,
            format='json'
        )

        # Validaciones: El backend debe rechazar la solicitud por validación (HTTP 400)
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        
        # Verifica que el sistema indica exactamente cuáles campos hacen falta
        self.assertIn('email', respuesta.data)
        self.assertIn('password', respuesta.data)

        # Verifica que NO se establecieron cookies de sesión (evitando la autenticación)
        self.assertNotIn('access', respuesta.cookies)
        self.assertNotIn('refresh', respuesta.cookies)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)
        print("Cookies establecidas:", list(respuesta.cookies.keys()))

#E4
    def test_autorizacion_funcionalidades_cliente(self):
        """
        Escenario: Autorización de funcionalidades para un Cliente.
        El sistema debe permitir la operación en funcionalidades de cliente 
        y debe impedir el acceso a las funcionalidades exclusivas del Proveedor.
        """
        
        # 1. Precondiciones: Registrar al usuario CLIENTE
        datos_cliente = {
            'nombres': 'Elena',
            'apellidos': 'Torres',
            'email': 'elena.cliente@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3201112233',
        }
        self.client.post('/api/auth/registro/', datos_cliente, format='json')

        # Iniciar sesión correctamente para obtener las cookies de autenticación
        self.client.post(
            '/api/auth/iniciar-sesion/',
            {'email': datos_cliente['email'], 'password': datos_cliente['password']},
            format='json'
        )

        # 2. Datos de prueba / Acción: Acceder a funcionalidad autorizada para clientes
        endpoint_cliente = '/api/usuarios/direcciones/' 
        respuesta_permitida = self.client.get(endpoint_cliente)

        # 3. Validación: El sistema permite la operación
        # (Se asume 200 OK, ajusta a 201 si es un POST según tu endpoint)
        self.assertEqual(
            respuesta_permitida.status_code,
            status.HTTP_200_OK
        )

        # 4. Acción: Intentar acceder a funcionalidad exclusiva de Proveedor
        
        endpoint_proveedor = '/api/proveedores/mis-zonas/'
        respuesta_denegada = self.client.get(endpoint_proveedor)

        # 5. Validación: El sistema impide el acceso por falta de permisos (403 Forbidden)
        self.assertEqual(
            respuesta_denegada.status_code,
            status.HTTP_403_FORBIDDEN
        )

        print("\n--- Resultado de la prueba ---")
        print(f"Estado HTTP (Acceso Cliente - {endpoint_cliente}):", respuesta_permitida.status_code)
        print(f"Estado HTTP (Acceso Proveedor - {endpoint_proveedor}):", respuesta_denegada.status_code)
        print("Mensaje del sistema (Rechazo):", respuesta_denegada.data)

#E5

    def test_autorizacion_funcionalidades_proveedor(self):
            """
            Escenario: Autorización de funcionalidades para un Proveedor.
            El sistema debe permitir la operación en funcionalidades de proveedor 
            y debe impedir el acceso a las funcionalidades exclusivas del Cliente.
            """
            
            # 1. Precondiciones: Registrar al usuario PROVEEDOR
            datos_proveedor = {
                'nombres': 'Jorge',
                'apellidos': 'Giraldo',
                'email': 'jorge.proveedor@example.com',
                'password': 'PasswordValida2026!',
                'password_confirmacion': 'PasswordValida2026!',
                'rol': PerfilUsuario.Rol.PROVEEDOR,
                'telefono': '3001122334',
            }
            self.client.post('/api/auth/registro/', datos_proveedor, format='json')

            # Iniciar sesión correctamente para obtener las cookies de autenticación
            self.client.post(
                '/api/auth/iniciar-sesion/',
                {'email': datos_proveedor['email'], 'password': datos_proveedor['password']},
                format='json'
            )

            # 2. Datos de prueba / Acción: Acceder a funcionalidad autorizada para proveedores
            endpoint_proveedor = '/api/proveedores/mis-zonas/'
            respuesta_permitida = self.client.get(endpoint_proveedor)

            # 3. Validación: El sistema permite la operación
            # (Se asume 200 OK, ajusta a 201 si es un POST según tu endpoint)
            self.assertEqual(
                respuesta_permitida.status_code,
                status.HTTP_200_OK
            )

            # 4. Acción: Intentar acceder a funcionalidad exclusiva de Cliente
            endpoint_cliente = '/api/usuarios/direcciones/' 
            respuesta_denegada = self.client.get(endpoint_cliente)

            # 5. Validación: El sistema impide el acceso por falta de permisos (403 Forbidden)
            self.assertEqual(
                respuesta_denegada.status_code,
                status.HTTP_403_FORBIDDEN
            )

            print("\n--- Resultado de la prueba ---")
            print(f"Estado HTTP (Acceso Proveedor - {endpoint_proveedor}):", respuesta_permitida.status_code)
            print(f"Estado HTTP (Acceso Cliente - {endpoint_cliente}):", respuesta_denegada.status_code)
            print("Mensaje del sistema (Rechazo):", respuesta_denegada.data)
#6
    def test_acceso_recurso_restringido_sin_autenticacion(self):
        """
        Escenario: Intento de acceso a un recurso restringido sin autenticación.
        El sistema debe denegar el acceso, no debe mostrar la información 
        protegida y debe solicitar que la persona inicie sesión.
        """
        
        # 1. Precondiciones: Asegurarnos de que no haya ninguna sesión activa
        # DRF APITestCase inicia sin autenticación por defecto, pero podemos 
        # limpiar las cookies por seguridad para representar explícitamente este estado
        self.client.cookies.clear()

        # 2. Datos de prueba / Acción: Intentar acceder a una funcionalidad restringida
        # Utilizaremos la ruta de direcciones de usuario que guardamos previamente
        endpoint_restringido = '/api/usuarios/direcciones/'
        
        respuesta = self.client.get(endpoint_restringido)

        # 3. Validación: El sistema deniega el acceso (401 Unauthorized)
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        
        # 4. Validación: El sistema responde con el mensaje estándar de DRF 
        # indicando que no se enviaron credenciales de autenticación
        self.assertIn('detail', respuesta.data)

        print("\n--- Resultado de la prueba ---")
        print(f"Estado HTTP (Intento de acceso a {endpoint_restringido}):", respuesta.status_code)
        print("Mensaje del sistema:", respuesta.data)

#E7

    def test_cierre_de_sesion_activa(self):
        """
        Escenario: Cierre de una sesión activa, seleccionando la opción de cerrar sesión.
        El sistema debe finalizar la sesión, invalidar el acceso previamente concedido 
        y requerir iniciar sesión nuevamente para acceder a recursos protegidos.
        """
        
        # 1. Precondiciones: Registrar un usuario e iniciar sesión para tener una sesión activa
        datos_usuario = {
            'nombres': 'Andres',
            'apellidos': 'Vargas',
            'email': 'andres.vargas@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3112223344',
        }
        
        self.client.post(
            '/api/auth/registro/', 
            datos_usuario, 
            format='json'
        )

        self.client.post(
            '/api/auth/iniciar-sesion/',
            {'email': datos_usuario['email'], 'password': datos_usuario['password']},
            format='json'
        )

        # 2. Acción: Seleccionando la opción de cerrar sesión (POST al endpoint de logout)
        respuesta_salida = self.client.post(
            '/api/auth/cerrar-sesion/',
            format='json'
        )

        # 3. Validación: El sistema debe finalizar la sesión (usualmente 204 No Content)
        self.assertEqual(
            respuesta_salida.status_code,
            status.HTTP_204_NO_CONTENT
        )
        
        # 4. Validación: El sistema invalida el acceso sobrescribiendo la cookie con un valor vacío
        self.assertEqual(
            respuesta_salida.cookies['access'].value, 
            ''
        )

        # 5. Validación: Se impide el acceso a funcionalidades protegidas exigiendo nuevo inicio de sesión
        respuesta_perfil = self.client.get('/api/auth/mi-perfil/')
        self.assertEqual(
            respuesta_perfil.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP (Cerrar sesión):", respuesta_salida.status_code)
        print("Valor cookie 'access' eliminada:", repr(respuesta_salida.cookies['access'].value))
        print("Estado HTTP (Intento acceso posterior):", respuesta_perfil.status_code)

#E8
    def test_acceso_recurso_despues_de_cerrar_sesion(self):
        """
        Escenario: Intento de acceso después de cerrar sesión, intentando acceder 
        a un recurso restringido sin autenticarse nuevamente.
        El sistema debe denegar el acceso, no debe mostrar información protegida 
        y debe solicitar un nuevo inicio de sesión.
        """
        
        # 1. Precondiciones: Registrar, iniciar sesión y luego cerrar sesión
        datos_usuario = {
            'nombres': 'Sofia',
            'apellidos': 'Gomez',
            'email': 'sofia.gomez@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3009998877',
        }
        
        self.client.post('/api/auth/registro/', datos_usuario, format='json')

        self.client.post(
            '/api/auth/iniciar-sesion/',
            {'email': datos_usuario['email'], 'password': datos_usuario['password']},
            format='json'
        )

        # Se ejecuta el cierre de sesión para dejar al usuario sin credenciales válidas
        self.client.post('/api/auth/cerrar-sesion/', format='json')

        # 2. Datos de prueba / Acción: Intentar acceder a un recurso restringido
        endpoint_restringido = '/api/usuarios/direcciones/'
        respuesta_denegada = self.client.get(endpoint_restringido)

        # 3. Validación: El sistema deniega el acceso (401 Unauthorized)
        self.assertEqual(
            respuesta_denegada.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        
        # 4. Validación: El sistema no muestra datos y envía el mensaje de autenticación requerida
        self.assertIn('detail', respuesta_denegada.data)

        print("\n--- Resultado de la prueba ---")
        print(f"Estado HTTP (Acceso posterior a cierre - {endpoint_restringido}):", respuesta_denegada.status_code)
        print("Mensaje del sistema:", respuesta_denegada.data)

#HU-03
#E1
    def test_solicitud_recuperacion_password_satisfactoria(self):
        """
        Escenario: Solicitud satisfactoria de recuperación, ingresando el 
        correo electrónico y solicitando recuperar su contraseña.
        El sistema debe iniciar el proceso, generar un código OTP o enlace 
        y enviarlo al correo electrónico registrado.
        """
        from django.core import mail  # Importación local para verificar la bandeja de salida

        # 1. Precondiciones: Registrar al usuario (Cliente o Proveedor)
        datos_usuario = {
            'nombres': 'Lucia',
            'apellidos': 'Mendez',
            'email': 'lucia.mendez@example.com',
            'password': 'PasswordValida2026!',
            'password_confirmacion': 'PasswordValida2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3001239988',
        }
        self.client.post('/api/auth/registro/', datos_usuario, format='json')

        # Limpiar la bandeja de salida de correos de prueba por precaución
        mail.outbox = []

        # 2. Datos de prueba / Acción: Enviar la solicitud de recuperación
        
        respuesta = self.client.post(
            '/recuperar-password/', 
            {'email': datos_usuario['email']}
        )

        # 3. Validación: La vista nativa de Django redirige (302) a la ruta de "enviado"
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_302_FOUND
        )

        # 4. Validación: El sistema generó y envió un correo electrónico
        self.assertEqual(len(mail.outbox), 1)
        
        # 5. Validación: El correo fue enviado al destinatario correcto
        correo_enviado = mail.outbox[0]
        self.assertEqual(correo_enviado.to, [datos_usuario['email']])
        
        # 6. Validación: El cuerpo del correo contiene la ruta base de restablecimiento 
        self.assertIn('restablecer', correo_enviado.body)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Redirige a:", respuesta.url)
        print("Correos enviados:", len(mail.outbox))
        if mail.outbox:
            print("Destinatario del correo:", correo_enviado.to)
            print("Asunto del correo:", correo_enviado.subject)
#E2
    def test_solicitud_recuperacion_correo_no_registrado(self):
        """
        Escenario: Solicitud mediante un correo no asociado a una cuenta, 
        proporcionando un correo electrónico y solicitando recuperar su contraseña.
        El sistema no debe iniciar un restablecimiento válido y debe presentar una 
        respuesta que no revele información sensible sobre las cuentas registradas.
        """
        from django.core import mail

        # 1. Precondiciones: Bandeja de salida limpia. No registramos ningún usuario.
        mail.outbox = []

        # 2. Datos de prueba / Acción: Enviar la solicitud con un correo inexistente
        correo_no_registrado = 'usuario_fantasma@example.com'
        
        respuesta = self.client.post(
            '/recuperar-password/', 
            {'email': correo_no_registrado}
        )

        # 3. Validación de Seguridad: Para evitar la enumeración de usuarios 
        # (revelar quién está registrado y quién no), la vista nativa de Django 
        # responde exactamente igual que si el correo existiera (redirige con 302).
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_302_FOUND
        )

        # 4. Validación Crucial: A pesar de simular éxito en la interfaz, 
        # internamente NO se debe haber generado ni enviado ningún correo.
        self.assertEqual(len(mail.outbox), 0)

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP (Simula éxito por seguridad):", respuesta.status_code)
        print("Redirige a:", respuesta.url)
        print("Correos enviados (debe ser 0):", len(mail.outbox))

#E3
    def test_validacion_satisfactoria_enlace_recuperacion(self):
        """
        Escenario: Validación satisfactoria del mecanismo de recuperación, 
        proporcionando el código correcto o utilizando el enlace válido.
        El sistema debe validar el mecanismo y debe permitir establecer una nueva contraseña.
        """
        from django.contrib.auth import get_user_model
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # 1. Precondiciones: Registrar al usuario a través de la API
        datos_usuario = {
            'nombres': 'Carlos',
            'apellidos': 'Recupera',
            'email': 'carlos.recupera@example.com',
            'password': 'PasswordVieja2026!',
            'password_confirmacion': 'PasswordVieja2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3109990000',
        }
        self.client.post('/api/auth/registro/', datos_usuario, format='json')

        # Obtenemos la instancia del usuario recién creado en la base de datos
        # (Necesario para generar el token nativo de Django)
        Usuario = get_user_model()
        usuario = Usuario.objects.get(email=datos_usuario['email'])

        # 2. Datos de prueba: Generar el uidb64 y un token VÁLIDO (simulando el link del correo)
        uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)

        # 3. Acción: El usuario "hace clic" en el enlace (petición GET al endpoint configurado)
        ruta_enlace = f'/restablecer/{uidb64}/{token}/'
        respuesta = self.client.get(ruta_enlace)

        # 4. Validación: El sistema acepta el token y muestra el formulario (HTTP 200 OK)
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_200_OK
        )

        # 5. Validación: Verificamos que la vista confirme que el enlace es válido.
        # (La vista nativa PasswordResetConfirmView de Django inyecta la variable 
        # 'validlink' en el contexto cuando el token pasa las pruebas de seguridad).
        self.assertTrue(respuesta.context['validlink'])

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP (Acceso al enlace):", respuesta.status_code)
        print("Ruta probada:", ruta_enlace)
        print("¿Enlace considerado válido por el sistema?:", respuesta.context['validlink'])

#E4
    def test_validacion_fallida_enlace_recuperacion(self):
        """
        Escenario: Uso de un mecanismo de recuperación inválido, proporcionando 
        un código OTP incorrecto o utilizando un enlace no válido.
        El sistema debe rechazar el mecanismo y no debe permitir establecer una nueva contraseña.
        """
        from django.contrib.auth import get_user_model
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # 1. Precondiciones: Registrar al usuario
        datos_usuario = {
            'nombres': 'Daniel',
            'apellidos': 'Prueba',
            'email': 'daniel.invalido@example.com',
            'password': 'PasswordVieja2026!',
            'password_confirmacion': 'PasswordVieja2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3200001111',
        }
        self.client.post('/api/auth/registro/', datos_usuario, format='json')

        Usuario = get_user_model()
        usuario = Usuario.objects.get(email=datos_usuario['email'])

        # 2. Datos de prueba: Generar el uidb64 correcto del usuario pero un token INVÁLIDO
        uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
        token_invalido = 'token-falso-e-invalido-123'

        # 3. Acción: Intentar acceder con el enlace manipulado/incorrecto
        ruta_enlace_invalido = f'/restablecer/{uidb64}/{token_invalido}/'
        respuesta = self.client.get(ruta_enlace_invalido)

        # 4. Validación: El sistema responde cargando la página HTML (200 OK)
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_200_OK,
            msg=f"Se esperaba 200, pero devolvió {respuesta.status_code}."
        )

        # 5. Validación Crucial: La vista nativa de Django detecta que el token 
        # no es válido y envía la variable 'validlink' como False al contexto. 
        # Esto hace que la plantilla HTML no muestre el formulario para cambiar 
        # la contraseña, sino un mensaje de error ("El enlace es inválido...").
        self.assertFalse(respuesta.context['validlink'])

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Ruta probada:", ruta_enlace_invalido)
        print("¿Enlace considerado válido por el sistema?:", respuesta.context['validlink'])

#E5
    def test_validacion_fallida_enlace_recuperacion_vencido(self):
        """
        Escenario: Uso de un mecanismo de recuperación vencido, intentando utilizar 
        el código OTP o enlace temporal.
        El sistema debe rechazar el restablecimiento y debe informar que el 
        mecanismo ya no es válido (enlace expirado).
        """
        from django.contrib.auth import get_user_model
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.test import override_settings # Importante para manipular el tiempo de vida del token

        # 1. Precondiciones: Registrar al usuario
        datos_usuario = {
            'nombres': 'Andrea',
            'apellidos': 'Tiempo',
            'email': 'andrea.tiempo@example.com',
            'password': 'PasswordVieja2026!',
            'password_confirmacion': 'PasswordVieja2026!',
            'rol': PerfilUsuario.Rol.CLIENTE,
            'telefono': '3300002222',
        }
        self.client.post('/api/auth/registro/', datos_usuario, format='json')

        Usuario = get_user_model()
        usuario = Usuario.objects.get(email=datos_usuario['email'])

        # 2. Datos de prueba: Generar el uidb64 y un token VÁLIDO generado AHORA mismo
        uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        ruta_enlace = f'/restablecer/{uidb64}/{token}/'

        # 3. Acción: Simulamos que el tiempo pasó. En lugar de detener el test por días, 
        # usamos 'override_settings' para decirle a Django que el tiempo de expiración 
        # (PASSWORD_RESET_TIMEOUT) sea -1 segundo. Esto hará que cualquier token 
        # nazca inmediatamente vencido.
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            respuesta = self.client.get(ruta_enlace)

        # 4. Validación: El sistema responde cargando la página HTML (200 OK)
        self.assertEqual(
            respuesta.status_code,
            status.HTTP_200_OK,
            msg=f"Se esperaba 200, pero devolvió {respuesta.status_code}."
        )

        # 5. Validación Crucial: La vista de Django analiza la marca de tiempo 
        # incrustada en el token, se da cuenta de que superó la vigencia y  
        # envía 'validlink' como False para que el HTML muestre el error de vencimiento.
        self.assertFalse(respuesta.context['validlink'])

        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP:", respuesta.status_code)
        print("Ruta probada:", ruta_enlace)
        print("¿Enlace vencido rechazado con éxito? (validlink = False):", not respuesta.context['validlink'])

#E6
#E7

#HU-04
#E1
class ConsultaPerfilClienteTests(APITestCase):
    def setUp(self):
        """
        Crea un usuario con rol CLIENTE, su PerfilUsuario y dos
        direcciones (una principal y una secundaria), para confirmar
        que el serializer selecciona la correcta.
        """
        self.url_mi_perfil = "/api/auth/mi-perfil/"
 
        self.usuario_cliente = Usuario.objects.create_user(
            username="cliente@test.com",
            email="cliente@test.com",
            password="ClaveSegura123!",
            first_name="Ana",
            last_name="Martínez",
        )
 
        self.perfil_cliente = PerfilUsuario.objects.create(
            usuario=self.usuario_cliente,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3001234567",
        )
 
        self.direccion_secundaria = Direccion.objects.create(
            usuario=self.usuario_cliente,
            direccion="Calle 10 # 20-30",
            ciudad="Cali",
            barrio="San Fernando",
            es_principal=False,
        )
 
        self.direccion_principal = Direccion.objects.create(
            usuario=self.usuario_cliente,
            direccion="Avenida Siempreviva # 7-42",
            ciudad="Cali",
            barrio="El Ingenio",
            complemento="Apto 301",
            es_principal=True,
        )
 
        # Se autentica directamente al cliente de pruebas para aislar este
        # escenario del flujo de login (ya cubierto en otro módulo).
        self.client.force_authenticate(user=self.usuario_cliente)
 
    def test_consulta_perfil_cliente_satisfactoria(self):
        """
        Un cliente autenticado debe recibir sus datos personales
        junto con el objeto completo de su dirección principal.
        """
        response = self.client.get(self.url_mi_perfil)
 
        data = response.json()
        direccion = data.get("direccion_principal")
 
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            data.get("email"),
            "cliente@test.com",
        )
        self.assertEqual(
            data.get("nombres"),
            "Ana",
        )
        self.assertEqual(
            data.get("apellidos"),
            "Martínez",
        )
        self.assertEqual(
            data.get("rol"),
            PerfilUsuario.Rol.CLIENTE,
        )
        self.assertIsNotNone(
            direccion,
            msg="Se esperaba el objeto direccion_principal en el JSON",
        )
        self.assertEqual(
            direccion.get("direccion"),
            "Avenida Siempreviva # 7-42",
        )
        self.assertEqual(
            direccion.get("barrio"),
            "El Ingenio",
        )
        self.assertTrue(
            direccion.get("es_principal"),
        )
 
        print(
            "\n[test_consulta_perfil_cliente_satisfactoria]",
            "\nStatus:", response.status_code,
            "\nDatos personales:", {
                "email": data.get("email"),
                "nombres": data.get("nombres"),
                "apellidos": data.get("apellidos"),
                "rol": data.get("rol"),
            },
            "\ndireccion_principal:", direccion,
        )

#E2
class actualizarPerfilClienteTest(APITestCase):
    def setUp(self):
            """
            Crea un usuario con rol CLIENTE, su PerfilUsuario y dos
            direcciones (una principal y una secundaria), para confirmar
            que el serializer selecciona la correcta.
            """
            self.url_mi_perfil = "/api/auth/mi-perfil/"
     
            self.usuario_cliente = Usuario.objects.create_user(
                username="cliente@test.com",
                email="cliente@test.com",
                password="ClaveSegura123!",
                first_name="Ana",
                last_name="Martínez",
            )
     
            self.perfil_cliente = PerfilUsuario.objects.create(
                usuario=self.usuario_cliente,
                rol=PerfilUsuario.Rol.CLIENTE,
                telefono="3001234567",
            )
     
            self.direccion_secundaria = Direccion.objects.create(
                usuario=self.usuario_cliente,
                direccion="Calle 10 # 20-30",
                ciudad="Cali",
                barrio="San Fernando",
                es_principal=False,
            )
     
            self.direccion_principal = Direccion.objects.create(
                usuario=self.usuario_cliente,
                direccion="Avenida Siempreviva # 7-42",
                ciudad="Cali",
                barrio="El Ingenio",
                complemento="Apto 301",
                es_principal=True,
            )
     
            # Se autentica directamente al cliente de pruebas para aislar este
            # escenario del flujo de login (ya cubierto en otro módulo).
            self.client.force_authenticate(user=self.usuario_cliente)
    def test_actualizacion_perfil_cliente_satisfactoria(self):
        """
        Escenario: Actualización satisfactoria de datos personales, modificando 
        datos permitidos de su perfil con información válida.
        El sistema debe guardar los cambios y debe mostrar la información 
        actualizada en consultas posteriores.
        """
        
        # Datos de prueba: Nueva información válida para los campos permitidos
        # (Modificaremos el nombre y el teléfono, dejando intacto el apellido)
        datos_actualizados = {
            'nombres': 'Ana Maria',
            'telefono': '3229998877'
        }

        # Acción 1: Enviar petición PATCH para actualizar el perfil
        respuesta_patch = self.client.patch(
            self.url_mi_perfil,
            datos_actualizados,
            format='json'
        )

        # Validación 1: El sistema guarda los cambios y responde exitosamente (HTTP 200 OK)
        self.assertEqual(
            respuesta_patch.status_code,
            status.HTTP_200_OK,
            msg=f"Falló la actualización. Respuesta: {respuesta_patch.data}"
        )

        # Acción 2: Consultar nuevamente el perfil para verificar persistencia real
        respuesta_get = self.client.get(self.url_mi_perfil)
        datos_consultados = respuesta_get.data

        # Validación 2: El sistema muestra la información actualizada
        self.assertEqual(
            datos_consultados.get('nombres'),
            datos_actualizados['nombres']
        )
        self.assertEqual(
            datos_consultados.get('telefono'),
            datos_actualizados['telefono']
        )
        
        # Validación 3: Confirmamos que los campos NO enviados (apellidos) no se alteraron
        self.assertEqual(
            datos_consultados.get('apellidos'),
            "Martínez"
        )

        # Bloque de depuración
        print("\n--- Resultado de la prueba ---")
        print("Estado HTTP (PATCH Actualización):", respuesta_patch.status_code)
        print("Estado HTTP (GET Consulta posterior):", respuesta_get.status_code)
        print("Datos modificados enviados:", datos_actualizados)
        print("Datos del perfil en base de datos tras actualizar:", {
            "nombres": datos_consultados.get('nombres'),
            "apellidos": datos_consultados.get('apellidos'),
            "telefono": datos_consultados.get('telefono')
        })

class actualizarDireccionClienteTest(APITestCase):
    def setUp(self):
        """
        Crea un usuario CLIENTE autenticado, listo para registrar
        una nueva dirección principal.
        """
        self.url_direcciones = "/api/usuarios/direcciones/"

        self.usuario_cliente = Usuario.objects.create_user(
            username="cliente_dir@test.com",
            email="cliente_dir@test.com",
            password="ClaveSegura123!",
            first_name="Carlos",
            last_name="Gómez",
        )

        self.perfil_cliente = PerfilUsuario.objects.create(
            usuario=self.usuario_cliente,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3001234567",
        )

        self.client.force_authenticate(user=self.usuario_cliente)

        
        self.nueva_direccion_principal = {
            "direccion": "Calle 5 # 40-100", 
            "ciudad": "Cali",
            "barrio": "Tequendama",
            "es_principal": True,
            "complemento": "Casa esquinera"
        }

    def test_actualizacion_nueva_direccion_principal_satisfactoria(self):
        """
        Un POST a las direcciones del usuario con es_principal=True 
        debe guardarse correctamente apuntando al Usuario directamente.
        """
        response = self.client.post(
            self.url_direcciones,
            data=self.nueva_direccion_principal,
            format="json",
        )

        data_response = response.json()

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg="El endpoint debe retornar 201 Created al guardar la nueva dirección.",
        )
        self.assertEqual(
            data_response.get("direccion"),
            "Calle 5 # 40-100",
        )
        self.assertTrue(
            data_response.get("es_principal"),
            msg="La respuesta JSON debe indicar que es la dirección principal.",
        )

        #Buscamos la relación desde el Usuario
        direccion_db = self.usuario_cliente.direcciones.filter(
            es_principal=True
        ).first()

        self.assertIsNotNone(
            direccion_db,
            msg="La nueva dirección principal debe existir en la BD relacionada al usuario.",
        )
        self.assertEqual(
            direccion_db.direccion,
            "Calle 5 # 40-100",
        )
        self.assertEqual(
            direccion_db.complemento,
            "Casa esquinera",
        )

        print(
            "\n[test_actualizacion_nueva_direccion_principal_satisfactoria]",
            "\nStatus HTTP POST:", response.status_code,
            "\nDatos devueltos por la API:", data_response,
            "\nDirección guardada (Usuario BD):", direccion_db.direccion if direccion_db else None,
            "\nComplemento en BD:", direccion_db.complemento if direccion_db else None,
            "\nEs principal en BD:", direccion_db.es_principal if direccion_db else None,
        )

#E4
class actualizarDireccionFallida(APITestCase):
    def setUp(self):
        """
        Crea un usuario CLIENTE autenticado con datos iniciales completos.
        """
        self.url_mi_perfil = "/api/auth/mi-perfil/"

        self.usuario_cliente = Usuario.objects.create_user(
            username="cliente_original@test.com",
            email="cliente_original@test.com",
            password="ClaveSegura123!",
            first_name="Roberto",
            last_name="García",
        )

        self.perfil_cliente = PerfilUsuario.objects.create(
            usuario=self.usuario_cliente,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3001234567",
        )

        self.client.force_authenticate(user=self.usuario_cliente)

        # Simulamos que el usuario borra/omite su nombre y su email (campos requeridos)
        self.datos_incompletos = {
            "nombres": "",
            "apellidos": "García",
            "email": "", 
            "telefono": "3001234567"
        }

    def test_actualizacion_rechazada_por_datos_incompletos(self):
        """
        Un PATCH enviando valores vacíos en campos obligatorios debe devolver 400,
        señalar el error en dichos campos, y no modificar los datos previos en BD.
        """
        response = self.client.patch(
            self.url_mi_perfil,
            data=self.datos_incompletos,
            format="json",
        )

        data_response = response.json()

        # 1. Verifica el rechazo de la actualización
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            msg="El endpoint debe retornar 400 Bad Request al omitir campos obligatorios.",
        )

        # 2. Verifica que se indiquen los campos pendientes/inválidos
        self.assertIn(
            "nombres",
            data_response,
            msg="El JSON de error debe indicar que 'nombres' falló o es requerido.",
        )
        self.assertIn(
            "email",
            data_response,
            msg="El JSON de error debe indicar que 'email' falló o es requerido.",
        )

        # 3. Verifica que la información previa se conserve (sin cambios)
        self.usuario_cliente.refresh_from_db()
        self.perfil_cliente.refresh_from_db()

        self.assertEqual(
            self.usuario_cliente.first_name,
            "Roberto",
            msg="El nombre original debe conservarse en la base de datos.",
        )
        self.assertEqual(
            self.usuario_cliente.email,
            "cliente_original@test.com",
            msg="El email original debe conservarse en la base de datos.",
        )

        print(
            "\n[test_actualizacion_rechazada_por_datos_incompletos]",
            "\nStatus HTTP PATCH:", response.status_code,
            "\nErrores indicados por la API:", data_response,
            "\nNombre conservado en BD:", self.usuario_cliente.first_name,
            "\nEmail conservado en BD:", self.usuario_cliente.email,
        )

#E5
class actulizarDirreccionFallida2(APITestCase):
    def setUp(self):
        """
        Crea un usuario CLIENTE autenticado con datos iniciales válidos.
        """
        self.url_mi_perfil = "/api/auth/mi-perfil/"

        self.usuario_cliente = Usuario.objects.create_user(
            username="cliente_valido@test.com",
            email="cliente_valido@test.com",
            password="ClaveSegura123!",
            first_name="Luis",
            last_name="Fernández",
        )

        self.perfil_cliente = PerfilUsuario.objects.create(
            usuario=self.usuario_cliente,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3001234567",
        )

        self.client.force_authenticate(user=self.usuario_cliente)

        # Datos que violan las validaciones de los serializadores/modelos
        self.datos_invalidos = {
            "nombres": "Luis Modificado",
            "apellidos": "Fernández",
            "email": "esto_no_es_un_correo",  # Formato inválido
            "telefono": "123456789012345678901"  # Excede max_length=20
        }

    def test_actualizacion_rechazada_por_datos_invalidos(self):
        """
        Un PATCH con datos mal formateados debe devolver 400, mostrar 
        el detalle de los errores y no guardar nada en la base de datos.
        """
        response = self.client.patch(
            self.url_mi_perfil,
            data=self.datos_invalidos,
            format="json",
        )

        data_response = response.json()

        # 1. Verifica el rechazo por formato inválido
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            msg="El endpoint debe retornar 400 Bad Request al enviar datos inválidos.",
        )

        # 2. Verifica que se indiquen los campos con errores de validación
        self.assertIn(
            "email",
            data_response,
            msg="El JSON de error debe indicar que 'email' no tiene un formato válido.",
        )
        self.assertIn(
            "telefono",
            data_response,
            msg="El JSON de error debe indicar que 'telefono' falló su validación de longitud.",
        )

        # 3. Verifica que la información previa se conserve intacta
        self.usuario_cliente.refresh_from_db()
        self.perfil_cliente.refresh_from_db()

        self.assertEqual(
            self.usuario_cliente.first_name,
            "Luis",
            msg="El nombre no debió actualizarse porque la petición completa fue rechazada.",
        )
        self.assertEqual(
            self.usuario_cliente.email,
            "cliente_valido@test.com",
            msg="El email original debe conservarse intacto.",
        )
        self.assertEqual(
            self.perfil_cliente.telefono,
            "3001234567",
            msg="El teléfono original debe conservarse intacto.",
        )

        print(
            "\n[test_actualizacion_rechazada_por_datos_invalidos]",
            "\nStatus HTTP PATCH:", response.status_code,
            "\nErrores de validación devueltos:", data_response,
            "\nNombre conservado en BD:", self.usuario_cliente.first_name,
            "\nEmail conservado en BD:", self.usuario_cliente.email,
            "\nTeléfono conservado en BD:", self.perfil_cliente.telefono,
        )

class consultarPerfilFallido(APITestCase):
    def setUp(self):
        """
        Crea dos usuarios CLIENTE. Autentica al primero e intenta
        operar sobre la URL del segundo.
        """
        # 1. Creación del cliente activo (el atacante/intruso)
        self.usuario_activo = Usuario.objects.create_user(
            username="cliente_activo@test.com",
            email="cliente_activo@test.com",
            password="ClaveSegura123!",
            first_name="Andrés",
            last_name="Pérez",
        )
        self.perfil_activo = PerfilUsuario.objects.create(
            usuario=self.usuario_activo,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3000000001",
        )

        # 2. Creación del cliente ajeno (la víctima)
        self.usuario_ajeno = Usuario.objects.create_user(
            username="cliente_ajeno@test.com",
            email="cliente_ajeno@test.com",
            password="ClaveSegura123!",
            first_name="Camilo",
            last_name="Sánchez",
        )
        self.perfil_ajeno = PerfilUsuario.objects.create(
            usuario=self.usuario_ajeno,
            rol=PerfilUsuario.Rol.CLIENTE,
            telefono="3000000002",
        )

        # Autenticamos al cliente activo
        self.client.force_authenticate(user=self.usuario_activo)

        # URL dinámica apuntando al recurso del usuario ajeno
        # Ajusta "usuarios-detail" o la estructura según el nombre de tus rutas
        self.url_ajena = f"/api/usuarios/{self.usuario_ajeno.id}/"

        self.datos_maliciosos = {
            "nombres": "Hackeado",
            "telefono": "9999999999"
        }

    def test_consulta_y_modificacion_perfil_ajeno_denegada(self):
        """
        Un cliente autenticado no debe poder hacer GET ni PATCH 
        en el perfil de otro cliente.
        """
        # --- 1. Intento de Consulta (GET) ---
        response_get = self.client.get(self.url_ajena)
        
        # Dependiendo de si filtras el queryset o usas permisos, DRF retorna 403 o 404.
        # Validamos que NO sea un 200 OK.
        self.assertNotEqual(
            response_get.status_code,
            status.HTTP_200_OK,
            msg="El sistema no debe permitir la consulta de un perfil ajeno (esperado 403 o 404).",
        )

        # --- 2. Intento de Modificación (PATCH) ---
        response_patch = self.client.patch(
            self.url_ajena,
            data=self.datos_maliciosos,
            format="json",
        )

        self.assertNotEqual(
            response_patch.status_code,
            status.HTTP_200_OK,
            msg="El sistema no debe permitir modificar un perfil ajeno (esperado 403 o 404).",
        )

        # --- 3. Verificación de Inmutabilidad ---
        self.usuario_ajeno.refresh_from_db()
        self.perfil_ajeno.refresh_from_db()

        self.assertEqual(
            self.usuario_ajeno.first_name,
            "Camilo",
            msg="El nombre del perfil ajeno debió conservarse intacto.",
        )
        self.assertEqual(
            self.perfil_ajeno.telefono,
            "3000000002",
            msg="El teléfono del perfil ajeno debió conservarse intacto.",
        )

        print(
            "\n[test_consulta_y_modificacion_perfil_ajeno_denegada]",
            "\nStatus HTTP GET (Consulta):", response_get.status_code,
            "\nStatus HTTP PATCH (Modificación):", response_patch.status_code,
            "\nNombre real conservado BD:", self.usuario_ajeno.first_name,
            "\nTeléfono real conservado BD:", self.perfil_ajeno.telefono,
        )

#HU-05
#E1
class ConsultaPerfilProfesionalTests(APITestCase):

    def setUp(self):
        """
        Crea un usuario PROVEEDOR autenticado, con su información 
        profesional y zonas de atención pre-cargadas en la base de datos.
        """
        self.url_perfil_profesional = "/api/proveedores/mi-perfil/"

        # 1. Creación del Usuario y Perfil base
        self.usuario_proveedor = Usuario.objects.create_user(
            username="proveedor@test.com",
            email="proveedor@test.com",
            password="ClaveSegura123!",
            first_name="Javier",
            last_name="Ramírez",
        )

        self.perfil_base = PerfilUsuario.objects.create(
            usuario=self.usuario_proveedor,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3150001122",
        )

        # 2. Creación de la Información Profesional
        self.perfil_proveedor = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base,
            descripcion_profesional="Fisioterapia a domicilio",
        )

        # 3. Creación de las Zonas de Atención (ajustado a barrio_sector y perfil_proveedor)
        ZonaAtencion.objects.create(
            perfil_proveedor=self.perfil_proveedor,
            ciudad="Cali",
            barrio_sector="Norte",
        )
        ZonaAtencion.objects.create(
            perfil_proveedor=self.perfil_proveedor,
            ciudad="Cali",
            barrio_sector="Sur",
        )

        # Autenticación del proveedor
        self.client.force_authenticate(user=self.usuario_proveedor)

    def test_consulta_perfil_profesional_satisfactoria(self):
        """
        Un GET al endpoint del perfil profesional debe devolver la data
        del proveedor, incluyendo un arreglo anidado con sus zonas de atención.
        """
        response = self.client.get(self.url_perfil_profesional)
        data_response = response.json()

        # 1. Validación de estado HTTP
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg="El endpoint debe retornar 200 OK al consultar el perfil profesional propio.",
        )

        # 2. Validación de la información profesional básica
        self.assertEqual(
            data_response.get("descripcion_profesional"),
            "Fisioterapia a domicilio",
            msg="El JSON debe contener la descripcion_profesional correcta.",
        )

        # 3. Validación de las zonas de atención anidadas
        zonas = data_response.get("zonas_atencion", [])
        
        self.assertIsInstance(
            zonas,
            list,
            msg="Las zonas de atención deben devolverse como una lista (array).",
        )
        self.assertEqual(
            len(zonas), 2,
            
            msg="El sistema debe devolver exactamente las 2 zonas registradas.",
        )
        
        # Verificamos el contenido de al menos una zona para asegurar correcta serialización
        ciudades_zonas = [z.get("ciudad") for z in zonas if isinstance(z, dict)]
        barrios_zonas = [z.get("barrio_sector") for z in zonas if isinstance(z, dict)]
        
        self.assertIn(
            "Cali",
            ciudades_zonas,
            msg="La ciudad 'Cali' debe estar presente en los objetos de zonas_atencion.",
        )
        self.assertIn(
            "Norte",
            barrios_zonas,
            msg="El barrio_sector 'Norte' debe estar presente en los objetos de zonas_atencion.",
        )

        print(
            "\n[test_consulta_perfil_profesional_satisfactoria]",
            "\nStatus HTTP GET:", response.status_code,
            "\nDescripción profesional devuelta:", data_response.get("descripcion_profesional"),
            "\nZonas de atención encontradas:", len(zonas),
            "\nEstructura de las zonas devueltas:", zonas,
        )
#E2
class ActualizacionPerfilProfesionalTests(APITestCase):

    def setUp(self):
        """
        Crea un usuario PROVEEDOR autenticado, listo para recibir un PATCH
        sobre su perfil profesional.
        """
        self.url_perfil_profesional = "/api/proveedores/mi-perfil/"

        self.usuario_proveedor = Usuario.objects.create_user(
            username="proveedor_act@test.com",
            email="proveedor_act@test.com",
            password="ClaveSegura123!",
            first_name="Laura",
            last_name="Gómez",
        )

        self.perfil_base = PerfilUsuario.objects.create(
            usuario=self.usuario_proveedor,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3201234567",
        )

        self.perfil_proveedor = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base,
            descripcion_profesional="Servicios generales de enfermería.",
        )

        self.client.force_authenticate(user=self.usuario_proveedor)

        self.datos_actualizados = {
            "descripcion_profesional": "Enfermera especialista en cuidados intensivos a domicilio.",
        }

    def test_actualizacion_perfil_profesional_satisfactoria(self):
        """
        Un PATCH con datos válidos sobre la descripción profesional debe 
        guardarse correctamente, y un GET posterior debe reflejar los cambios.
        """
        # 1. Ejecutar la actualización (PATCH)
        response_patch = self.client.patch(
            self.url_perfil_profesional,
            data=self.datos_actualizados,
            format="json",
        )

        data_patch = response_patch.json()

        self.assertEqual(
            response_patch.status_code,
            status.HTTP_200_OK,
            msg="El endpoint debe retornar 200 OK al actualizar correctamente.",
        )
        self.assertEqual(
            data_patch.get("descripcion_profesional"),
            "Enfermera especialista en cuidados intensivos a domicilio.",
        )

        # 2. Verificar la persistencia con una consulta posterior (GET)
        response_get = self.client.get(self.url_perfil_profesional)
        data_get = response_get.json()

        self.assertEqual(
            response_get.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            data_get.get("descripcion_profesional"),
            "Enfermera especialista en cuidados intensivos a domicilio.",
            msg="El GET posterior debe devolver la descripción actualizada.",
        )

        # 3. Verificar directamente en la base de datos
        self.perfil_proveedor.refresh_from_db()

        self.assertEqual(
            self.perfil_proveedor.descripcion_profesional,
            "Enfermera especialista en cuidados intensivos a domicilio.",
            msg="La descripción profesional debe haberse guardado en la base de datos.",
        )

        print(
            "\n[test_actualizacion_perfil_profesional_satisfactoria]",
            "\nStatus PATCH:", response_patch.status_code,
            "\nDescripción devuelta en PATCH:", data_patch.get("descripcion_profesional"),
            "\nStatus GET posterior:", response_get.status_code,
            "\nDescripción devuelta en GET:", data_get.get("descripcion_profesional"),
            "\nDescripción en BD:", self.perfil_proveedor.descripcion_profesional,
        )
#E3
class RegistroZonasAtencionTests(APITestCase):

    def setUp(self):
        """
        Crea un usuario PROVEEDOR autenticado y su perfil base y profesional,
        listo para registrar nuevas zonas de atención.
        """
        # Ajusta esta URL a la ruta real de tu API para gestionar zonas
        self.url_zonas = "/api/proveedores/mis-zonas/"

        # 1. Creación del Usuario y Perfiles
        self.usuario_proveedor = Usuario.objects.create_user(
            username="proveedor_zonas@test.com",
            email="proveedor_zonas@test.com",
            password="ClaveSegura123!",
            first_name="Diana",
            last_name="Ríos",
        )

        self.perfil_base = PerfilUsuario.objects.create(
            usuario=self.usuario_proveedor,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3009998877",
        )

        self.perfil_proveedor = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base,
            descripcion_profesional="Terapia ocupacional infantil.",
        )

        # 2. Autenticación
        self.client.force_authenticate(user=self.usuario_proveedor)

        # 3. Datos de prueba: Zonas a registrar
        self.zona_1 = {
            "ciudad": "Cali",
            "barrio_sector": "Ciudad Jardín"
        }
        self.zona_2 = {
            "ciudad": "Palmira",
            "barrio_sector": "Centro"
        }

    def test_registro_zonas_atencion_satisfactorio(self):
        """
        Un POST al endpoint de zonas con datos válidos debe registrar 
        la nueva zona asociándola automáticamente al perfil del proveedor autenticado.
        """
        # --- 1. Registrar la primera zona ---
        response_zona_1 = self.client.post(
            self.url_zonas,
            data=self.zona_1,
            format="json",
        )

        self.assertEqual(
            response_zona_1.status_code,
            status.HTTP_201_CREATED,
            msg="El endpoint debe retornar 201 Created al registrar la primera zona.",
        )

        # --- 2. Registrar la segunda zona (demostrando "una o más") ---
        response_zona_2 = self.client.post(
            self.url_zonas,
            data=self.zona_2,
            format="json",
        )

        self.assertEqual(
            response_zona_2.status_code,
            status.HTTP_201_CREATED,
            msg="El endpoint debe retornar 201 Created al registrar una zona adicional.",
        )

        # --- 3. Verificación de persistencia y asociación en BD ---
        # Consultamos las zonas directamente asociadas a este perfil
        zonas_en_bd = ZonaAtencion.objects.filter(perfil_proveedor=self.perfil_proveedor)
        
        self.assertEqual(
            zonas_en_bd.count(),
            2,
            msg="El sistema debe conservar las 2 zonas registradas asociadas al perfil profesional.",
        )

        # Verificamos que los datos guarden coherencia
        ciudades_registradas = list(zonas_en_bd.values_list("ciudad", flat=True))
        barrios_registrados = list(zonas_en_bd.values_list("barrio_sector", flat=True))

        self.assertIn("Cali", ciudades_registradas)
        self.assertIn("Palmira", ciudades_registradas)
        self.assertIn("Ciudad Jardín", barrios_registrados)
        self.assertIn("Centro", barrios_registrados)

        print(
            "\n[test_registro_zonas_atencion_satisfactorio]",
            "\nStatus HTTP Zona 1:", response_zona_1.status_code,
            "\nStatus HTTP Zona 2:", response_zona_2.status_code,
            "\nDatos devueltos Zona 1:", response_zona_1.json(),
            "\nTotal zonas en BD para el proveedor:", zonas_en_bd.count(),
            "\nCiudades guardadas:", ciudades_registradas,
            "\nBarrios/Sectores guardados:", barrios_registrados,
        )

#E4
class ZonasAtencionInformativasTests(APITestCase):

    def setUp(self):
        """
        Crea un usuario PROVEEDOR autenticado con zonas de atención base.
        """
        # Endpoint donde se consultan los datos del perfil y sus zonas
        self.url_perfil_profesional = "/api/proveedores/mi-perfil/"

        self.usuario_proveedor = Usuario.objects.create_user(
            username="proveedor_info@test.com",
            email="proveedor_info@test.com",
            password="ClaveSegura123!",
            first_name="Héctor",
            last_name="Vargas",
        )

        self.perfil_base = PerfilUsuario.objects.create(
            usuario=self.usuario_proveedor,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3001112233",
        )

        self.perfil_proveedor = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base,
            descripcion_profesional="Servicios de plomería general.",
        )

        # Registramos un par de zonas informativas
        ZonaAtencion.objects.create(
            perfil_proveedor=self.perfil_proveedor,
            ciudad="Cali",
            barrio_sector="San Fernando",
        )
        ZonaAtencion.objects.create(
            perfil_proveedor=self.perfil_proveedor,
            ciudad="Palmira",
            barrio_sector="Centro",
        )

        self.client.force_authenticate(user=self.usuario_proveedor)

    def test_consulta_zonas_puramente_informativas(self):
        """
        Al consultar las zonas, el payload JSON debe contener únicamente
        los datos de texto registrados, sin campos de cálculo geográfico.
        """
        response = self.client.get(self.url_perfil_profesional)
        data_response = response.json()
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        zonas = data_response.get("zonas_atencion", [])

        self.assertGreater(
            len(zonas),
            0,
            msg="El perfil debe tener zonas de atención registradas para la prueba.",
        )

        # Iteramos sobre cada zona devuelta para verificar el contrato de la API
        for zona in zonas:
            # 1. Verificamos que SÍ contenga la información orientativa esperada
            self.assertIn(
                "ciudad",
                zona,
                msg="La zona debe incluir la ciudad como información orientativa.",
            )
            self.assertIn(
                "barrio_sector",
                zona,
                msg="La zona debe incluir el barrio/sector como información orientativa.",
            )

            # 2. Verificamos que NO contenga lógica de geolocalización o distancias
            claves_prohibidas = [
                "distancia", 
                "distancia_km", 
                "cobertura", 
                "en_rango", 
                "latitud", 
                "longitud",
                "lat",
                "lng"
            ]
            
            for clave in claves_prohibidas:
                self.assertNotIn(
                    clave,
                    zona,
                    msg=f"El sistema NO debe calcular ni devolver el campo '{clave}' "
                        f"ya que las zonas son estrictamente orientativas.",
                )

        print(
            "\n[test_consulta_zonas_puramente_informativas]",
            "\nStatus HTTP GET:", response.status_code,
            "\nZonas devueltas:", len(zonas),
            "\nMuestra de una zona (verificando estructura limpia):", zonas[0] if zonas else None,
            "\nValidación superada: No se detectaron campos de distancia ni validación geográfica.",
        )

#E5
class PrivacidadPerfilProveedorAjenoTests(APITestCase):

    def setUp(self):
        """
        Crea dos usuarios PROVEEDOR. Autentica al primero e intenta
        modificar los datos del segundo.
        """
        # 1. Creación del proveedor activo (el atacante/intruso)
        self.usuario_activo = Usuario.objects.create_user(
            username="proveedor_activo@test.com",
            email="proveedor_activo@test.com",
            password="ClaveSegura123!",
            first_name="Miguel",
            last_name="Torres",
        )
        self.perfil_base_activo = PerfilUsuario.objects.create(
            usuario=self.usuario_activo,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3100000001",
        )
        self.perfil_proveedor_activo = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base_activo,
            descripcion_profesional="Electricista residencial.",
        )

        # 2. Creación del proveedor ajeno (la víctima)
        self.usuario_ajeno = Usuario.objects.create_user(
            username="proveedor_ajeno@test.com",
            email="proveedor_ajeno@test.com",
            password="ClaveSegura123!",
            first_name="Carlos",
            last_name="Ruiz",
        )
        self.perfil_base_ajeno = PerfilUsuario.objects.create(
            usuario=self.usuario_ajeno,
            rol=PerfilUsuario.Rol.PROVEEDOR,
            telefono="3100000002",
        )
        self.perfil_proveedor_ajeno = PerfilProveedor.objects.create(
            perfil_usuario=self.perfil_base_ajeno,
            descripcion_profesional="Carpintero especialista.",
        )

        # Autenticamos al proveedor activo
        self.client.force_authenticate(user=self.usuario_activo)

        # URL dinámica apuntando al recurso del perfil profesional ajeno
        # Ajusta la ruta a la estructura de tu ViewSet (ej. /api/proveedores/perfiles/<id>/)
        self.url_ajena = f"/api/proveedores/perfiles/{self.perfil_proveedor_ajeno.id}/"

        self.datos_maliciosos = {
            "descripcion_profesional": "Descripción alterada por un intruso."
        }

    def test_modificacion_perfil_profesional_ajeno_denegada(self):
        """
        Un proveedor autenticado no debe poder hacer PATCH 
        en el perfil profesional de otro proveedor.
        """
        response_patch = self.client.patch(
            self.url_ajena,
            data=self.datos_maliciosos,
            format="json",
        )

        # 1. Validamos que el sistema rechace la operación (403 o 404). NO debe ser 200 OK.
        self.assertNotEqual(
            response_patch.status_code,
            status.HTTP_200_OK,
            msg="El sistema no debe permitir modificar el perfil profesional ajeno (esperado 403 o 404).",
        )

        # 2. Verificación de Inmutabilidad
        self.perfil_proveedor_ajeno.refresh_from_db()

        self.assertEqual(
            self.perfil_proveedor_ajeno.descripcion_profesional,
            "Carpintero especialista.",
            msg="La descripción profesional del perfil ajeno debió conservarse intacta.",
        )

        print(
            "\n[test_modificacion_perfil_profesional_ajeno_denegada]",
            "\nStatus HTTP PATCH (Intento de Modificación):", response_patch.status_code,
            "\nDescripción real conservada BD:", self.perfil_proveedor_ajeno.descripcion_profesional,
        )