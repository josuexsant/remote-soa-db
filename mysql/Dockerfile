FROM mysql:8.0

# Los scripts en este directorio se ejecutarán automáticamente al iniciar el contenedor
COPY ./init /docker-entrypoint-initdb.d/

# Configuraciones opcionales para MySQL
ENV MYSQL_ROOT_PASSWORD=rootpassword
ENV MYSQL_DATABASE=dbservice

# Exponer el puerto estándar de MySQL
EXPOSE 3306