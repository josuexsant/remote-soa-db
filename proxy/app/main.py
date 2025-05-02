#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servicio Proxy para la SOA Database
Este módulo actúa como proxy para validar, distribuir y evitar carga innecesaria
en la aplicación principal. También maneja la concurrencia.
"""

import os
import logging
import ipaddress
import requests
import json
import time
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import threading
from typing import Optional, Dict, Any, List
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

# Crear aplicación FastAPI
app = FastAPI(title="SOA Database Proxy Service")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def is_ip_allowed(ip: str) -> bool:
    """Comprueba si una IP está en la lista blanca."""
    try:
        client_ip = ipaddress.ip_address(ip)
        return any(client_ip in network for network in allowed_ip_networks)
    except ValueError:
        logger.error(f"Formato de IP incorrecto: {ip}")
        return False

async def ip_whitelist_middleware(request: Request, client_ip: Optional[str] = Header(None, alias="X-Forwarded-For")):
    """Middleware para comprobar si la IP del cliente está en la lista blanca."""
    # Si no hay X-Forwarded-For, usar la IP directa
    ip = client_ip if client_ip else request.client.host
    
    # Si hay varias IPs en X-Forwarded-For, tomar la primera (la del cliente original)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    
    if not is_ip_allowed(ip):
        raise HTTPException(status_code=403, detail="Acceso denegado: IP no autorizada")
    return ip

async def concurrency_middleware(request: Request):
    """Middleware para controlar la concurrencia."""
    if not connection_semaphore.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intente de nuevo más tarde.")
    
    try:
        response = await request.call_next(request)
        return response
    finally:
        connection_semaphore.release()

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware para recopilar métricas de rendimiento."""
    start_time = time.time()
    
    global metrics
    metrics["requests_total"] += 1
    metrics["active_connections"] = max_connections - connection_semaphore._value
    
    # Registrar por endpoint
    endpoint = request.url.path
    metrics["requests_by_endpoint"][endpoint] = metrics["requests_by_endpoint"].get(endpoint, 0) + 1
    
    response = await call_next(request)
    
    # Registrar por status
    status = response.status_code
    metrics["requests_by_status"][str(status)] = metrics["requests_by_status"].get(str(status), 0) + 1
    
    # Registrar latencia
    latency = time.time() - start_time
    logger.info(f"Solicitud: {request.method} {endpoint} - Status: {status} - Tiempo: {latency:.4f}s")
    
    return response

@app.post("/soap", dependencies=[Depends(ip_whitelist_middleware)])
async def soap_proxy(request: Request):
    """
    Endpoint principal para proxying de peticiones SOAP.
    Recibe solicitudes SOAP, las valida y las reenvía al servicio apropiado.
    """
    # Obtener el body de la petición
    body = await request.body()
    content_type = request.headers.get("Content-Type", "")
    
    # Validar que es una petición SOAP
    if "text/xml" not in content_type and "application/soap+xml" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type no válido. Debe ser text/xml o application/soap+xml"
        )
    
    # Construir la URL de destino en la aplicación
    target_url = f"http://{APP_HOST}:{APP_PORT}/soap"
    
    try:
        # Reenviar la petición al servicio interno
        response = requests.post(
            target_url,
            data=body,
            headers={
                "Content-Type": content_type,
                "SOAPAction": request.headers.get("SOAPAction", ""),
            },
            timeout=30,
        )
        
        # Devolver la respuesta del servicio
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={"Content-Type": response.headers.get("Content-Type", "text/xml")}
        )
    
    except requests.RequestException as e:
        logger.error(f"Error al contactar con el servicio: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo contactar con el servicio: {str(e)}"
        )

@app.get("/wsdl/{service}", dependencies=[Depends(ip_whitelist_middleware)])
async def get_wsdl(service: str, request: Request):
    """
    Endpoint para obtener el WSDL de un servicio.
    """
    # Validar que el servicio solicitado existe
    valid_services = ["sql", "nosql", "auth", "admin"]
    if service not in valid_services:
        raise HTTPException(
            status_code=404,
            detail=f"Servicio no encontrado. Servicios disponibles: {', '.join(valid_services)}"
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
            content=response.content,
            status_code=response.status_code,
            headers={"Content-Type": "text/xml"}
        )
    
    except requests.RequestException as e:
        logger.error(f"Error al obtener el WSDL del servicio {service}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo obtener el WSDL: {str(e)}"
        )

@app.get("/health", dependencies=[Depends(ip_whitelist_middleware)])
async def health_check():
    """Endpoint para comprobar el estado del servicio."""
    return {"status": "ok", "service": "proxy"}

@app.get("/metrics", dependencies=[Depends(ip_whitelist_middleware)])
async def get_metrics():
    """Endpoint para obtener métricas de rendimiento."""
    return metrics

if __name__ == "__main__":
    # Iniciar el servidor principal
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)