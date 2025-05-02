#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor principal de la SOA Database
Este módulo gestiona los servicios SOAP para gestionar bases de datos SQL y NoSQL.
"""

import os
import sys
import logging
from spyne import Application, ServiceBase, rpc, Integer, Unicode, Array
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
from werkzeug.serving import run_simple
from flask import Flask, request, Response, abort
import json
from dotenv import load_dotenv

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar servicios
from services.auth_service import AuthService
from services.sql_service import SQLService
from services.nosql_service import NoSQLService

# Cargar variables de entorno
load_dotenv()

# Configuración
SERVICE_HOST = os.getenv('SERVICE_HOST', '0.0.0.0')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '8080'))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)

# Crear aplicaciones SOAP
def create_soap_app(service_class, tns):
    """Crea una aplicación SOAP para un servicio específico."""
    application = Application(
        [service_class],
        tns=tns,
        in_protocol=Soap11(validator='lxml'),
        out_protocol=Soap11()
    )
    return WsgiApplication(application)

# Crear aplicaciones SOAP para cada servicio
soap_services = {
    'auth': create_soap_app(AuthService, 'http://services.soadb.example.com/auth'),
    'sql': create_soap_app(SQLService, 'http://services.soadb.example.com/sql'),
    'nosql': create_soap_app(NoSQLService, 'http://services.soadb.example.com/nosql'),
}

# Clase para el servicio de administración
class AdminService(ServiceBase):
    """
    Servicio de administración que proporciona información sobre los servicios disponibles.
    """
    
    @rpc(Unicode, _returns=Unicode)
    def listAll(ctx, interface_type=None):
        """
        Lista todos los servicios disponibles y sus métodos.
        
        Args:
            interface_type: Tipo de interfaz ('SQL' o 'NOSQL'). Si es None, muestra todos.
        
        Returns:
            Cadena JSON con la información de los servicios.
        """
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
    
    @rpc(Unicode, _returns=Unicode)
    def getServiceHealth(ctx, service_name):
        """
        Obtiene el estado de salud de un servicio específico.
        
        Args:
            service_name: Nombre del servicio ('auth', 'sql', 'nosql', 'admin')
        
        Returns:
            Cadena JSON con información del estado del servicio.
        """
        if service_name not in soap_services and service_name != 'admin':
            return json.dumps({"status": "error", "message": f"Servicio no encontrado: {service_name}"})
        
        # En un entorno real, aquí verificaríamos la salud real del servicio
        return json.dumps({"status": "healthy", "service": service_name})

# Crear aplicación SOAP para el servicio Admin
soap_services['admin'] = create_soap_app(AdminService, 'http://services.soadb.example.com/admin')

# Ruta principal para recibir peticiones SOAP
@app.route('/soap', methods=['POST'])
def soap_handler():
    """
    Manejador principal para peticiones SOAP.
    Determina qué servicio debe procesar la petición y la redirige.
    """
    soap_action = request.headers.get('SOAPAction', '').strip('"\'')
    content_type = request.headers.get('Content-Type', '')
    
    # Validar petición SOAP
    if "text/xml" not in content_type and "application/soap+xml" not in content_type:
        return Response("Content-Type no válido", status=415)
    
    # Determinar el servicio basado en SOAPAction o contenido
    service_name = None
    
    if soap_action:
        # auth.login -> auth
        service_name = soap_action.split('.')[0] if '.' in soap_action else None
    
    if not service_name:
        # Intentar determinar el servicio desde el contenido XML
        body = request.data.decode('utf-8')
        for name in soap_services.keys():
            if f"services.soadb.example.com/{name}" in body:
                service_name = name
                break
    
    if not service_name or service_name not in soap_services:
        return Response("Servicio no encontrado", status=400)
    
    # Procesar la petición con el servicio correspondiente
    wsgi_app = soap_services[service_name]
    
    # Convertir Flask request a environ WSGI
    environ = request.environ.copy()
    
    # Crear una función para capturar la respuesta
    def start_response(status, headers):
        nonlocal response_status, response_headers
        response_status = status
        response_headers = headers
    
    response_status = None
    response_headers = None
    
    # Llamar a la aplicación WSGI
    response_body = b''.join(wsgi_app(environ, start_response))
    
    # Crear respuesta Flask
    response = Response(response_body, status=int(response_status.split()[0]))
    for header, value in response_headers:
        response.headers[header] = value
    
    return response

# Ruta para obtener WSDLs
@app.route('/wsdl/<service>', methods=['GET'])
def get_wsdl(service):
    """
    Devuelve el WSDL para un servicio específico.
    """
    if service not in soap_services:
        return Response("Servicio no encontrado", status=404)
    
    # Obtener la aplicación SOAP correspondiente
    soap_app = soap_services[service]
    
    # Generar WSDL
    wsdl = soap_app.app.interface.get_wsdl()
    
    # Devolver el WSDL
    return Response(wsdl, mimetype='text/xml')

# Ruta de health check
@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para comprobar el estado del servicio."""
    return json.dumps({"status": "ok", "service": "app"})

# Función principal para iniciar el servidor
if __name__ == "__main__":
    logger.info(f"Iniciando servidor en {SERVICE_HOST}:{SERVICE_PORT}")
    run_simple(SERVICE_HOST, SERVICE_PORT, app, threaded=True)