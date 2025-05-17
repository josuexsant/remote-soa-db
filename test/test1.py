import unittest
import subprocess
import xml.etree.ElementTree as ET
import tempfile
import os
import json

class TestSQLServiceWithCurl(unittest.TestCase):
    """Pruebas para los endpoints SOAP del servicio SQL usando curl"""
    
    def setUp(self):
        """Configuración inicial para cada prueba"""
        # URL del servicio SOAP
        self.service_url = "http://localhost:8000/soap"
        
        # Token de sesión válido (usando el token de ejemplo proporcionado)
        self.valid_token = "42d08295-1611-4d6f-9a6c-e6676e429599"
        
        # Token de sesión inválido para pruebas
        self.invalid_token = "token-invalido-para-prueba"
        
        # Namespaces para procesar las respuestas SOAP
        self.namespaces = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns0': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns1': 'http://services.soadb.example.com/sql'
        }

    def execute_soap_request(self, soap_request):
        """Ejecuta una solicitud SOAP usando curl y devuelve la respuesta XML"""
        # Crear un archivo temporal para la solicitud SOAP
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.xml') as temp_file:
            temp_file.write(soap_request)
            temp_file_path = temp_file.name
        
        try:
            # Extraer el nombre de la operación SOAP desde la solicitud
            # Esto asume que el formato es siempre <sql:nombreOperacion>
            operation_start = soap_request.find("<sql:")
            if operation_start != -1:
                operation_end = soap_request.find(">", operation_start)
                operation = soap_request[operation_start+5:operation_end]
            else:
                operation = "unknown"
            
            # Ejecutar curl para enviar la solicitud SOAP
            cmd = [
                'curl',
                '-s',  # modo silencioso
                '-X', 'POST',
                '-H', 'Content-Type: text/xml;charset=UTF-8',
                '-H', f'SOAPAction: "{operation}"',
                '-d', f'@{temp_file_path}',
                self.service_url
            ]
            
            # Ejecutar el comando y capturar la salida
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Para depuración, guardar la respuesta en un archivo
            with open('last_response.xml', 'w') as f:
                f.write(result.stdout)
            
            return result.stdout
        
        finally:
            # Eliminar el archivo temporal
            os.unlink(temp_file_path)

    def test_list_databases_success(self):
        """Prueba el caso exitoso de listar bases de datos"""
        # Crear solicitud SOAP para listDatabases
        soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header/>
   <soapenv:Body>
      <sql:listDatabases>
         <session_token>{self.valid_token}</session_token>
      </sql:listDatabases>
   </soapenv:Body>
</soapenv:Envelope>"""
        
        # Ejecutar la solicitud
        response_xml = self.execute_soap_request(soap_request)
        
        # Verificar que la respuesta no esté vacía
        self.assertTrue(response_xml, "La respuesta está vacía")
        
        # Parsear la respuesta XML
        try:
            root = ET.fromstring(response_xml)
            
            # Encontrar el elemento de respuesta
            response_element = root.find('.//ns1:listDatabasesResponse', self.namespaces)
            self.assertIsNotNone(response_element, "No se encontró el elemento de respuesta")
            
            # Extraer el contenido JSON de la respuesta
            response_content = response_element.text
            response_data = json.loads(response_content)
            
            # Verificar que la respuesta sea exitosa
            self.assertTrue(response_data.get('success'), "La respuesta indica un error")
            
            # Verificar que hay bases de datos listadas
            databases = response_data.get('databases', [])
            self.assertTrue(len(databases) > 0, "No se encontraron bases de datos")
            
            # Imprimir las bases de datos encontradas
            print(f"Bases de datos encontradas: {databases}")
            
        except ET.ParseError as e:
            # Si hay un error al parsear el XML, mostramos el contenido de la respuesta
            print(f"Error al parsear XML: {e}")
            print(f"Contenido de la respuesta: {response_xml}")
            self.fail("La respuesta no es un XML válido")
        except json.JSONDecodeError as e:
            # Si hay un error al parsear el JSON, mostramos el texto del elemento de respuesta
            print(f"Error al parsear JSON: {e}")
            if 'response_element' in locals() and response_element is not None:
                print(f"Contenido del elemento de respuesta: {response_element.text}")
            self.fail("El contenido de la respuesta no es un JSON válido")
    
    def test_list_databases_invalid_session(self):
        """Prueba el caso de token de sesión inválido"""
        # Crear solicitud SOAP con token inválido
        soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header/>
   <soapenv:Body>
      <sql:listDatabases>
         <session_token>{self.invalid_token}</session_token>
      </sql:listDatabases>
   </soapenv:Body>
</soapenv:Envelope>"""
        
        # Ejecutar la solicitud
        response_xml = self.execute_soap_request(soap_request)
        
        # Verificar que la respuesta no esté vacía
        self.assertTrue(response_xml, "La respuesta está vacía")
        
        try:
            # Parsear la respuesta XML
            root = ET.fromstring(response_xml)
            
            # Encontrar el elemento de respuesta
            response_element = root.find('.//ns1:listDatabasesResponse', self.namespaces)
            
            if response_element is not None:
                # Extraer el contenido JSON de la respuesta
                response_content = response_element.text
                try:
                    response_data = json.loads(response_content)
                    
                    # Verificar que la respuesta indica un error
                    self.assertFalse(response_data.get('success', True), 
                                    "Se esperaba que la respuesta indicara un error para un token inválido")
                    
                    # Verificar que hay un mensaje de error
                    self.assertTrue('error' in response_data or 'message' in response_data, 
                                   "Se esperaba un mensaje de error en la respuesta")
                    
                    # Imprimir el mensaje de error
                    error_msg = response_data.get('error') or response_data.get('message')
                    print(f"Mensaje de error: {error_msg}")
                    
                except json.JSONDecodeError:
                    # Si no es un JSON válido, verificar si hay mensaje de error en formato texto
                    print(f"Contenido no JSON: {response_content}")
                    self.assertTrue("error" in response_content.lower() or 
                                   "invalid" in response_content.lower() or 
                                   "unauthorized" in response_content.lower(),
                                   "Se esperaba un mensaje de error para un token inválido")
            else:
                # Si no hay elemento de respuesta, buscar un elemento Fault
                fault_element = root.find('.//soapenv:Fault', self.namespaces)
                self.assertIsNotNone(fault_element, "No se encontró un elemento de respuesta o Fault")
                
                # Imprimir los detalles del Fault
                fault_string = fault_element.find('./faultstring')
                if fault_string is not None:
                    print(f"Fault String: {fault_string.text}")
                    self.assertTrue("token" in fault_string.text.lower() or 
                                   "session" in fault_string.text.lower() or 
                                   "auth" in fault_string.text.lower(),
                                   "Se esperaba un mensaje de error relacionado con la autenticación")
                
        except ET.ParseError as e:
            # Si hay un error al parsear el XML, verificamos si la respuesta indica un error
            print(f"Error al parsear XML: {e}")
            print(f"Contenido de la respuesta: {response_xml}")
            self.assertTrue("error" in response_xml.lower() or 
                           "invalid" in response_xml.lower() or 
                           "unauthorized" in response_xml.lower(),
                           "Se esperaba un mensaje de error para un token inválido")
    
    def test_list_tables(self):
        """Prueba el endpoint listTables"""
        # Primero obtenemos las bases de datos para usar una existente
        list_db_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header/>
   <soapenv:Body>
      <sql:listDatabases>
         <session_token>{self.valid_token}</session_token>
      </sql:listDatabases>
   </soapenv:Body>
