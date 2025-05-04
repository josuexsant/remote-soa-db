FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

# Exponer el puerto que usará el proxy
EXPOSE 8000

# Comando para iniciar el proxy
# Cambiamos de main.py a new_main.py para usar la implementación nueva
CMD ["python", "new_main.py"]