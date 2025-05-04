#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Implementación simplificada de servicios SOAP para SOA Database
"""

import os
import sys
import logging
import json
import datetime
import uuid
import mysql.connector
from pymongo import MongoClient
from flask import Flask, request, Response
import xml.etree.ElementTree as ET
from lxml import etree
import re
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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Definir los espacios de nombres SOAP
NAMESPACES = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'auth': 'http://services.soadb.example.com/auth',
    'sql': 'http://services.soadb.example.com/sql',
    'nosql': 'http://services.soadb.example.com/nosql',
    'admin': 'http://services.soadb.example.com/admin'
}

# Crear la aplicación Flask
app = Flask(__name__)

# Función para validar token y permisos
def validate_session(session_token, required_role=None):
    """
    Valida un token de sesión y verifica permisos.
    
    Args:
        session_token: Token de sesión a validar
        required_role: Rol requerido (admin, editor, viewer)
    
    Returns:
        Tupla (valid, role, message)
    """
    try:
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
            SELECT user_id, role
            FROM sessions
            WHERE token = %s AND expires_at > NOW()
            """,
            (session_token,)
        )
        session = cursor.fetchone()
        
        if not session:
            return False, None, "Sesión no válida o expirada"
        
        role = session['role']
        
        # Verificar permisos si se especifica un rol requerido
        if required_role:
            # Jerarquía de roles: admin > editor > viewer
            role_hierarchy = {'admin': 3, 'editor': 2, 'viewer': 1}
            
            if role_hierarchy.get(role, 0) < role_hierarchy.get(required_role, 0):
                return False, role, f"Se requiere rol '{required_role}' o superior"
        
        return True, role, "Sesión válida"
    
    except Exception as e:
        logger.error(f"Error al validar sesión: {e}")
        return False, None, str(e)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Función para extraer el cuerpo de la solicitud SOAP
def extract_soap_body(soap_envelope):
    """
    Extrae el cuerpo de un mensaje SOAP y determina la operación.
    
    Args:
        soap_envelope: String XML con el sobre SOAP
    
    Returns:
        Tupla (namespace, operation, parameters)
    """
    try:
        # Analizar el XML
        root = ET.fromstring(soap_envelope)
        
        # Buscar el cuerpo SOAP
        body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
        
        if body is None or len(body) == 0:
            return None, None, {}
        
        # El primer hijo del cuerpo es la operación
        operation_element = body[0]
        
        # Extraer el namespace y la operación
        ns_uri = operation_element.tag.split('}')[0].strip('{')
        operation = operation_element.tag.split('}')[1] if '}' in operation_element.tag else operation_element.tag
        
        # Extraer parámetros
        parameters = {}
        for param in operation_element:
            param_name = param.tag.split('}')[1] if '}' in param.tag else param.tag
            param_value = param.text
            parameters[param_name] = param_value
        
        # Determinar el servicio basado en el namespace
        service = None
        for key, value in NAMESPACES.items():
            if value == ns_uri:
                service = key
                break
        
        return service, operation, parameters
    
    except Exception as e:
        logger.error(f"Error al extraer el cuerpo SOAP: {e}")
        return None, None, {}

