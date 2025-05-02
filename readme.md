# Documentación del Servicio SOA Database

## Descripción General

SOA Database es un servicio de bases de datos remoto implementado utilizando una arquitectura orientada a servicios (SOA). El sistema permite a los usuarios gestionar bases de datos SQL (MySQL) y NoSQL (MongoDB) de forma transparente, a través de una interfaz SOAP, sin necesidad de tener instalado ningún sistema gestor de bases de datos.

## Arquitectura

El sistema está compuesto por los siguientes componentes:

1. **Proxy**: Actúa como punto de entrada al sistema, gestionando la validación, distribución y balanceo de carga. Es responsable de manejar la concurrencia y realizar IP Whitelisting.

2. **Aplicación**: Contiene los servicios web SOAP que implementan la lógica de negocio:
   - Servicio de Autenticación (Auth Service)
   - Servicio SQL (SQL Service)
   - Servicio NoSQL (NoSQL Service)
   - Servicio de Administración (Admin Service)

3. **Bases de Datos**:
   - MySQL: Almacena datos estructurados
   - MongoDB: Almacena datos no estructurados

## Tecnologías Utilizadas

- **Python**: Lenguaje de programación principal
- **Spyne**: Framework para implementar servicios SOAP
- **Flask**: Servidor web
- **MySQL**: Sistema de gestión de bases de datos relacionales
- **MongoDB**: Sistema de gestión de bases de datos NoSQL
- **Docker**: Contenedorización de la aplicación
- **OAuth2**: Autenticación mediante proveedores externos

## Estructura SOAP

### Definición de SOAP

SOAP (Simple Object Access Protocol) es un protocolo estándar de comunicación basado en XML que permite el intercambio de información estructurada entre servicios web. En nuestro sistema, SOAP se utiliza para todas las comunicaciones entre el cliente y los servicios.

#### Formato de los Mensajes SOAP

Un mensaje SOAP consta de:

- **Envelope (Sobre)**: El elemento raíz que identifica el documento XML como un mensaje SOAP
- **Header (Cabecera)**: Contiene información específica de la aplicación (ej. autenticación)
- **Body (Cuerpo)**: Contiene la información a transmitir
- **Fault (Fallo)**: Elemento opcional para reportar errores

Ejemplo de un mensaje SOAP para crear una base de datos:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header>
      <auth>
         <session_token>3f7d5ae3-2a4c-4a00-8d06-28b3b5e3e599</session_token>
      </auth>
   </soapenv:Header>
   <soapenv:Body>
      <sql:createDatabase>
         <session_token>3f7d5ae3-2a4c-4a00-8d06-28b3b5e3e599</session_token>
         <database_name>mi_nueva_db</database_name>
      </sql:createDatabase>
   </soapenv:Body>
</soapenv:Envelope>
```

## Estructura WSDL

### Definición de WSDL

WSDL (Web Services Description Language) es un formato XML utilizado para describir servicios web. Define la interfaz pública de un servicio, especificando los métodos disponibles, sus parámetros y tipos de retorno.

En nuestro sistema, cada servicio (Auth, SQL, NoSQL, Admin) dispone de su propio WSDL, lo que permite la evolución independiente de cada componente.

#### Componentes de un WSDL

- **Types**: Define los tipos de datos utilizados
- **Message**: Define los mensajes intercambiados
- **PortType**: Define las operaciones (métodos) disponibles
- **Binding**: Define el protocolo de comunicación
- **Service**: Define los puntos finales del servicio

Ejemplo simplificado de WSDL para el servicio SQL:

```xml
<definitions name="SQLService" 
            targetNamespace="http://services.soadb.example.com/sql"
            xmlns="http://schemas.xmlsoap.org/wsdl/"
            xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
            xmlns:tns="http://services.soadb.example.com/sql"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema">

    <types>
        <schema targetNamespace="http://services.soadb.example.com/sql"
                xmlns="http://www.w3.org/2001/XMLSchema">
            <!-- Definición de tipos -->
        </schema>
    </types>

    <message name="createDatabaseRequest">
        <part name="session_token" type="xsd:string"/>
        <part name="database_name" type="xsd:string"/>
    </message>
    <message name="createDatabaseResponse">
        <part name="result" type="xsd:string"/>
    </message>

    <portType name="SQLPortType">
        <operation name="createDatabase">
            <input message="tns:createDatabaseRequest"/>
            <output message="tns:createDatabaseResponse"/>
        </operation>
        <!-- Más operaciones -->
    </portType>

    <binding name="SQLBinding" type="tns:SQLPortType">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="createDatabase">
            <soap:operation soapAction="createDatabase"/>
            <input>
                <soap:body use="literal"/>
            </input>
            <output>
                <soap:body use="literal"/>
            </output>
        </operation>
        <!-- Más operaciones -->
    </binding>

    <service name="SQLService">
        <port name="SQLPort" binding="tns:SQLBinding">
            <soap:address location="http://localhost:8080/soap"/>
        </port>
    </service>
