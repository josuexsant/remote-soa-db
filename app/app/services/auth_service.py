#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servicio de Autenticación para la SOA Database
Gestiona la autenticación de usuarios mediante OAuth2.
"""

import os
import sys
import logging
import json
import uuid
import time
import datetime
import mysql.connector
from pymongo import MongoClient
from spyne import Application, ServiceBase, rpc, Integer, Unicode, Boolean, Array
from spyne.model.complex import ComplexModel
from spyne.model.fault import Fault
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de bases de datos
MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'rootpassword')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'dbservice')

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://root:rootpassword@mongodb:27017/')

# Configuración OAuth
OAUTH_GOOGLE_CLIENT_ID = os.getenv('OAUTH_GOOGLE_CLIENT_ID', '')
OAUTH_GOOGLE_CLIENT_SECRET = os.getenv('OAUTH_GOOGLE_CLIENT_SECRET', '')
OAUTH_FACEBOOK_CLIENT_ID = os.getenv('OAUTH_FACEBOOK_CLIENT_ID', '')
OAUTH_FACEBOOK_CLIENT_SECRET = os.getenv('OAUTH_FACEBOOK_CLIENT_SECRET', '')
OAUTH_MICROSOFT_CLIENT_ID = os.getenv('OAUTH_MICROSOFT_CLIENT_ID', '')
OAUTH_MICROSOFT_CLIENT_SECRET = os.getenv('OAUTH_MICROSOFT_CLIENT_SECRET', '')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Clase para representar un usuario
class User(ComplexModel):
    __namespace__ = "http://services.soadb.example.com/auth"
    id = Unicode
    username = Unicode
    email = Unicode
    provider = Unicode
    provider_id = Unicode
    role = Unicode
    created_at = Unicode
    last_login = Unicode

# Configuración de OAuth2 para diferentes proveedores
OAUTH_PROVIDERS = {
    'google': {
        'client_id': OAUTH_GOOGLE_CLIENT_ID,
        'client_secret': OAUTH_GOOGLE_CLIENT_SECRET,
        'authorize_url': 'https://accounts.google.com/o/oauth2/auth',
        'token_url': 'https://accounts.google.com/o/oauth2/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v1/userinfo',
        'scope': ['openid', 'email', 'profile']
    },
    'facebook': {
        'client_id': OAUTH_FACEBOOK_CLIENT_ID,
        'client_secret': OAUTH_FACEBOOK_CLIENT_SECRET,
        'authorize_url': 'https://www.facebook.com/v13.0/dialog/oauth',
        'token_url': 'https://graph.facebook.com/v13.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email',
        'scope': ['email', 'public_profile']
    },
    'microsoft': {
        'client_id': OAUTH_MICROSOFT_CLIENT_ID,
        'client_secret': OAUTH_MICROSOFT_CLIENT_SECRET,
        'authorize_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'userinfo_url': 'https://graph.microsoft.com/v1.0/me',
        'scope': ['openid', 'email', 'profile', 'User.Read']
    }
}

# Clase para el servicio de autenticación
class AuthService(ServiceBase):
    """
    Servicio que maneja la autenticación de usuarios mediante OAuth2.
    """
    
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def login(ctx, provider, authorization_code, redirect_uri):
        """
        Inicia sesión utilizando un proveedor OAuth2.
        
        Args:
            provider: Nombre del proveedor (google, facebook, microsoft)
            authorization_code: Código de autorización recibido del proveedor
            redirect_uri: URI de redirección utilizado en la solicitud
        
        Returns:
            Token de sesión en formato JSON
        """
        try:
            # Validar proveedor
            if provider not in OAUTH_PROVIDERS:
                return json.dumps({"error": f"Proveedor no soportado: {provider}"})
            
            # Configurar cliente OAuth2
            oauth_config = OAUTH_PROVIDERS[provider]
            oauth = OAuth2Session(
                oauth_config['client_id'],
                redirect_uri=redirect_uri,
                scope=oauth_config['scope']
            )
            
            # Obtener token
            token = oauth.fetch_token(
                oauth_config['token_url'],
                client_secret=oauth_config['client_secret'],
                code=authorization_code
            )
            
            # Obtener información del usuario
            user_info_response = oauth.get(oauth_config['userinfo_url'])
            user_info = user_info_response.json()
            
            # Extraer datos del usuario según el proveedor
            if provider == 'google':
                provider_id = user_info.get('id', '')
                email = user_info.get('email', '')
                username = user_info.get('name', '')
            elif provider == 'facebook':
                provider_id = user_info.get('id', '')
                email = user_info.get('email', '')
                username = user_info.get('name', '')
            elif provider == 'microsoft':
                provider_id = user_info.get('id', '')
                email = user_info.get('mail', user_info.get('userPrincipalName', ''))
                username = user_info.get('displayName', '')
            else:
                return json.dumps({"error": "Proveedor no reconocido"})
            
            # Verificar si el usuario existe, si no, registrarlo
            user_id = None
            user_role = 'viewer'  # Rol por defecto
            
            # Conectar a MySQL
            try:
                conn = mysql.connector.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DATABASE
                )
                cursor = conn.cursor(dictionary=True)
                
                # Buscar usuario
                cursor.execute(
                    "SELECT id, role FROM users WHERE provider = %s AND provider_id = %s",
                    (provider, provider_id)
                )
                user = cursor.fetchone()
                
                if user:
                    # Usuario existente
                    user_id = user['id']
                    user_role = user['role']
                    
                    # Actualizar último login
                    cursor.execute(
                        "UPDATE users SET last_login = NOW() WHERE id = %s",
                        (user_id,)
                    )
                else:
                    # Nuevo usuario
                    user_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO users (id, username, email, provider, provider_id, role, created_at, last_login)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        """,
                        (user_id, username, email, provider, provider_id, user_role)
                    )
                
                conn.commit()
                
                # Crear sesión
                session_id = str(uuid.uuid4())
                session_token = str(uuid.uuid4())
                expires_at = datetime.datetime.now() + datetime.timedelta(days=1)
                
                cursor.execute(
                    """
                    INSERT INTO sessions (id, user_id, role, token, created_at, expires_at, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
                    """,
                    (
                        session_id,
                        user_id,
                        user_role,
                        session_token,
                        expires_at,
                        ctx.transport.req.remote_addr if hasattr(ctx.transport, 'req') else '',
                        ctx.transport.req.environ.get('HTTP_USER_AGENT', '') if hasattr(ctx.transport, 'req') else ''
                    )
                )
                
                conn.commit()
                
                # También guardar en MongoDB para redundancia
                try:
                    mongo_client = MongoClient(MONGO_URI)
                    db = mongo_client['dbservice']
                    
                    # Verificar si el usuario existe
                    user_doc = db.users.find_one({
                        'provider': provider,
                        'provider_id': provider_id
                    })
                    
                    if not user_doc:
                        # Insertar nuevo usuario
                        db.users.insert_one({
                            '_id': user_id,
                            'username': username,
                            'email': email,
                            'provider': provider,
                            'provider_id': provider_id,
                            'role': user_role,
                            'created_at': datetime.datetime.now(),
                            'last_login': datetime.datetime.now()
                        })
                    else:
                        # Actualizar último login
                        db.users.update_one(
                            {'_id': user_id},
                            {'$set': {'last_login': datetime.datetime.now()}}
                        )
                    
                    # Crear sesión
                    db.sessions.insert_one({
                        '_id': session_id,
                        'user_id': user_id,
                        'role': user_role,
                        'token': session_token,
                        'created_at': datetime.datetime.now(),
                        'expires_at': expires_at,
                        'ip_address': ctx.transport.req.remote_addr if hasattr(ctx.transport, 'req') else '',
                        'user_agent': ctx.transport.req.environ.get('HTTP_USER_AGENT', '') if hasattr(ctx.transport, 'req') else ''
                    })
                    
                except Exception as e:
                    logger.error(f"Error al guardar en MongoDB: {e}")
                    # Continuar aunque haya error en MongoDB, ya tenemos los datos en MySQL
                
                # Devolver token de sesión
                return json.dumps({
                    "success": True,
                    "user_id": user_id,
                    "session_token": session_token,
                    "role": user_role,
                    "expires_at": expires_at.isoformat()
                })
                
            except mysql.connector.Error as e:
                logger.error(f"Error de base de datos MySQL: {e}")
                return json.dumps({"error": f"Error de base de datos: {str(e)}"})
            finally:
                if 'cursor' in locals():
                    cursor.close()
                if 'conn' in locals():
                    conn.close()
        
        except Exception as e:
            logger.error(f"Error en login: {e}")
            return json.dumps({"error": f"Error al iniciar sesión: {str(e)}"})
    
    @rpc(Unicode, _returns=Unicode)
    def logout(ctx, session_token):
        """
        Cierra la sesión del usuario.
        
        Args:
            session_token: Token de sesión a cerrar
        
        Returns:
            Resultado en formato JSON
        """
        try:
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor()
            
            # Eliminar sesión
            cursor.execute(
                "DELETE FROM sessions WHERE token = %s",
                (session_token,)
            )
            
            rows_affected = cursor.rowcount
            conn.commit()
            
            # También eliminar en MongoDB
            try:
                mongo_client = MongoClient(MONGO_URI)
                db = mongo_client['dbservice']
                db.sessions.delete_one({'token': session_token})
            except Exception as e:
                logger.error(f"Error al eliminar sesión de MongoDB: {e}")
            
            return json.dumps({
                "success": True,
                "message": "Sesión cerrada correctamente" if rows_affected > 0 else "No se encontró la sesión"
            })
            
        except Exception as e:
            logger.error(f"Error en logout: {e}")
            return json.dumps({"error": f"Error al cerrar sesión: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, _returns=Unicode)
    def validateToken(ctx, session_token):
        """
        Valida un token de sesión.
        
        Args:
            session_token: Token de sesión a validar
        
        Returns:
            Información de la sesión en formato JSON
        """
        try:
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor(dictionary=True)
            
            # Buscar sesión
            cursor.execute(
                """
                SELECT s.id, s.user_id, s.role, s.created_at, s.expires_at, u.username, u.email
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = %s AND s.expires_at > NOW()
                """,
                (session_token,)
            )
            session = cursor.fetchone()
            
            if session:
                # Convertir datetime a string
                session['created_at'] = session['created_at'].isoformat() if session['created_at'] else None
                session['expires_at'] = session['expires_at'].isoformat() if session['expires_at'] else None
                
                return json.dumps({
                    "valid": True,
                    "session": session
                })
            else:
                return json.dumps({
                    "valid": False,
                    "message": "Sesión no válida o expirada"
                })
            
        except Exception as e:
            logger.error(f"Error en validateToken: {e}")
            return json.dumps({"error": f"Error al validar token: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, _returns=Unicode)
    def getUserRole(ctx, session_token):
        """
        Obtiene el rol del usuario.
        
        Args:
            session_token: Token de sesión
        
        Returns:
            Rol del usuario en formato JSON
        """
        try:
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor(dictionary=True)
            
            # Buscar rol
            cursor.execute(
                """
                SELECT role
                FROM sessions
                WHERE token = %s AND expires_at > NOW()
                """,
                (session_token,)
            )
            result = cursor.fetchone()
            
            if result:
                return json.dumps({
                    "success": True,
                    "role": result['role']
                })
            else:
                return json.dumps({
                    "success": False,
                    "message": "Sesión no válida o expirada"
                })
            
        except Exception as e:
            logger.error(f"Error en getUserRole: {e}")
            return json.dumps({"error": f"Error al obtener rol: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def register(ctx, username, email, provider):
        """
        Método para pre-registrar un usuario. En un caso real, se enviaría un email de verificación.
        Esta es una implementación simplificada para pruebas.
        
        Args:
            username: Nombre de usuario
            email: Correo electrónico
            provider: Proveedor (google, facebook, microsoft)
        
        Returns:
            Resultado del registro en formato JSON
        """
        try:
            # Validar proveedor
            if provider not in OAUTH_PROVIDERS:
                return json.dumps({"error": f"Proveedor no soportado: {provider}"})
            
            # Generar IDs
            user_id = str(uuid.uuid4())
            provider_id = f"pending_{str(uuid.uuid4())}"
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor()
            
            # Verificar si el correo ya existe
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return json.dumps({
                    "success": False,
                    "message": "El correo ya está registrado"
                })
            
            # Crear usuario
            cursor.execute(
                """
                INSERT INTO users (id, username, email, provider, provider_id, role, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (user_id, username, email, provider, provider_id, 'viewer')
            )
            
            conn.commit()
            
            # También guardar en MongoDB
            try:
                mongo_client = MongoClient(MONGO_URI)
                db = mongo_client['dbservice']
                
                db.users.insert_one({
                    '_id': user_id,
                    'username': username,
                    'email': email,
                    'provider': provider,
                    'provider_id': provider_id,
                    'role': 'viewer',
                    'created_at': datetime.datetime.now()
                })
            except Exception as e:
                logger.error(f"Error al guardar en MongoDB: {e}")
            
            return json.dumps({
                "success": True,
                "user_id": user_id,
                "message": "Usuario pre-registrado correctamente. Completa el proceso con el proveedor OAuth."
            })
            
        except Exception as e:
            logger.error(f"Error en register: {e}")
            return json.dumps({"error": f"Error al registrar usuario: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()