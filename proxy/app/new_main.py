#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor Proxy para la SOA Database
Este módulo inicia el proxy simplificado para evitar los problemas con Prometheus.
"""

import os
import logging
from dotenv import load_dotenv
from simple_proxy import app

# Cargar variables de entorno
load_dotenv()

# Configuración
PROXY_HOST = os.getenv('PROXY_HOST', '0.0.0.0')
PROXY_PORT = int(os.getenv('PROXY_PORT', '8000'))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Función principal para iniciar el servidor
if __name__ == "__main__":
    logger.info(f"Iniciando servidor proxy en {PROXY_HOST}:{PROXY_PORT}")
    app.run(host=PROXY_HOST, port=PROXY_PORT, threaded=True)