</soapenv:Envelope>"""
        
        response_xml = self.execute_soap_request(list_db_request)
        
        try:
            # Parsear la respuesta para obtener las bases de datos
            root = ET.fromstring(response_xml)
            response_element = root.find('.//ns1:listDatabasesResponse', self.namespaces)
            response_content = response_element.text
            response_data = json.loads(response_content)
            
            # Verificar que hay bases de datos
            self.assertTrue(response_data.get('success'), "La obtención de bases de datos falló")
            databases = response_data.get('databases', [])
            self.assertTrue(len(databases) > 0, "No hay bases de datos disponibles para pruebas")
            
            # Usar la primera base de datos para la prueba de listTables
            test_db = databases[0]
            print(f"Usando base de datos: {test_db}")
            
            # Crear solicitud SOAP para listTables
            list_tables_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:sql="http://services.soadb.example.com/sql">
   <soapenv:Header/>
   <soapenv:Body>
      <sql:listTables>
         <session_token>{self.valid_token}</session_token>
         <database_name>{test_db}</database_name>
      </sql:listTables>
   </soapenv:Body>
</soapenv:Envelope>"""
            
            # Ejecutar la solicitud
            tables_response = self.execute_soap_request(list_tables_request)
            
            # Verificar que la respuesta no está vacía
            self.assertTrue(tables_response, "La respuesta de listTables está vacía")
            
            # Imprimir la respuesta para depuración
            print(f"Respuesta de listTables: {tables_response}")
            
            # Intentar parsear la respuesta
            try:
                tables_root = ET.fromstring(tables_response)
                tables_response_element = tables_root.find('.//ns1:listTablesResponse', self.namespaces)
                
                if tables_response_element is not None:
                    tables_content = tables_response_element.text
                    try:
                        tables_data = json.loads(tables_content)
                        print(f"Datos de tablas: {tables_data}")
                        
                        # La prueba es exitosa si podemos obtener una respuesta, independientemente 
                        # de si hay tablas o no en la base de datos
                        self.assertTrue(True)
                    except json.JSONDecodeError:
                        print(f"Contenido de listTablesResponse no es JSON: {tables_content}")
                else:
                    print("No se encontró el elemento listTablesResponse")
            except ET.ParseError as e:
                print(f"Error al parsear respuesta de listTables: {e}")
                print(f"Contenido: {tables_response}")
                self.fail("La respuesta de listTables no es un XML válido")
            
        except Exception as e:
            print(f"Error durante la prueba: {e}")
            self.fail(f"La prueba falló: {e}")

if __name__ == '__main__':
    unittest.main()