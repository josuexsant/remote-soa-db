# Guía de Pruebas con SOAP UI para SOA Database

Esta guía te ayudará a configurar un proyecto de pruebas en SOAP UI para interactuar con los servicios SOAP de la SOA Database.

## Requisitos Previos

1. Tener SOAP UI instalado. Puedes descargarlo desde [SoapUI.org](https://www.soapui.org/downloads/soapui/)
2. Tener el sistema SOA Database en funcionamiento (los contenedores Docker deben estar ejecutándose)

## Configuración Inicial

### 1. Crear un Nuevo Proyecto en SOAP UI

1. Abre SOAP UI
2. Haz clic en "File" > "New SOAP Project"
3. Asigna un nombre al proyecto (ej. "SOA Database")
4. Marca la opción "Create sample requests for all operations"
5. Haz clic en "OK"

### 2. Importar los WSDLs

Para cada servicio (Auth, SQL, NoSQL, Admin), debes importar su WSDL:

1. Haz clic derecho en el proyecto creado
2. Selecciona "Add WSDL"
3. Ingresa la URL del WSDL:
   - Auth Service: `http://localhost:8000/wsdl/auth`
   - SQL Service: `http://localhost:8000/wsdl/sql`
   - NoSQL Service: `http://localhost:8000/wsdl/nosql`
   - Admin Service: `http://localhost:8000/wsdl/admin`
4. Haz clic en "OK"

Repite este proceso para cada servicio.

## Flujo de Pruebas

Para probar el sistema de forma completa, sigue este flujo de operaciones:

### 1. Obtener Información de los Servicios

Comienza verificando que todos los servicios estén disponibles:

1. Abre la operación `listAll` del servicio Admin
2. Haz clic en el botón "Submit Request" (triángulo verde)
3. Deberías recibir una respuesta JSON con todos los servicios disponibles y sus métodos

### 2. Registrar un Usuario y Obtener un Token de Sesión

Para interactuar con el resto de los servicios, necesitas un token de sesión:

1. **Registro de usuario**:
   - Abre la operación `register` del servicio Auth
   - Edita la solicitud para incluir tus datos:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:auth="http://services.soadb.example.com/auth">
      <soapenv:Header/>
      <soapenv:Body>
         <auth:register>
            <username>test_user</username>
            <email>test@example.com</email>
            <provider>google</provider>
         </auth:register>
      </soapenv:Body>
   </soapenv:Envelope>
   ```
   - Haz clic en "Submit Request"

2. **Iniciar sesión**:
   - Para las pruebas, puedes usar un flujo OAuth2 simplificado:
   - En un entorno real, deberías obtener un código de autorización de Google, Facebook o Microsoft
   - Para pruebas, modifica la operación `login` del servicio Auth:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:auth="http://services.soadb.example.com/auth">
      <soapenv:Header/>
      <soapenv:Body>
         <auth:login>
            <provider>google</provider>
            <authorization_code>test_code</authorization_code>
            <redirect_uri>http://localhost:8080/callback</redirect_uri>
         </auth:login>
      </soapenv:Body>
   </soapenv:Envelope>
   ```
   - En la respuesta, obtendrás un token de sesión. **Cópialo** ya que lo necesitarás para todas las operaciones siguientes.

### 3. Probar Operaciones SQL

Una vez que tengas un token de sesión, puedes probar las operaciones SQL:

1. **Crear base de datos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
      <soapenv:Header/>
      <soapenv:Body>
         <sql:createDatabase>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_db</database_name>
         </sql:createDatabase>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

2. **Crear tabla**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
      <soapenv:Header/>
      <soapenv:Body>
         <sql:createTable>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_db</database_name>
            <table_name>empleados</table_name>
            <fields_json>[
               {"name": "id", "type": "INT", "nullable": false, "auto_increment": true, "primary_key": true},
               {"name": "nombre", "type": "VARCHAR(100)", "nullable": false},
               {"name": "departamento", "type": "VARCHAR(50)", "nullable": true},
               {"name": "salario", "type": "DECIMAL(10,2)", "nullable": false}
            ]</fields_json>
         </sql:createTable>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

3. **Insertar datos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
      <soapenv:Header/>
      <soapenv:Body>
         <sql:insert>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_db</database_name>
            <table_name>empleados</table_name>
            <data_json>[
               {"nombre": "Ana García", "departamento": "Ventas", "salario": 35000},
               {"nombre": "Luis Rodríguez", "departamento": "IT", "salario": 42000},
               {"nombre": "Carmen Pérez", "departamento": "Recursos Humanos", "salario": 38500},
               {"nombre": "Javier López", "departamento": "IT", "salario": 45000}
            ]</data_json>
         </sql:insert>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

4. **Consultar datos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
      <soapenv:Header/>
      <soapenv:Body>
         <sql:select>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_db</database_name>
            <table_name>empleados</table_name>
            <fields>id, nombre, departamento, salario</fields>
         </sql:select>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

5. **Realizar una agregación**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
      <soapenv:Header/>
      <soapenv:Body>
         <sql:aggregate>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_db</database_name>
            <table_name>empleados</table_name>
            <operation>AVG</operation>
            <field>salario</field>
            <group_by>departamento</group_by>
         </sql:aggregate>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

### 4. Probar Operaciones NoSQL

También puedes probar las operaciones NoSQL:

1. **Crear base de datos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
      <soapenv:Header/>
      <soapenv:Body>
         <nosql:createDatabase>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_nosql</database_name>
         </nosql:createDatabase>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

2. **Crear colección**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
      <soapenv:Header/>
      <soapenv:Body>
         <nosql:createCollection>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_nosql</database_name>
            <collection_name>productos</collection_name>
         </nosql:createCollection>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

3. **Insertar documentos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
      <soapenv:Header/>
      <soapenv:Body>
         <nosql:insertDocument>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_nosql</database_name>
            <collection_name>productos</collection_name>
            <documents_json>[
               {
                  "nombre": "Laptop Pro",
                  "precio": 1299.99,
                  "categoria": "Electrónica",
                  "especificaciones": {
                     "procesador": "Intel i7",
                     "ram": "16GB",
                     "almacenamiento": "512GB SSD"
                  },
                  "colores_disponibles": ["plata", "gris espacial", "oro"]
               },
               {
                  "nombre": "Monitor UltraWide",
                  "precio": 499.99,
                  "categoria": "Electrónica",
                  "especificaciones": {
                     "tamaño": "34 pulgadas",
                     "resolución": "3440x1440",
                     "tipo_panel": "IPS"
                  },
                  "colores_disponibles": ["negro"]
               }
            ]</documents_json>
         </nosql:insertDocument>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

4. **Buscar documentos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
      <soapenv:Header/>
      <soapenv:Body>
         <nosql:findDocument>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_nosql</database_name>
            <collection_name>productos</collection_name>
            <filter_json>{"categoria": "Electrónica"}</filter_json>
         </nosql:findDocument>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

5. **Agregación de documentos**:
   ```xml
   <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
      <soapenv:Header/>
      <soapenv:Body>
         <nosql:aggregateDocuments>
            <session_token>TU_TOKEN_DE_SESIÓN</session_token>
            <database_name>test_nosql</database_name>
            <collection_name>productos</collection_name>
            <pipeline_json>[
               {"$group": {"_id": "$categoria", "precio_promedio": {"$avg": "$precio"}, "cantidad": {"$sum": 1}}}
            ]</pipeline_json>
         </nosql:aggregateDocuments>
      </soapenv:Body>
   </soapenv:Envelope>
   ```

### 5. Cerrar Sesión

Al finalizar las pruebas, es buena práctica cerrar la sesión:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:auth="http://services.soadb.example.com/auth">
   <soapenv:Header/>
   <soapenv:Body>
      <auth:logout>
         <session_token>TU_TOKEN_DE_SESIÓN</session_token>
      </auth:logout>
   </soapenv:Body>
</soapenv:Envelope>
```

## Probando la Arquitectura Multi-Máquina

Para probar el sistema en un entorno de varias máquinas:

### Máquina 1 (Servidor)

1. Asegúrate de que todos los contenedores estén en ejecución:
   ```bash
   docker-compose ps
   ```

2. Verifica que los servicios son accesibles desde la red:
   ```bash
   curl http://localhost:8000/health
   ```

3. Obtén la dirección IP de la máquina 1:
   ```bash
   # En Linux
   ip addr show

   # En Windows
   ipconfig
   ```

### Máquinas 2 y 3 (Clientes)

1. En SOAP UI, configura los endpoints para que apunten a la dirección IP de la máquina 1:
   - Haz doble clic en cada servicio
   - Cambia la URL base a `http://[IP_MÁQUINA_1]:8000/soap`

2. Ejecuta las mismas pruebas que hiciste anteriormente
3. Verifica que ambas máquinas pueden interactuar simultáneamente con el sistema

## Solución de Problemas

### Error "Cannot connect to endpoint"
- Verifica que los contenedores estén en ejecución
- Comprueba si hay algún firewall bloqueando las conexiones
- Asegúrate de que la IP esté correctamente configurada

### Error "Invalid token" o "Session expired"
- La sesión puede haber caducado (duran 24 horas por defecto)
- Inicia sesión nuevamente para obtener un nuevo token

### Error "Permission denied"
- El usuario puede no tener los permisos necesarios para la operación
- Verifica el rol del usuario (admin, editor, viewer)

### Error de conexión a bases de datos
- Verifica que los contenedores de MySQL y MongoDB estén en ejecución
- Comprueba los logs para ver si hay algún error específico:
  ```bash
  docker-compose logs mysql
  docker-compose logs mongodb
  ```

## Recomendaciones para Pruebas Avanzadas

1. **Pruebas de Concurrencia**:
   - Utiliza la función TestRunner de SOAP UI para ejecutar múltiples solicitudes simultáneamente

2. **Pruebas de Seguridad**:
   - Intenta acceder a recursos sin un token válido
   - Intenta realizar operaciones con un rol insuficiente

3. **Pruebas de Recuperación**:
   - Detén uno de los contenedores y verifica cómo responde el sistema
   - Reinicia los contenedores y verifica que los datos persisten

4. **Pruebas del Patrón Saga**:
   - Intenta una operación compleja que involucre múltiples servicios
   - Fuerza un error en algún punto para verificar la compensación

## Conclusión

Esta guía te ha mostrado cómo probar los diferentes servicios y operaciones de la SOA Database utilizando SOAP UI. Recuerda que este es un entorno de pruebas simplificado y que en un entorno de producción se requerirían configuraciones adicionales de seguridad y rendimiento.