# Función para crear una respuesta SOAP
def create_soap_response(service, operation, data):
    """
    Crea una respuesta SOAP.
    
    Args:
        service: Servicio (auth, sql, nosql, admin)
        operation: Operación
        data: Datos a incluir en la respuesta
    
    Returns:
        String XML con la respuesta SOAP
    """
    # Crear el sobre SOAP
    soap_env = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope')
    soap_body = etree.SubElement(soap_env, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    
    # Crear el elemento de respuesta
    response_name = f"{operation}Response"
    ns_uri = NAMESPACES.get(service, '')
    response_element = etree.SubElement(soap_body, f"{{{ns_uri}}}{response_name}")
    
    # Convertir los datos a string si no lo son
    if not isinstance(data, str):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        else:
            data = str(data)
    
    # Añadir los datos
    response_element.text = data
    
    # Convertir el XML a string
    return etree.tostring(soap_env, pretty_print=True, encoding='utf-8').decode('utf-8')

# Función para crear un WSDL
def create_wsdl(service_name):
    """
    Crea un documento WSDL para un servicio.
    
    Args:
        service_name: Nombre del servicio (auth, sql, nosql, admin)
    
    Returns:
        String XML con el WSDL
    """
    # Definir operaciones y tipos según el servicio
    operations = []
    types = []
    
    service_ns = NAMESPACES.get(service_name, '')
    
    if service_name == 'auth':
        operations = [
            {'name': 'login', 'params': ['provider', 'authorization_code', 'redirect_uri']},
            {'name': 'logout', 'params': ['session_token']},
            {'name': 'validateToken', 'params': ['session_token']},
            {'name': 'getUserRole', 'params': ['session_token']},
            {'name': 'register', 'params': ['username', 'email', 'provider']}
        ]
    elif service_name == 'sql':
        operations = [
            {'name': 'listDatabases', 'params': ['session_token']},
            {'name': 'createDatabase', 'params': ['session_token', 'database_name']},
            {'name': 'dropDatabase', 'params': ['session_token', 'database_name']},
            {'name': 'listTables', 'params': ['session_token', 'database_name']},
            {'name': 'createTable', 'params': ['session_token', 'database_name', 'table_name', 'fields_json']},
            {'name': 'dropTable', 'params': ['session_token', 'database_name', 'table_name']},
            {'name': 'insert', 'params': ['session_token', 'database_name', 'table_name', 'data_json']},
            {'name': 'update', 'params': ['session_token', 'database_name', 'table_name', 'data_json', 'where_json']},
            {'name': 'delete', 'params': ['session_token', 'database_name', 'table_name', 'where_json']},
            {'name': 'select', 'params': ['session_token', 'database_name', 'table_name', 'fields', 'where_json']},
            {'name': 'join', 'params': ['session_token', 'database_name', 'join_query', 'params_json']},
            {'name': 'aggregate', 'params': ['session_token', 'database_name', 'table_name', 'operation', 'field', 'group_by', 'where_json']}
        ]
    elif service_name == 'nosql':
        operations = [
            {'name': 'listDatabases', 'params': ['session_token']},
            {'name': 'createDatabase', 'params': ['session_token', 'database_name']},
            {'name': 'dropDatabase', 'params': ['session_token', 'database_name']},
            {'name': 'listCollections', 'params': ['session_token', 'database_name']},
            {'name': 'createCollection', 'params': ['session_token', 'database_name', 'collection_name', 'options_json']},
            {'name': 'dropCollection', 'params': ['session_token', 'database_name', 'collection_name']},
            {'name': 'insertDocument', 'params': ['session_token', 'database_name', 'collection_name', 'documents_json']},
            {'name': 'updateDocument', 'params': ['session_token', 'database_name', 'collection_name', 'filter_json', 'update_json']},
            {'name': 'deleteDocument', 'params': ['session_token', 'database_name', 'collection_name', 'filter_json']},
            {'name': 'findDocument', 'params': ['session_token', 'database_name', 'collection_name', 'filter_json', 'projection_json', 'sort_json']},
            {'name': 'aggregateDocuments', 'params': ['session_token', 'database_name', 'collection_name', 'pipeline_json']}
        ]
    elif service_name == 'admin':
        operations = [
            {'name': 'listAll', 'params': ['interface_type']},
            {'name': 'getServiceHealth', 'params': ['service_name']}
        ]
    
    # Crear el WSDL
    wsdl = f"""<?xml version="1.0" encoding="UTF-8"?>
<wsdl:definitions 
    name="{service_name.capitalize()}Service"
    targetNamespace="{service_ns}"
    xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
    xmlns:tns="{service_ns}"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema">

    <!-- Definición de tipos -->
    <wsdl:types>
        <xsd:schema targetNamespace="{service_ns}">
"""
    
    # Añadir tipos para cada operación
    for op in operations:
        wsdl += f"""
            <!-- Tipo para {op['name']} -->
            <xsd:element name="{op['name']}">
                <xsd:complexType>
                    <xsd:sequence>
"""
        
        for param in op['params']:
            wsdl += f"""
                        <xsd:element name="{param}" type="xsd:string" minOccurs="0"/>
"""
        
        wsdl += f"""
                    </xsd:sequence>
                </xsd:complexType>
            </xsd:element>
            <xsd:element name="{op['name']}Response" type="xsd:string"/>
"""
    
    wsdl += f"""
        </xsd:schema>
    </wsdl:types>

    <!-- Definición de mensajes -->
"""
    
    # Añadir mensajes para cada operación
    for op in operations:
        wsdl += f"""
    <wsdl:message name="{op['name']}Request">
        <wsdl:part name="parameters" element="tns:{op['name']}"/>
    </wsdl:message>
    <wsdl:message name="{op['name']}Response">
        <wsdl:part name="parameters" element="tns:{op['name']}Response"/>
    </wsdl:message>
"""
    
    wsdl += f"""
    <!-- Definición de port types -->
    <wsdl:portType name="{service_name.capitalize()}ServicePortType">
"""
    
    # Añadir operaciones al port type
    for op in operations:
        wsdl += f"""
        <wsdl:operation name="{op['name']}">
            <wsdl:input message="tns:{op['name']}Request"/>
            <wsdl:output message="tns:{op['name']}Response"/>
        </wsdl:operation>
"""
    
    wsdl += f"""
    </wsdl:portType>

    <!-- Binding (conexión con protocolo SOAP) -->
    <wsdl:binding name="{service_name.capitalize()}ServiceSoapBinding" type="tns:{service_name.capitalize()}ServicePortType">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
"""
    
    # Añadir operaciones al binding
    for op in operations:
        wsdl += f"""
        <wsdl:operation name="{op['name']}">
            <soap:operation soapAction="{service_ns}/{op['name']}"/>
            <wsdl:input>
                <soap:body use="literal"/>
            </wsdl:input>
            <wsdl:output>
                <soap:body use="literal"/>
            </wsdl:output>
        </wsdl:operation>
"""
    
    wsdl += f"""
    </wsdl:binding>

    <!-- Definición del servicio -->
    <wsdl:service name="{service_name.capitalize()}Service">
        <wsdl:port name="{service_name.capitalize()}ServicePort" binding="tns:{service_name.capitalize()}ServiceSoapBinding">
            <soap:address location="http://localhost:8080/soap"/>
        </wsdl:port>
    </wsdl:service>
</wsdl:definitions>
"""
    
    return wsdl

# Rutas para los servicios SOAP
@app.route('/soap', methods=['POST'])
def handle_soap():
    """Manejador principal para peticiones SOAP."""
    # Obtener el cuerpo de la petición
    soap_envelope = request.data.decode('utf-8')
    
    # Extraer la operación y los parámetros
    service, operation, parameters = extract_soap_body(soap_envelope)
    
    # Verificar que se pudo extraer la operación
    if not service or not operation:
        return Response(
            "Error al procesar la petición SOAP",
            status=400,
            content_type='text/xml'
        )
    
    logger.info(f"Solicitud SOAP - Servicio: {service}, Operación: {operation}, Parámetros: {parameters}")
    
    # Enrutamiento basado en el servicio y la operación
    result = None
    
    # Servicio de autenticación
    if service == 'auth':
        if operation == 'login':
            result = auth_login(parameters)
        elif operation == 'logout':
            result = auth_logout(parameters)
        elif operation == 'validateToken':
            result = auth_validate_token(parameters)
        elif operation == 'getUserRole':
            result = auth_get_user_role(parameters)
        elif operation == 'register':
            result = auth_register(parameters)
        else:
            result = json.dumps({"error": f"Operación no soportada: {operation}"})
    
    # Servicio SQL
    elif service == 'sql':
        if operation == 'listDatabases':
            result = sql_list_databases(parameters)
        elif operation == 'createDatabase':
            result = sql_create_database(parameters)
        elif operation == 'dropDatabase':
            result = sql_drop_database(parameters)
        elif operation == 'listTables':
            result = sql_list_tables(parameters)
        elif operation == 'createTable':
            result = sql_create_table(parameters)
        elif operation == 'dropTable':
            result = sql_drop_table(parameters)
        elif operation == 'insert':
            result = sql_insert(parameters)
        elif operation == 'update':
            result = sql_update(parameters)
        elif operation == 'delete':
            result = sql_delete(parameters)
        elif operation == 'select':
            result = sql_select(parameters)
        elif operation == 'join':
            result = sql_join(parameters)
        elif operation == 'aggregate':
            result = sql_aggregate(parameters)
        else:
            result = json.dumps({"error": f"Operación no soportada: {operation}"})
    
    # Servicio NoSQL
    elif service == 'nosql':
        if operation == 'listDatabases':
            result = nosql_list_databases(parameters)
        elif operation == 'createDatabase':
            result = nosql_create_database(parameters)
        elif operation == 'dropDatabase':
            result = nosql_drop_database(parameters)
        elif operation == 'listCollections':
            result = nosql_list_collections(parameters)
        elif operation == 'createCollection':
            result = nosql_create_collection(parameters)
        elif operation == 'dropCollection':
            result = nosql_drop_collection(parameters)
        elif operation == 'insertDocument':
            result = nosql_insert_document(parameters)
        elif operation == 'updateDocument':
            result = nosql_update_document(parameters)
        elif operation == 'deleteDocument':
            result = nosql_delete_document(parameters)
        elif operation == 'findDocument':
            result = nosql_find_document(parameters)
        elif operation == 'aggregateDocuments':
            result = nosql_aggregate_documents(parameters)
        else:
            result = json.dumps({"error": f"Operación no soportada: {operation}"})
    
    # Servicio de administración
    elif service == 'admin':
        if operation == 'listAll':
            result = admin_list_all(parameters)
        elif operation == 'getServiceHealth':
            result = admin_get_service_health(parameters)
        else:
            result = json.dumps({"error": f"Operación no soportada: {operation}"})
    
    else:
        result = json.dumps({"error": f"Servicio no reconocido: {service}"})
    
    # Crear y devolver la respuesta SOAP
    soap_response = create_soap_response(service, operation, result)
    
    return Response(
        soap_response,
        status=200,
        content_type='text/xml'
    )

# Ruta para obtener los WSDL
@app.route('/wsdl/<service>', methods=['GET'])
def get_wsdl(service):
    """Devuelve el WSDL para un servicio específico."""
    if service not in ['auth', 'sql', 'nosql', 'admin']:
        return Response(
            f"Servicio no reconocido: {service}",
            status=404,
            content_type='text/plain'
        )
    
    wsdl = create_wsdl(service)
    
    return Response(
        wsdl,
        status=200,
        content_type='text/xml'
    )

# Ruta de health check
@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para comprobar el estado del servicio."""
    return json.dumps({"status": "ok", "service": "app"})

# Implementaciones de los servicios de autenticación
def auth_login(parameters):
    """Implementación de la operación login del servicio de autenticación."""
    provider = parameters.get('provider')
    authorization_code = parameters.get('authorization_code')
    redirect_uri = parameters.get('redirect_uri')
    
    # Validar parámetros
    if not provider or not authorization_code:
        return json.dumps({"error": "Se requieren los parámetros provider y authorization_code"})
    
    # Simular autenticación OAuth2 (en un entorno real, se comunicaría con el proveedor)
    # En este ejemplo, simplemente generamos un token de sesión
    
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
        
        # Buscar usuario (simulado)
        user_id = str(uuid.uuid4())
        username = "Usuario de prueba"
        email = "usuario@example.com"
        role = "admin"  # Para pruebas, todos son admin
        
        # Crear sesión
        session_id = str(uuid.uuid4())
        session_token = str(uuid.uuid4())
        expires_at = datetime.datetime.now() + datetime.timedelta(days=1)
        
        # Insertar sesión en la base de datos
        cursor.execute(
            """
            INSERT INTO sessions (id, user_id, role, token, created_at, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            """,
            (
                session_id,
                user_id,
                role,
                session_token,
                expires_at,
                "127.0.0.1",  # IP ficticia
                "Ejemplo de User-Agent"  # User-Agent ficticio
            )
        )
        
        conn.commit()
        
        # Devolver respuesta
        return json.dumps({
            "success": True,
            "user_id": user_id,
            "session_token": session_token,
            "role": role,
            "expires_at": expires_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en login: {e}")
        return json.dumps({"error": f"Error al iniciar sesión: {str(e)}"})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def auth_logout(parameters):
    """Implementación de la operación logout del servicio de autenticación."""
    session_token = parameters.get('session_token')
    
    # Validar parámetros
    if not session_token:
        return json.dumps({"error": "Se requiere el parámetro session_token"})
    
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

def auth_validate_token(parameters):
    """Implementación de la operación validateToken del servicio de autenticación."""
    session_token = parameters.get('session_token')
    
    # Validar parámetros
    if not session_token:
        return json.dumps({"error": "Se requiere el parámetro session_token"})
    
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
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.token = %s AND s.expires_at > NOW()
            """,
            (session_token,)
        )
        session = cursor.fetchone()
        
        if session:
            # Convertir datetime a string
            if session.get('created_at'):
                session['created_at'] = session['created_at'].isoformat()
            if session.get('expires_at'):
                session['expires_at'] = session['expires_at'].isoformat()
            
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

def auth_get_user_role(parameters):
    """Implementación de la operación getUserRole del servicio de autenticación."""
    session_token = parameters.get('session_token')
    
    # Validar parámetros
    if not session_token:
        return json.dumps({"error": "Se requiere el parámetro session_token"})
    
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

def auth_register(parameters):
    """Implementación de la operación register del servicio de autenticación."""
    username = parameters.get('username')
    email = parameters.get('email')
    provider = parameters.get('provider')
    
    # Validar parámetros
    if not username or not email or not provider:
        return json.dumps({"error": "Se requieren los parámetros username, email y provider"})
    
    try:
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

# Implementaciones de los servicios SQL
def sql_list_databases(parameters):
    """Implementación de la operación listDatabases del servicio SQL."""
    session_token = parameters.get('session_token')
    
    # Validar sesión
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        # Conectar a MySQL
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Obtener lista de bases de datos
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall() if db[0] not in ['information_schema', 'performance_schema', 'mysql', 'sys']]
        
        return json.dumps({
            "success": True,
            "databases": databases
        })
        
    except Exception as e:
        logger.error(f"Error al listar bases de datos: {e}")
        return json.dumps({"error": f"Error al listar bases de datos: {str(e)}"})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def sql_create_database(parameters):
    """Implementación de la operación createDatabase del servicio SQL."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    # Validar parámetros
    if not database_name:
        return json.dumps({"error": "Se requiere el parámetro database_name"})
    
    # Validar sesión y permisos
    valid, role, message = validate_session(session_token, 'admin')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        # Validar nombre de base de datos
        if not database_name.isalnum():
            return json.dumps({
                "success": False,
                "message": "Nombre de base de datos no válido. Use solo letras y números."
            })
        
        # Conectar a MySQL
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Crear base de datos
        cursor.execute(f"CREATE DATABASE {database_name}")
        
        return json.dumps({
            "success": True,
            "message": f"Base de datos '{database_name}' creada correctamente"
        })
        
    except Exception as e:
        logger.error(f"Error al crear base de datos: {e}")
        return json.dumps({"error": f"Error al crear base de datos: {str(e)}"})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def sql_drop_database(parameters):
    """Implementación de la operación dropDatabase del servicio SQL."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    # Validar parámetros
    if not database_name:
        return json.dumps({"error": "Se requiere el parámetro database_name"})
    
    # Validar sesión y permisos
    valid, role, message = validate_session(session_token, 'admin')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        # Validar nombre de base de datos
        if not database_name.isalnum() or database_name in ['information_schema', 'performance_schema', 'mysql', 'sys', 'dbservice']:
            return json.dumps({
                "success": False,
                "message": "Nombre de base de datos no válido o protegido."
            })
        
        # Conectar a MySQL
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Eliminar base de datos
        cursor.execute(f"DROP DATABASE {database_name}")
        
        return json.dumps({
            "success": True,
            "message": f"Base de datos '{database_name}' eliminada correctamente"
        })
        
    except Exception as e:
        logger.error(f"Error al eliminar base de datos: {e}")
        return json.dumps({"error": f"Error al eliminar base de datos: {str(e)}"})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Implementaciones simplificadas de los otros métodos SQL
