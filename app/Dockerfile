FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

# Exponer el puerto para los servicios SOAP
EXPOSE 8080

# Comando para iniciar el servidor de aplicaciones
CMD ["python", "main.py"]