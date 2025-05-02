#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Funciones auxiliares para la SOA Database
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """
    Crea una respuesta de error en formato JSON.
    
    Args:
        message (str): Mensaje de error
        status_code (int, optional): Código de estado HTTP. Por defecto 400.
    
    Returns:
        Dict[str, Any]: Respuesta de error en formato JSON
    """
    return {
        "success": False,
        "error": {
            "message": message,
            "status_code": status_code
        }
    }

def create_success_response(data: Any = None, message: str = "Operación exitosa") -> Dict[str, Any]:
    """
    Crea una respuesta de éxito en formato JSON.
    
    Args:
        data (Any, optional): Datos a incluir en la respuesta. Por defecto None.
        message (str, optional): Mensaje de éxito. Por defecto "Operación exitosa".
    
    Returns:
        Dict[str, Any]: Respuesta de éxito en formato JSON
    """
    response = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response["data"] = data
    
    return response

def format_datetime(dt: Optional[Union[datetime, str]] = None) -> str:
    """
    Formatea una fecha y hora en formato ISO 8601.
    
    Args:
        dt (Optional[Union[datetime, str]], optional): Fecha y hora a formatear.
            Si es None, se utiliza la fecha y hora actual.
    
    Returns:
        str: Fecha y hora formateada
    """
    if dt is None:
        dt = datetime.now()
    elif isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            logger.error(f"Formato de fecha y hora no válido: {dt}")
            dt = datetime.now()
    
    return dt.isoformat()

def is_valid_identifier(name: str) -> bool:
    """
    Verifica si un nombre es un identificador válido para bases de datos o tablas.
    
    Args:
        name (str): Nombre a verificar
    
    Returns:
        bool: True si es válido, False en caso contrario
    """
    # Patrón para nombres válidos (alfanuméricos y guiones bajos)
    pattern = r'^[a-zA-Z0-9_]+$'
    
    # Verificar que el nombre no esté vacío y cumpla con el patrón
    if not name or not re.match(pattern, name):
        return False
    
    # Verificar que no comience con un número
    if name[0].isdigit():
        return False
    
    # Verificar que no sea una palabra reservada
    reserved_words = [
        'add', 'all', 'alter', 'and', 'any', 'as', 'asc', 'backup', 'between',
        'case', 'check', 'column', 'constraint', 'create', 'database', 'default',
        'delete', 'desc', 'distinct', 'drop', 'exec', 'exists', 'foreign', 'from',
        'full', 'group', 'having', 'in', 'index', 'inner', 'insert', 'is', 'join',
        'key', 'left', 'like', 'limit', 'not', 'null', 'or', 'order', 'outer',
        'primary', 'procedure', 'right', 'rownum', 'select', 'set', 'table', 'top',
        'truncate', 'union', 'unique', 'update', 'values', 'view', 'where'
    ]
    
    if name.lower() in reserved_words:
        return False
    
    return True

def parse_json_safely(json_str: str) -> Dict[str, Any]:
    """
    Parsea una cadena JSON de forma segura.
    
    Args:
        json_str (str): Cadena JSON a parsear
    
    Returns:
        Dict[str, Any]: Objeto JSON parseado o diccionario vacío en caso de error
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON: {e}")
        return {}