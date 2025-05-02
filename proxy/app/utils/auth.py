#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades de autenticación para el proxy SOA Database
"""

import os
import ipaddress
import logging
import requests
import json
from fastapi import Request, HTTPException, Header
from typing import Optional, List, Dict, Any, Union, Tuple

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URL del servicio de autenticación
AUTH_SERVICE_URL = f"http://{os.getenv('APP_HOST', 'app')}:{os.getenv('APP_PORT', '8080')}/soap"

# Caché para tokens validados (muy simplificado, no usar en producción real)
# En un entorno real, usar Redis u otra solución de caché distribuida
TOKEN_CACHE = {}

def validate_ip(ip: str, allowed_networks: List[ipaddress.IPv4Network]) -> bool:
    """
    Valida si una dirección IP está permitida.
    
    Args:
        ip (str): Dirección IP a validar
        allowed_networks (List[ipaddress.IPv4Network]): Lista de redes permitidas
    
    Returns:
        bool: True si la IP está permitida, False en caso contrario
    """
    try:
        client_ip = ipaddress.ip_address(ip)
        return any(client_ip in network for network in allowed_networks)
    except ValueError:
        logger.error(f"Formato de IP incorrecto: {ip}")
        return False

def validate_token(session_token: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida un token de sesión contra el servicio de autenticación.
    
    Args:
        session_token (str): Token de sesión a validar
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (válido, rol, mensaje)
    """
    # Comprobar si el token está en caché
    if session_token in TOKEN_CACHE:
        if TOKEN_CACHE[session_token]['expires_at'] > time.time():
            return True, TOKEN_CACHE[session_token]['role'], "Sesión válida (caché)"
        else:
            # Token expirado, eliminar de la caché
            del TOKEN_CACHE[session_token]
    
    # Construir solicitud SOAP
    soap_request = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:auth="http://services.soadb.example.com/auth">
       <soapenv:Header/>
       <soapenv:Body>
          <auth:validateToken>
             <session_token>{session_token}</session_token>
          </auth:validateToken>
       </soapenv:Body>
    </soapenv:Envelope>
    """
    
    try:
        # Enviar solicitud al servicio de autenticación
        response = requests.post(
            AUTH_SERVICE_URL,
            data=soap_request,
            headers={
                "Content-Type": "text/xml",
                "SOAPAction": "validateToken"
            },
            timeout=5
        )
        
        # Verificar respuesta
        if response.status_code != 200:
            return False, None, f"Error al validar token: {response.status_code}"
        
        # Extraer resultado de la respuesta SOAP
        # Esto es una simplificación, en un entorno real usar un parser XML adecuado
        response_text = response.text
        start_tag = "<validateTokenResponse>"
        end_tag = "</validateTokenResponse>"
        
        if start_tag in response_text and end_tag in response_text:
            start_index = response_text.find(start_tag) + len(start_tag)
            end_index = response_text.find(end_tag)
            json_str = response_text[start_index:end_index].strip()
            
            try:
                result = json.loads(json_str)
                if result.get("valid", False):
                    session = result.get("session", {})
                    role = session.get("role")
                    
                    # Guardar en caché
                    TOKEN_CACHE[session_token] = {
                        'role': role,
                        'expires_at': time.time() + 3600  # 1 hora
                    }
                    
                    return True, role, "Sesión válida"
                else:
                    return False, None, result.get("message", "Token no válido")
            except json.JSONDecodeError:
                return False, None, "Error al parsear respuesta JSON"
        else:
            return False, None, "Formato de respuesta no reconocido"
    
    except requests.RequestException as e:
        logger.error(f"Error al comunicarse con el servicio de autenticación: {e}")
        return False, None, f"Error de conexión: {str(e)}"

def get_user_role(session_token: str) -> Optional[str]:
    """
    Obtiene el rol de un usuario a partir de su token de sesión.
    
    Args:
        session_token (str): Token de sesión
    
    Returns:
        Optional[str]: Rol del usuario o None si el token no es válido
    """
    valid, role, _ = validate_token(session_token)
    return role if valid else None

def check_permission(session_token: str, required_role: str) -> bool:
    """
    Verifica si un usuario tiene los permisos necesarios.
    
    Args:
        session_token (str): Token de sesión
        required_role (str): Rol requerido
    
    Returns:
        bool: True si tiene permisos, False en caso contrario
    """
    # Jerarquía de roles: admin > editor > viewer
    role_hierarchy = {'admin': 3, 'editor': 2, 'viewer': 1}
    
    valid, role, _ = validate_token(session_token)
    if not valid or not role:
        return False
    
    return role_hierarchy.get(role, 0) >= role_hierarchy.get(required_role, 0)

# Importar time al inicio del módulo
import time