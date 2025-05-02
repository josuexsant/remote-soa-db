FROM mongo:5.0

# Los scripts en este directorio se ejecutarán automáticamente al iniciar el contenedor
COPY ./init /docker-entrypoint-initdb.d/

# Variables de entorno para MongoDB
ENV MONGO_INITDB_ROOT_USERNAME=root
ENV MONGO_INITDB_ROOT_PASSWORD=rootpassword
ENV MONGO_INITDB_DATABASE=dbservice

# Exponer el puerto estándar de MongoDB
EXPOSE 27017