#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servicio SQL para la SOA Database
Gestiona operaciones en bases de datos MySQL.
"""

import os
import sys
import logging
import json
import uuid
import time
import datetime
import mysql.connector
from mysql.connector import errorcode
from spyne import Application, ServiceBase, rpc, Integer, Unicode, Boolean, Array
from spyne.model.complex import ComplexModel
from spyne.model.fault import Fault
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de MySQL
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

# Clase para el servicio SQL
class SQLService(ServiceBase):
    """
    Servicio que maneja operaciones en bases de datos MySQL.
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
            
        except mysql.connector.Error as e:
            logger.error(f"Error al listar bases de datos: {e}")
            return json.dumps({"error": f"Error al listar bases de datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, _returns=Unicode)
    def createDatabase(ctx, session_token, database_name):
        """
        Crea una nueva base de datos.
        
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
            if not database_name or not database_name.isalnum():
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
            
        except mysql.connector.Error as e:
            logger.error(f"Error al crear base de datos: {e}")
            return json.dumps({"error": f"Error al crear base de datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
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
            if not database_name or not database_name.isalnum() or database_name in ['information_schema', 'performance_schema', 'mysql', 'sys', 'dbservice']:
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
            
        except mysql.connector.Error as e:
            logger.error(f"Error al eliminar base de datos: {e}")
            return json.dumps({"error": f"Error al eliminar base de datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, _returns=Unicode)
    def listTables(ctx, session_token, database_name):
        """
        Lista las tablas de una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
        
        Returns:
            Lista de tablas en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombre de base de datos
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Listar tablas
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            
            return json.dumps({
                "success": True,
                "database": database_name,
                "tables": tables
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            logger.error(f"Error al listar tablas: {e}")
            return json.dumps({"error": f"Error al listar tablas: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def createTable(ctx, session_token, database_name, table_name, fields_json):
        """
        Crea una nueva tabla en una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla a crear
            fields_json: JSON con la definición de campos
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido. Use letras, números y guiones bajos."
                })
            
            # Validar y parsear campos
            try:
                fields = json.loads(fields_json)
                if not isinstance(fields, list) or not fields:
                    return json.dumps({
                        "success": False,
                        "message": "La definición de campos debe ser un array no vacío."
                    })
                
                for field in fields:
                    if not isinstance(field, dict) or 'name' not in field or 'type' not in field:
                        return json.dumps({
                            "success": False,
                            "message": "Cada campo debe tener 'name' y 'type'."
                        })
            except json.JSONDecodeError:
                return json.dumps({
                    "success": False,
                    "message": "JSON de campos no válido."
                })
            
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
                
                # Validar nombre de campo
                if not all(c.isalnum() or c == '_' for c in name):
                    return json.dumps({
                        "success": False,
                        "message": f"Nombre de campo no válido: {name}"
                    })
                
                # Construir definición de campo
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
            
            # Agregar clave primaria si existe
            if primary_key:
                sql_parts.append(f"PRIMARY KEY (`{primary_key}`)")
            
            # Construir SQL completo
            sql = f"CREATE TABLE `{table_name}` (\n  " + ",\n  ".join(sql_parts) + "\n)"
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Crear tabla
            cursor.execute(sql)
            
            return json.dumps({
                "success": True,
                "message": f"Tabla '{table_name}' creada correctamente",
                "sql": sql
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            logger.error(f"Error al crear tabla: {e}")
            return json.dumps({"error": f"Error al crear tabla: {str(e)}"})
        except Exception as e:
            logger.error(f"Error general: {e}")
            return json.dumps({"error": f"Error general: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def dropTable(ctx, session_token, database_name, table_name):
        """
        Elimina una tabla de una base de datos.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla a eliminar
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Eliminar tabla
            cursor.execute(f"DROP TABLE `{table_name}`")
            
            return json.dumps({
                "success": True,
                "message": f"Tabla '{table_name}' eliminada correctamente"
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error al eliminar tabla: {e}")
            return json.dumps({"error": f"Error al eliminar tabla: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def insert(ctx, session_token, database_name, table_name, data_json):
        """
        Inserta registros en una tabla.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla
            data_json: JSON con los datos a insertar
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Validar y parsear datos
            try:
                data = json.loads(data_json)
                if not isinstance(data, (dict, list)):
                    return json.dumps({
                        "success": False,
                        "message": "Los datos deben ser un objeto o una lista de objetos."
                    })
                
                # Convertir a lista si es un solo objeto
                if isinstance(data, dict):
                    data = [data]
                
                if not data:
                    return json.dumps({
                        "success": False,
                        "message": "No hay datos para insertar."
                    })
                
                # Validar que todos los objetos tengan las mismas claves
                keys = set(data[0].keys())
                for item in data:
                    if set(item.keys()) != keys:
                        return json.dumps({
                            "success": False,
                            "message": "Todos los objetos deben tener las mismas claves."
                        })
            except json.JSONDecodeError:
                return json.dumps({
                    "success": False,
                    "message": "JSON de datos no válido."
                })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Construir SQL para insertar
            columns = list(keys)
            placeholders = ", ".join(["%s"] * len(columns))
            
            sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in columns])}) VALUES ({placeholders})"
            
            # Preparar valores para insertar
            values = []
            for item in data:
                row = [item[col] for col in columns]
                values.append(row)
            
            # Ejecutar inserción
            cursor.executemany(sql, values)
            conn.commit()
            
            return json.dumps({
                "success": True,
                "message": f"Se insertaron {cursor.rowcount} registros en la tabla '{table_name}'",
                "rows_affected": cursor.rowcount
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error al insertar datos: {e}")
            return json.dumps({"error": f"Error al insertar datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def update(ctx, session_token, database_name, table_name, data_json, where_json=None):
        """
        Actualiza registros en una tabla.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla
            data_json: JSON con los datos a actualizar
            where_json: JSON con condiciones para la actualización (opcional)
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Validar y parsear datos
            try:
                data = json.loads(data_json)
                if not isinstance(data, dict) or not data:
                    return json.dumps({
                        "success": False,
                        "message": "Los datos deben ser un objeto no vacío."
                    })
                
                # Parsear condiciones where si existen
                where_conditions = {}
                if where_json:
                    where_conditions = json.loads(where_json)
                    if not isinstance(where_conditions, dict):
                        return json.dumps({
                            "success": False,
                            "message": "Las condiciones WHERE deben ser un objeto."
                        })
            except json.JSONDecodeError:
                return json.dumps({
                    "success": False,
                    "message": "JSON no válido."
                })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Construir SQL para actualizar
            set_clause = ", ".join([f"`{col}` = %s" for col in data.keys()])
            set_values = list(data.values())
            
            sql = f"UPDATE `{table_name}` SET {set_clause}"
            
            # Agregar condiciones WHERE si existen
            where_values = []
            if where_conditions:
                where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
                where_values = list(where_conditions.values())
                sql += f" WHERE {where_clause}"
            
            # Ejecutar actualización
            cursor.execute(sql, set_values + where_values)
            conn.commit()
            
            return json.dumps({
                "success": True,
                "message": f"Se actualizaron {cursor.rowcount} registros en la tabla '{table_name}'",
                "rows_affected": cursor.rowcount
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error al actualizar datos: {e}")
            return json.dumps({"error": f"Error al actualizar datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def delete(ctx, session_token, database_name, table_name, where_json=None):
        """
        Elimina registros de una tabla.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla
            where_json: JSON con condiciones para la eliminación (opcional)
        
        Returns:
            Resultado en formato JSON
        """
        # Validar sesión y permisos
        valid, role, message = validate_session(session_token, 'editor')
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Parsear condiciones where si existen
            where_conditions = {}
            if where_json:
                try:
                    where_conditions = json.loads(where_json)
                    if not isinstance(where_conditions, dict):
                        return json.dumps({
                            "success": False,
                            "message": "Las condiciones WHERE deben ser un objeto."
                        })
                except json.JSONDecodeError:
                    return json.dumps({
                        "success": False,
                        "message": "JSON de condiciones no válido."
                    })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor()
            
            # Construir SQL para eliminar
            sql = f"DELETE FROM `{table_name}`"
            
            # Agregar condiciones WHERE si existen
            where_values = []
            if where_conditions:
                where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
                where_values = list(where_conditions.values())
                sql += f" WHERE {where_clause}"
            
            # Ejecutar eliminación
            cursor.execute(sql, where_values)
            conn.commit()
            
            return json.dumps({
                "success": True,
                "message": f"Se eliminaron {cursor.rowcount} registros de la tabla '{table_name}'",
                "rows_affected": cursor.rowcount
            })
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error al eliminar datos: {e}")
            return json.dumps({"error": f"Error al eliminar datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def select(ctx, session_token, database_name, table_name, fields=None, where_json=None):
        """
        Consulta registros de una tabla.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla
            fields: Campos a seleccionar, separados por comas (o "*" para todos)
            where_json: JSON con condiciones para la consulta (opcional)
        
        Returns:
            Registros en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Si no se especifican campos, seleccionar todos
            if not fields:
                fields = "*"
            
            # Parsear condiciones where si existen
            where_conditions = {}
            if where_json:
                try:
                    where_conditions = json.loads(where_json)
                    if not isinstance(where_conditions, dict):
                        return json.dumps({
                            "success": False,
                            "message": "Las condiciones WHERE deben ser un objeto."
                        })
                except json.JSONDecodeError:
                    return json.dumps({
                        "success": False,
                        "message": "JSON de condiciones no válido."
                    })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor(dictionary=True)
            
            # Construir SQL para consultar
            sql = f"SELECT {fields} FROM `{table_name}`"
            
            # Agregar condiciones WHERE si existen
            where_values = []
            if where_conditions:
                where_clause = " AND ".join([f"`{col}` = %s" for col in where_conditions.keys()])
                where_values = list(where_conditions.values())
                sql += f" WHERE {where_clause}"
            
            # Ejecutar consulta
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
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error al consultar datos: {e}")
            return json.dumps({"error": f"Error al consultar datos: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    # Operaciones de consulta avanzadas
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def join(ctx, session_token, database_name, join_query, params_json=None):
        """
        Realiza un JOIN entre tablas.
        
        Args: 
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            join_query: Consulta SQL para el JOIN (sin WHERE)
            params_json: JSON con parámetros para la consulta (opcional)
        
        Returns:
            Registros en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            # Validar consulta JOIN
            if not join_query or 'join' not in join_query.lower():
                return json.dumps({
                    "success": False,
                    "message": "La consulta debe incluir un JOIN."
                })
            
            # Rechazar consultas potencialmente peligrosas
            if any(keyword in join_query.lower() for keyword in ['delete', 'update', 'insert', 'create', 'drop', 'alter', 'grant']):
                return json.dumps({
                    "success": False,
                    "message": "La consulta contiene comandos no permitidos."
                })
            
            # Parsear parámetros si existen
            params = []
            if params_json:
                try:
                    params_obj = json.loads(params_json)
                    if isinstance(params_obj, list):
                        params = params_obj
                    elif isinstance(params_obj, dict):
                        params = list(params_obj.values())
                    else:
                        return json.dumps({
                            "success": False,
                            "message": "Los parámetros deben ser un array o un objeto."
                        })
                except json.JSONDecodeError:
                    return json.dumps({
                        "success": False,
                        "message": "JSON de parámetros no válido."
                    })
            
            # Asegurarse de que la consulta comienza con SELECT
            if not join_query.strip().lower().startswith('select'):
                join_query = 'SELECT * ' + join_query
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor(dictionary=True)
            
            # Ejecutar consulta JOIN
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
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            
            logger.error(f"Error en consulta JOIN: {e}")
            return json.dumps({"error": f"Error en consulta JOIN: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    @rpc(Unicode, Unicode, Unicode, Unicode, Unicode, _returns=Unicode)
    def aggregate(ctx, session_token, database_name, table_name, operation, field, group_by=None, where_json=None):
        """
        Realiza operaciones de agregación en una tabla.
        
        Args:
            session_token: Token de sesión
            database_name: Nombre de la base de datos
            table_name: Nombre de la tabla
            operation: Operación a realizar (SUM, COUNT, DISTINCT, AVG)
            field: Campo sobre el que se realiza la operación
            group_by: Campo para agrupar (opcional)
            where_json: JSON con condiciones para la consulta (opcional)
        
        Returns:
            Resultado de la agregación en formato JSON
        """
        # Validar sesión
        valid, role, message = validate_session(session_token)
        if not valid:
            return json.dumps({"error": message})
        
        try:
            # Validar nombres
            if not database_name or not database_name.isalnum():
                return json.dumps({
                    "success": False,
                    "message": "Nombre de base de datos no válido."
                })
            
            if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
                return json.dumps({
                    "success": False,
                    "message": "Nombre de tabla no válido."
                })
            
            # Validar operación
            valid_operations = ['SUM', 'COUNT', 'DISTINCT', 'AVG']
            if operation.upper() not in valid_operations:
                return json.dumps({
                    "success": False,
                    "message": f"Operación no válida. Permitidas: {', '.join(valid_operations)}"
                })
            
            operation = operation.upper()
            
            # Validar campo
            if not field or not all(c.isalnum() or c == '_' for c in field):
                return json.dumps({
                    "success": False,
                    "message": "Campo no válido."
                })
            
            # Validar campo de agrupación
            if group_by and not all(c.isalnum() or c == '_' for c in group_by):
                return json.dumps({
                    "success": False,
                    "message": "Campo de agrupación no válido."
                })
            
            # Parsear condiciones where si existen
            where_conditions = {}
            if where_json:
                try:
                    where_conditions = json.loads(where_json)
                    if not isinstance(where_conditions, dict):
                        return json.dumps({
                            "success": False,
                            "message": "Las condiciones WHERE deben ser un objeto."
                        })
                except json.JSONDecodeError:
                    return json.dumps({
                        "success": False,
                        "message": "JSON de condiciones no válido."
                    })
            
            # Conectar a MySQL
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=database_name
            )
            cursor = conn.cursor(dictionary=True)
            
            # Construir SQL para la agregación
            if operation == 'DISTINCT':
                # DISTINCT es un caso especial
                sql = f"SELECT DISTINCT `{field}` FROM `{table_name}`"
            else:
                # Para otras operaciones usamos funciones de agregación
                sql = f"SELECT {operation}(`{field}`) as result"
                
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
            
            # Ejecutar consulta
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
            
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_BAD_DB_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Base de datos '{database_name}' no encontrada"
                })
            elif e.errno == errorcode.ER_BAD_TABLE_ERROR:
                return json.dumps({
                    "success": False,
                    "message": f"Tabla '{table_name}' no encontrada"
                })
            
            logger.error(f"Error en operación de agregación: {e}")
            return json.dumps({"error": f"Error en operación de agregación: {str(e)}"})
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()