def sql_list_tables(parameters):
    """Implementación simplificada de listTables."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        
        return json.dumps({
            "success": True,
            "database": database_name,
            "tables": tables
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_create_table(parameters):
    """Implementación simplificada de createTable."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    fields_json = parameters.get('fields_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        fields = json.loads(fields_json)
        
        # Construir SQL para crear tabla
        sql_parts = []
        primary_key = None
        
        for field in fields:
            name = field['name']
            field_type = field['type'].upper()
            nullable = field.get('nullable', True)
            default = field.get('default')
            auto_increment = field.get('auto_increment', False)
            is_primary = field.get('primary_key', False)
            
            field_def = [f"`{name}` {field_type}"]
            
            if not nullable:
                field_def.append("NOT NULL")
            
            if default is not None:
                if isinstance(default, str):
                    field_def.append(f"DEFAULT '{default}'")
                else:
                    field_def.append(f"DEFAULT {default}")
            
            if auto_increment:
                field_def.append("AUTO_INCREMENT")
            
            if is_primary:
                primary_key = name
            
            sql_parts.append(" ".join(field_def))
        
        if primary_key:
            sql_parts.append(f"PRIMARY KEY (`{primary_key}`)")
        
        sql = f"CREATE TABLE `{table_name}` (\n  " + ",\n  ".join(sql_parts) + "\n)"
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.execute(sql)
        
        return json.dumps({
            "success": True,
            "message": f"Tabla '{table_name}' creada correctamente",
            "sql": sql
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_drop_table(parameters):
    """Implementación simplificada de dropTable."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE `{table_name}`")
        
        return json.dumps({
            "success": True,
            "message": f"Tabla '{table_name}' eliminada correctamente"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_insert(parameters):
    """Implementación simplificada de insert."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    data_json = parameters.get('data_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        data = json.loads(data_json)
        if isinstance(data, dict):
            data = [data]
        
        columns = list(data[0].keys())
        placeholders = ", ".join(["%s"] * len(columns))
        
        sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in columns])}) VALUES ({placeholders})"
        
        values = []
        for item in data:
            row = [item[col] for col in columns]
            values.append(row)
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.executemany(sql, values)
        conn.commit()
        
        return json.dumps({
            "success": True,
            "message": f"Se insertaron {cursor.rowcount} registros en la tabla '{table_name}'",
            "rows_affected": cursor.rowcount
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_update(parameters):
    """Implementación simplificada de update."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    data_json = parameters.get('data_json')
    where_json = parameters.get('where_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        data = json.loads(data_json)
        where_conditions = json.loads(where_json) if where_json else {}
        
        set_clause = ", ".join([f"`{col}` = %s" for col in data.keys()])
        set_values = list(data.values())
        
        sql = f"UPDATE `{table_name}` SET {set_clause}"
        
        where_values = []
        if where_conditions:
            where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
            where_values = list(where_conditions.values())
            sql += f" WHERE {where_clause}"
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.execute(sql, set_values + where_values)
        conn.commit()
        
        return json.dumps({
            "success": True,
            "message": f"Se actualizaron {cursor.rowcount} registros en la tabla '{table_name}'",
            "rows_affected": cursor.rowcount
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_delete(parameters):
    """Implementación simplificada de delete."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    where_json = parameters.get('where_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        where_conditions = json.loads(where_json) if where_json else {}
        
        sql = f"DELETE FROM `{table_name}`"
        
        where_values = []
        if where_conditions:
            where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
            where_values = list(where_conditions.values())
            sql += f" WHERE {where_clause}"
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor()
        cursor.execute(sql, where_values)
        conn.commit()
        
        return json.dumps({
            "success": True,
            "message": f"Se eliminaron {cursor.rowcount} registros de la tabla '{table_name}'",
            "rows_affected": cursor.rowcount
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_select(parameters):
    """Implementación simplificada de select."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    fields = parameters.get('fields', '*')
    where_json = parameters.get('where_json')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        where_conditions = json.loads(where_json) if where_json else {}
        
        sql = f"SELECT {fields} FROM `{table_name}`"
        
        where_values = []
        if where_conditions:
            where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
            where_values = list(where_conditions.values())
            sql += f" WHERE {where_clause}"
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, where_values)
        results = cursor.fetchall()
        
        # Convertir resultados a formato serializable
        serializable_results = []
        for row in results:
            serializable_row = {}
            for key, value in row.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    serializable_row[key] = value.isoformat()
                elif isinstance(value, (bytes, bytearray)):
                    serializable_row[key] = value.hex()
                else:
                    serializable_row[key] = value
            serializable_results.append(serializable_row)
        
        return json.dumps({
            "success": True,
            "database": database_name,
            "table": table_name,
            "count": len(serializable_results),
            "data": serializable_results
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_join(parameters):
    """Implementación simplificada de join."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    join_query = parameters.get('join_query')
    params_json = parameters.get('params_json')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        params = json.loads(params_json) if params_json else []
        
        if not join_query.strip().lower().startswith('select'):
            join_query = 'SELECT * ' + join_query
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(join_query, params)
        results = cursor.fetchall()
        
        # Convertir resultados a formato serializable
        serializable_results = []
        for row in results:
            serializable_row = {}
            for key, value in row.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    serializable_row[key] = value.isoformat()
                elif isinstance(value, (bytes, bytearray)):
                    serializable_row[key] = value.hex()
                else:
                    serializable_row[key] = value
            serializable_results.append(serializable_row)
        
        return json.dumps({
            "success": True,
            "database": database_name,
            "count": len(serializable_results),
            "data": serializable_results
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def sql_aggregate(parameters):
    """Implementación simplificada de aggregate."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    table_name = parameters.get('table_name')
    operation = parameters.get('operation')
    field = parameters.get('field')
    group_by = parameters.get('group_by')
    where_json = parameters.get('where_json')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        where_conditions = json.loads(where_json) if where_json else {}
        
        # Construir SQL para la agregación
        if operation.upper() == 'DISTINCT':
            sql = f"SELECT DISTINCT `{field}` FROM `{table_name}`"
        else:
            sql = f"SELECT {operation.upper()}(`{field}`) as result"
            
            if group_by:
                sql += f", `{group_by}`"
            
            sql += f" FROM `{table_name}`"
            
            if group_by:
                sql += f" GROUP BY `{group_by}`"
        
        # Agregar condiciones WHERE si existen
        where_values = []
        if where_conditions:
            where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
            where_values = list(where_conditions.values())
            sql += f" WHERE {where_clause}"
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=database_name
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, where_values)
        results = cursor.fetchall()
        
        # Convertir resultados a formato serializable
        serializable_results = []
        for row in results:
            serializable_row = {}
            for key, value in row.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    serializable_row[key] = value.isoformat()
                elif isinstance(value, (bytes, bytearray)):
                    serializable_row[key] = value.hex()
                else:
                    serializable_row[key] = value
            serializable_results.append(serializable_row)
        
        return json.dumps({
            "success": True,
            "database": database_name,
            "table": table_name,
            "operation": operation,
            "field": field,
            "group_by": group_by,
            "count": len(serializable_results),
            "data": serializable_results
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# Implementaciones de los servicios NoSQL
def nosql_list_databases(parameters):
    """Implementación de la operación listDatabases del servicio NoSQL."""
    session_token = parameters.get('session_token')
    
    # Validar sesión
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        # Conectar a MongoDB
        client = MongoClient(MONGO_URI)
        
        # Obtener lista de bases de datos
        system_dbs = ['admin', 'local', 'config']
        databases = [db for db in client.list_database_names() if db not in system_dbs]
        
        return json.dumps({
            "success": True,
            "databases": databases
        })
        
    except Exception as e:
        logger.error(f"Error al listar bases de datos: {e}")
        return json.dumps({"error": f"Error al listar bases de datos: {str(e)}"})
    finally:
        if 'client' in locals():
            client.close()

# Implementaciones simplificadas de los otros métodos NoSQL
def nosql_create_database(parameters):
    """Implementación simplificada de createDatabase."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    valid, role, message = validate_session(session_token, 'admin')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        db.create_collection('_temp')
        
        return json.dumps({
            "success": True,
            "message": f"Base de datos '{database_name}' creada correctamente"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_drop_database(parameters):
    """Implementación simplificada de dropDatabase."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    valid, role, message = validate_session(session_token, 'admin')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        client = MongoClient(MONGO_URI)
        client.drop_database(database_name)
        
        return json.dumps({
            "success": True,
            "message": f"Base de datos '{database_name}' eliminada correctamente"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_list_collections(parameters):
    """Implementación simplificada de listCollections."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collections = db.list_collection_names()
        
        return json.dumps({
            "success": True,
            "database": database_name,
            "collections": collections
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_create_collection(parameters):
    """Implementación simplificada de createCollection."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        db.create_collection(collection_name)
        
        return json.dumps({
            "success": True,
            "message": f"Colección '{collection_name}' creada correctamente"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_drop_collection(parameters):
    """Implementación simplificada de dropCollection."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        db.drop_collection(collection_name)
        
        return json.dumps({
            "success": True,
            "message": f"Colección '{collection_name}' eliminada correctamente"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_insert_document(parameters):
    """Implementación simplificada de insertDocument."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    documents_json = parameters.get('documents_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        docs = json.loads(documents_json)
        if isinstance(docs, dict):
            docs = [docs]
        
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        
        result = collection.insert_many(docs)
        inserted_ids = [str(id) for id in result.inserted_ids]
        
        return json.dumps({
            "success": True,
            "message": f"Se insertaron {len(inserted_ids)} documentos",
            "inserted_ids": inserted_ids
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_update_document(parameters):
    """Implementación simplificada de updateDocument."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    filter_json = parameters.get('filter_json')
    update_json = parameters.get('update_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        filter_query = json.loads(filter_json)
        update = json.loads(update_json)
        
        if not any(key.startswith('$') for key in update.keys()):
            update = {'$set': update}
        
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        
        result = collection.update_many(filter_query, update)
        
        return json.dumps({
            "success": True,
            "message": f"Se actualizaron {result.modified_count} documentos",
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_delete_document(parameters):
    """Implementación simplificada de deleteDocument."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    filter_json = parameters.get('filter_json')
    
    valid, role, message = validate_session(session_token, 'editor')
    if not valid:
        return json.dumps({"error": message})
    
    try:
        filter_query = json.loads(filter_json)
        
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        
        result = collection.delete_many(filter_query)
        
        return json.dumps({
            "success": True,
            "message": f"Se eliminaron {result.deleted_count} documentos",
            "deleted_count": result.deleted_count
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_find_document(parameters):
    """Implementación simplificada de findDocument."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    filter_json = parameters.get('filter_json')
    projection_json = parameters.get('projection_json')
    sort_json = parameters.get('sort_json')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        filter_query = json.loads(filter_json) if filter_json else {}
        projection = json.loads(projection_json) if projection_json else None
        sort = json.loads(sort_json) if sort_json else None
        
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        
        cursor = collection.find(filter_query, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        
        # Convertir cursor a lista
        documents = list(cursor)
        
        # Serializar documentos a JSON
        import json
        from bson import json_util
        
        return json_util.dumps({
            "success": True,
            "database": database_name,
            "collection": collection_name,
            "count": len(documents),
            "documents": documents
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

def nosql_aggregate_documents(parameters):
    """Implementación simplificada de aggregateDocuments."""
    session_token = parameters.get('session_token')
    database_name = parameters.get('database_name')
    collection_name = parameters.get('collection_name')
    pipeline_json = parameters.get('pipeline_json')
    
    valid, role, message = validate_session(session_token)
    if not valid:
        return json.dumps({"error": message})
    
    try:
        pipeline = json.loads(pipeline_json)
        
        client = MongoClient(MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        
        result = list(collection.aggregate(pipeline))
        
        # Serializar documentos a JSON
        import json
        from bson import json_util
        
        return json_util.dumps({
            "success": True,
            "database": database_name,
            "collection": collection_name,
            "count": len(result),
            "result": result
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        if 'client' in locals():
            client.close()

# Implementaciones de los servicios Admin
def admin_list_all(parameters):
    """Implementación de la operación listAll del servicio Admin."""
    interface_type = parameters.get('interface_type')
    
    services_info = {
        "auth": {
            "methods": [
                {"name": "login", "description": "Autenticación mediante OAuth2"},
                {"name": "logout", "description": "Cierra la sesión actual"},
                {"name": "register", "description": "Registra un nuevo usuario"},
                {"name": "validateToken", "description": "Valida un token de sesión"},
                {"name": "getUserRole", "description": "Obtiene el rol del usuario actual"}
            ]
        },
        "sql": {
            "methods": [
                {"name": "createDatabase", "description": "Crea una nueva base de datos SQL"},
                {"name": "dropDatabase", "description": "Elimina una base de datos SQL"},
                {"name": "listDatabases", "description": "Lista todas las bases de datos SQL disponibles"},
                {"name": "createTable", "description": "Crea una nueva tabla en una base de datos SQL"},
                {"name": "dropTable", "description": "Elimina una tabla de una base de datos SQL"},
                {"name": "listTables", "description": "Lista todas las tablas de una base de datos SQL"},
                {"name": "insert", "description": "Inserta registros en una tabla SQL"},
                {"name": "update", "description": "Actualiza registros en una tabla SQL"},
                {"name": "delete", "description": "Elimina registros de una tabla SQL"},
                {"name": "select", "description": "Consulta registros de una o varias tablas SQL"},
                {"name": "join", "description": "Realiza un JOIN entre tablas SQL"},
                {"name": "aggregate", "description": "Realiza operaciones de agregación (SUM, COUNT, DISTINCT, AVG)"}
            ]
        },
        "nosql": {
            "methods": [
                {"name": "createDatabase", "description": "Crea una nueva base de datos NoSQL"},
                {"name": "dropDatabase", "description": "Elimina una base de datos NoSQL"},
                {"name": "listDatabases", "description": "Lista todas las bases de datos NoSQL disponibles"},
                {"name": "createCollection", "description": "Crea una nueva colección en una base de datos NoSQL"},
                {"name": "dropCollection", "description": "Elimina una colección de una base de datos NoSQL"},
                {"name": "listCollections", "description": "Lista todas las colecciones de una base de datos NoSQL"},
                {"name": "insertDocument", "description": "Inserta documentos en una colección NoSQL"},
                {"name": "updateDocument", "description": "Actualiza documentos en una colección NoSQL"},
                {"name": "deleteDocument", "description": "Elimina documentos de una colección NoSQL"},
                {"name": "findDocument", "description": "Busca documentos en una colección NoSQL"},
                {"name": "aggregateDocuments", "description": "Realiza operaciones de agregación en documentos NoSQL"}
            ]
        },
        "admin": {
            "methods": [
                {"name": "listAll", "description": "Lista todos los servicios disponibles y sus métodos"},
                {"name": "getServiceHealth", "description": "Obtiene el estado de salud de un servicio específico"}
            ]
        }
    }
    
    # Filtrar por tipo de interfaz si se especifica
    if interface_type:
        if interface_type.upper() == "SQL":
            return json.dumps({"sql": services_info["sql"]})
        elif interface_type.upper() == "NOSQL":
            return json.dumps({"nosql": services_info["nosql"]})
        else:
            return json.dumps({"error": f"Tipo de interfaz no válido: {interface_type}"})
    
    return json.dumps(services_info)

def admin_get_service_health(parameters):
    """Implementación de la operación getServiceHealth del servicio Admin."""
    service_name = parameters.get('service_name')
    
    if service_name not in ['auth', 'sql', 'nosql', 'admin']:
        return json.dumps({"status": "error", "message": f"Servicio no encontrado: {service_name}"})
    
    # En un entorno real, aquí verificaríamos la salud real del servicio
    return json.dumps({"status": "healthy", "service": service_name})

# Iniciar el servidor si este script se ejecuta directamente
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)()
            
          

