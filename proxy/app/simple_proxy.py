#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servicio Proxy simplificado para la SOA Database
Este módulo actúa como proxy para validar, distribuir y evitar carga innecesaria
en la aplicación principal. También maneja la concurrencia sin usar Prometheus.
"""

import os
import logging
import ipaddress
import requests
import json
import time
import threading
from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
APP_HOST = os.getenv('APP_HOST', 'app')
APP_PORT = os.getenv('APP_PORT', '8080')
ALLOWED_IPS = os.getenv('ALLOWED_IPS', '127.0.0.1')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)

# Semáforo para manejar concurrencia
# Se limita a 100 conexiones simultáneas
max_connections = 100
connection_semaphore = threading.Semaphore(max_connections)

# Diccionario para almacenar las IPs permitidas (caché)
allowed_ip_networks = []

# Diccionario para almacenar métricas básicas
metrics = {
    "requests_total": 0,
    "requests_by_endpoint": {},
    "requests_by_status": {},
    "active_connections": 0,
    "max_connections": max_connections
}

def load_ip_whitelist():
    """Carga la lista de IPs permitidas desde la variable de entorno."""
    global allowed_ip_networks
    allowed_ip_networks = []
    
    # Procesamos la lista de IPs permitidas
    ip_ranges = ALLOWED_IPS.split(',')
    for ip_range in ip_ranges:
        try:
            # Si es un rango CIDR
            if '/' in ip_range:
                network = ipaddress.ip_network(ip_range.strip(), strict=False)
                allowed_ip_networks.append(network)
            # Si es una IP individual
            else:
                ip = ipaddress.ip_address(ip_range.strip())
                # Crear un rango con una sola IP
                network = ipaddress.ip_network(f"{ip}/32", strict=False)
                allowed_ip_networks.append(network)
        except ValueError as e:
            logger.error(f"IP no válida en la configuración: {ip_range}. Error: {e}")

# Cargar IPs al inicio
load_ip_whitelist()

def is_ip_allowed(ip):
    """Comprueba si una IP está en la lista blanca."""
    """try:
        client_ip = ipaddress.ip_address(ip)
        return any(client_ip in network for network in allowed_ip_networks)
    except ValueError:
        logger.error(f"Formato de IP incorrecto: {ip}")
        return False"""
        
    # hacemos que todas las IPs estan autorizadas
    return True

@app.before_request
def before_request():
    """Ejecutar antes de cada solicitud."""
    # Verificar IP
    ip = request.remote_addr
    
    # Si hay X-Forwarded-For, usar esa IP
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        ip = forwarded_for.split(',')[0].strip()
    
    if not is_ip_allowed(ip):
        return jsonify({"error": "Acceso denegado: IP no autorizada"}), 403
    
    # Control de concurrencia
    global metrics
    if not connection_semaphore.acquire(blocking=False):
        return jsonify({"error": "Demasiadas solicitudes. Intente de nuevo más tarde."}), 429
    
    metrics["active_connections"] = max_connections - connection_semaphore._value
    metrics["requests_total"] += 1
    
    # Registrar endpoint
    endpoint = request.path
    metrics["requests_by_endpoint"][endpoint] = metrics["requests_by_endpoint"].get(endpoint, 0) + 1

@app.after_request
def after_request(response):
    """Ejecutar después de cada solicitud."""
    # Liberar el semáforo
    connection_semaphore.release()
    
    # Registrar status code
    status = str(response.status_code)
    metrics["requests_by_status"][status] = metrics["requests_by_status"].get(status, 0) + 1
    
    return response

@app.route('/soap', methods=['POST'])
def soap_proxy():
    """
    Endpoint principal para proxying de peticiones SOAP.
    Recibe solicitudes SOAP, las valida y las reenvía al servicio apropiado.
    """
    # Obtener el body de la petición
    body = request.data
    content_type = request.headers.get("Content-Type", "")
    
    # Validar que es una petición SOAP
    if "text/xml" not in content_type and "application/soap+xml" not in content_type:
        return Response(
            "Content-Type no válido. Debe ser text/xml o application/soap+xml",
            status=415
        )
    
    # Construir la URL de destino en la aplicación
    target_url = f"http://{APP_HOST}:{APP_PORT}/soap"
    
    try:
        # Reenviar la petición al servicio interno
        start_time = time.time()
        response = requests.post(
            target_url,
            data=body,
            headers={
                "Content-Type": content_type,
                "SOAPAction": request.headers.get("SOAPAction", ""),
            },
            timeout=300,
        )
        
        # Registrar tiempo de respuesta
        elapsed_time = time.time() - start_time
        logger.info(f"Petición procesada en {elapsed_time:.4f} segundos")
        
        # Devolver la respuesta del servicio
        return Response(
            response.content,
            status=response.status_code,
            headers={"Content-Type": response.headers.get("Content-Type", "text/xml")}
        )
    
    except requests.RequestException as e:
        logger.error(f"Error al contactar con el servicio: {e}")
        return Response(
            f"No se pudo contactar con el servicio: {str(e)}",
            status=502
        )

@app.route('/wsdl/<service>', methods=['GET'])
def get_wsdl(service):
    """
    Endpoint para obtener el WSDL de un servicio.
    """
    # Validar que el servicio solicitado existe
    valid_services = ["sql", "nosql", "auth", "admin"]
    if service not in valid_services:
        return Response(
            f"Servicio no encontrado. Servicios disponibles: {', '.join(valid_services)}",
            status=404
        )
    
    # Construir la URL de destino en la aplicación
    target_url = f"http://{APP_HOST}:{APP_PORT}/wsdl/{service}"
    
    try:
        # Reenviar la petición al servicio interno
        response = requests.get(
            target_url,
            timeout=10,
        )
        
        # Devolver la respuesta del servicio
        return Response(
            response.content,
            status=response.status_code,
            headers={"Content-Type": "text/xml"}
        )
    
    except requests.RequestException as e:
        logger.error(f"Error al obtener el WSDL del servicio {service}: {e}")
        return Response(
            f"No se pudo obtener el WSDL: {str(e)}",
            status=502
        )

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para comprobar el estado del servicio."""
    return jsonify({"status": "ok", "service": "proxy"})

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Endpoint para obtener métricas de rendimiento."""
    return jsonify(metrics)

# Iniciar el servidor si este script se ejecuta directamente
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, threaded=True)