</definitions>
```

## Estructura BPEL

### Definición de BPEL

BPEL (Business Process Execution Language) es un lenguaje basado en XML diseñado para la composición, orquestación y coordinación de servicios web. Permite definir procesos de negocio complejos que involucran múltiples servicios.

En nuestro sistema, BPEL se utiliza para implementar el patrón Saga, que permite gestionar transacciones distribuidas con compensaciones.

#### Ejemplo de Proceso BPEL para Transacción Distribuida

Ejemplo simplificado de un proceso BPEL para crear una tabla en una base de datos con compensación en caso de error:

```xml
<process name="CreateTableProcess"
        targetNamespace="http://example.com/bpel/createTable"
        xmlns="http://docs.oasis-open.org/wsbpel/2.0/process/executable">

    <partnerLinks>
        <partnerLink name="sqlService" partnerLinkType="sql:SQLLinkType" partnerRole="SQLProvider"/>
    </partnerLinks>

    <variables>
        <variable name="request" messageType="sql:createTableRequest"/>
        <variable name="response" messageType="sql:createTableResponse"/>
        <variable name="faultInfo" messageType="sql:faultMessage"/>
    </variables>

    <sequence>
        <receive partnerLink="sqlService" operation="createTable" variable="request" createInstance="yes"/>
        
        <scope>
            <faultHandlers>
                <catch faultName="sql:databaseError" faultVariable="faultInfo">
                    <!-- Compensación -->
                    <compensate/>
                </catch>
            </faultHandlers>
            
            <sequence>
                <!-- Actividad principal -->
                <invoke partnerLink="sqlService" operation="createTable" inputVariable="request" outputVariable="response"/>
                
                <reply partnerLink="sqlService" operation="createTable" variable="response"/>
            </sequence>
            
            <compensationHandler>
                <!-- Lógica de compensación -->
                <invoke partnerLink="sqlService" operation="cleanupFailedTable" inputVariable="request"/>
            </compensationHandler>
        </scope>
    </sequence>
</process>
```

## Seguridad

El sistema implementa las siguientes medidas de seguridad:

1. **Autenticación**: Mediante OAuth2, utilizando proveedores externos (Google, Facebook, Microsoft).
2. **Autorización**: Sistema de roles (Admin, Editor, Viewer) con permisos diferenciados.
3. **Sesiones**: Las sesiones se almacenan en la base de datos con tiempo de caducidad.
4. **IP Whitelisting**: Restricción de acceso por IP en el proxy.
5. **HTTPS**: Soporte para comunicaciones seguras.

## Pruebas y Monitoreo

1. **Pruebas Unitarias**: Verifican la lógica de negocio de cada servicio.
2. **Métricas**: El proxy recopila métricas de rendimiento que son expuestas en un endpoint dedicado.
3. **Logs**: Cada componente genera logs detallados para facilitar la depuración.

## Uso del Servicio

### Consulta de Servicios Disponibles

Para conocer todos los servicios disponibles, se puede utilizar el método `listAll` del servicio Admin:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:adm="http://services.soadb.example.com/admin">
   <soapenv:Header/>
   <soapenv:Body>
      <adm:listAll/>
   </soapenv:Body>
</soapenv:Envelope>
```

### Autenticación

Para autenticarse mediante OAuth2:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:auth="http://services.soadb.example.com/auth">
   <soapenv:Header/>
   <soapenv:Body>
      <auth:login>
         <provider>google</provider>
         <authorization_code>CODE_FROM_GOOGLE</authorization_code>
         <redirect_uri>http://myapp.com/callback</redirect_uri>
      </auth:login>
   </soapenv:Body>
</soapenv:Envelope>
```

### Operaciones con Bases de Datos SQL

Ejemplo de creación de una tabla:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header/>
   <soapenv:Body>
      <sql:createTable>
         <session_token>YOUR_SESSION_TOKEN</session_token>
         <database_name>my_database</database_name>
         <table_name>users</table_name>
         <fields_json>[
            {"name": "id", "type": "INT", "nullable": false, "auto_increment": true, "primary_key": true},
            {"name": "name", "type": "VARCHAR(100)", "nullable": false},
            {"name": "email", "type": "VARCHAR(255)", "nullable": false, "unique": true},
            {"name": "created_at", "type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
         ]</fields_json>
      </sql:createTable>
   </soapenv:Body>
</soapenv:Envelope>
```

### Operaciones con Bases de Datos NoSQL

Ejemplo de inserción de un documento:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:nosql="http://services.soadb.example.com/nosql">
   <soapenv:Header/>
   <soapenv:Body>
      <nosql:insertDocument>
         <session_token>YOUR_SESSION_TOKEN</session_token>
         <database_name>my_database</database_name>
         <collection_name>users</collection_name>
         <documents_json>[
            {
               "name": "John Doe",
               "email": "john@example.com",
               "age": 30,
               "address": {
                  "city": "New York",
                  "country": "USA"
               },
               "interests": ["programming", "music", "sports"]
            }
         ]</documents_json>
      </nosql:insertDocument>
   </soapenv:Body>
</soapenv:Envelope>
```

## Despliegue

El sistema está contenerizado utilizando Docker, con un contenedor para cada componente:

1. **Proxy**: Gestiona la validación, distribución y balanceo de carga.
2. **Aplicación**: Contiene los servicios web SOAP.
3. **MySQL**: Base de datos relacional.
4. **MongoDB**: Base de datos NoSQL.

El despliegue se realiza mediante Docker Compose, que orquesta todos los contenedores y configura la red.

### Requisitos de Hardware y Software

- Docker y Docker Compose
- Al menos 4 GB de RAM
- Al menos 10 GB de espacio en disco
- Conexión a Internet (para la autenticación OAuth2)

### Instrucciones de Despliegue

1. Clonar el repositorio
2. Configurar las variables de entorno (ver `.env.example`)
3#   r e m o t e - s o a - d b  
 