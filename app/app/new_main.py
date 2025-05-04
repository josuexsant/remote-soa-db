#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor principal de la SOA Database
Este módulo gestiona los servicios SOAP para gestionar bases de datos SQL y NoSQL.
"""

import os
import sys
import logging
from dotenv import load_dotenv
from soap_service import app as soap_app

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

# Función principal para iniciar el servidor
if __name__ == "__main__":
    logger.info(f"Iniciando servidor en {SERVICE_HOST}:{SERVICE_PORT}")
    soap_app.run(host=SERVICE_HOST, port=SERVICE_PORT)