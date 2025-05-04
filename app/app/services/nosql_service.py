#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servicio NoSQL para la SOA Database
Gestiona operaciones en bases de datos MongoDB.
"""

import os
import sys
import logging
import json
import uuid
import time
import datetime
from bson import json_util, ObjectId
from pymongo import MongoClient
import mysql.connector
from spyne import Application, ServiceBase, rpc, Integer, Unicode, Boolean, Array
from spyne.model.complex import ComplexModel
from spyne.model.fault import Fault
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de MongoDB y MySQL
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://root:rootpassword@mongodb:27017/')

MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'rootpassword')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'dbservice')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Clase para el servicio NoSQL
class NoSQLService(ServiceBase):
    """
    Servicio que maneja operaciones en bases de datos MongoDB.
    """
    
    @rpc(Unicode, _returns=Unicode)
    def listDatabases(ctx, session_token):
        """
        Lista las bases de datos disponibles.
        
        Args:
            session_token: Token de sesión
        
        Returns:
            Lista de bases de datos en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Obtener lista de bases de datos
            # Excluir bases de datos del sistema
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
    
    @rpc(Unicode, Unicode, _returns=Unicode)
    def createDatabase(ctx, session_token, database_name):
        """
        Crea una nueva base de datos.
        En MongoDB, las bases de datos se crean implícitamente al crear una colección.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos a crear
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'admin')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombre de base de datos
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido. Use solo letras, números y guiones bajos."
                })
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Crear una colección temporal para que se cree la base de datos
            db = client[database_name]
            db.create_collection('_temp')
            
            return json.dumps({
                "success": True,
                "message": f"Base de datos '{database_name}' creada correctamente"
            })
            
        except Exception as e:
            logger.error(f"Error al crear base de datos: {e}")
            return json.dumps({"error": f"Error al crear base de datos: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
    
    @rpc(Unicode, Unicode, _returns=Unicode)
    def dropDatabase(ctx, session_token, database_name):
        """
        Elimina una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos a eliminar
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'admin')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombre de base de datos
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name) or database_name in ['admin', 'local', 'config', 'dbservice']:
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido o protegido."
                })
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Eliminar base de datos
            client.drop_database(database_name)
            
            return json.dumps({
                "success": True,
                "message": f"Base de datos '{database_name}' eliminada correctamente"
            })
            
        except Exception as e:
            logger.error(f"Error al eliminar base de datos: {e}")
            return json.dumps({"error": f"Error al eliminar base de datos: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
    
    @rpc(Unicode, Unicode, _returns=Unicode)
    def listCollections(ctx, session_token, database_name):
        """
        Lista las colecciones de una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
        
        Returns:
            Lista de colecciones en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombre de base de datos
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Verificar si la base de datos existe
            if database_name not in client.list_database_names():
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            # Obtener lista de colecciones
            db = client[database_name]
            collections = db.list_collection_names()
            
            # Filtrar colecciones del sistema
            collections = [col for col in collections if not col.startswith('system.')]
            
            return json.dumps({
                "success": True,
                "database": database_name,
                "collections": collections
            })
            
        except Exception as e:
            logger.error(f"Error al listar colecciones: {e}")
            return json.dumps({"error": f"Error al listar colecciones: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def createCollection(ctx, session_token, database_name, collection_name, options_json=None):
        """
        Crea una nueva colección en una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            collection_name: Nombre de la colección a crear
            options_json: JSON con opciones para la creación (opcional)
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not collection_name or not all(c.isalnum() or c == '_' for c in collection_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de colección no válido."
                })
            
            # Parsear opciones si existen
            options = {}
            if options_json:
                try:
                    options = json.loads(options_json)
                    if not isinstance(options, dict):
                        options = {}
                except json.JSONDecodeError:
                    options = {}
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Crear colección
            db = client[database_name]
            db.create_collection(collection_name, **options)
            
            return json.dumps({
                "success": True,
                "message": f"Colección '{collection_name}' creada correctamente"
            })
            
        except Exception as e:
            logger.error(f"Error al crear colección: {e}")
            return json.dumps({"error": f"Error al crear colección: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
    
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def dropCollection(ctx, session_token, database_name, collection_name):
        """
        Elimina una colección de una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            collection_name: Nombre de la colección a eliminar
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not collection_name or not all(c.isalnum() or c == '_' for c in collection_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de colección no válido."
                })
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Verificar si la base de datos y la colección existen
            if database_name not in client.list_database_names():
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            db = client[database_name]
            if collection_name not in db.list_collection_names():
                return json.dumps({
                    "success": False,
                    "message": f"Colección '{collection_name}' no encontrada"
                })
            
            # Eliminar colección
            db.drop_collection(collection_name)
            
            return json.dumps({
                "success": True,
                "message": f"Colección '{collection_name}' eliminada correctamente"
            })
            
        except Exception as e:
            logger.error(f"Error al eliminar colección: {e}")
            return json.dumps({"error": f"Error al eliminar colección: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def insertDocument(ctx, session_token, database_name, collection_name, documents_json):
        """
        Inserta documentos en una colección.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            collection_name: Nombre de la colección
            documents_json: JSON con los documentos a insertar
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not all(c.isalnum() or c == '_' for c in database_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not collection_name or not all(c.isalnum() or c == '_' for c in collection_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de colección no válido."
                })
            
            # Parsear documentos
            try:
                documents = json.loads(documents_json)
                if not isinstance(documents, list):
                    documents = [documents]
            except json.JSONDecodeError:
                return json.dumps({
                    "success": False,
                    "message": "Formato de documentos no válido. Debe ser JSON."
                })
            
            # Conectar a MongoDB
            client = MongoClient(MONGO_URI)
            
            # Verificar si la base de datos y la colección existen
            if database_name not in client.list_database_names():
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            db = client[database_name]
            if collection_name not in db.list_collection_names():
                return json.dumps({
                    "success": False,
                    "message": f"Colección '{collection_name}' no encontrada"
                })
            
            # Insertar documentos
            collection = db[collection_name]
            result = collection.insert_many(documents)
            
            return json.dumps({
                "success": True,
                "message": f"{len(result.inserted_ids)} documentos insertados correctamente",
                "inserted_ids": [str(doc_id) for doc_id in result.inserted_ids]
            })
            
        except Exception as e:
            logger.error(f"Error al insertar documentos: {e}")
            return json.dumps({"error": f"Error al insertar documentos: {str(e)}"})
        finally:
            if 'client' in locals():
                client.close()
              