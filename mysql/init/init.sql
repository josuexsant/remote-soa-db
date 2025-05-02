-- Crear tabla de sesiones para almacenar información de autenticación
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    token VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    INDEX (expires_at),
    INDEX (user_id)
);

-- Crear tabla de usuarios
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    role ENUM('admin', 'editor', 'viewer') DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX (email),
    INDEX (provider, provider_id)
);

-- Tabla de ejemplo: estudiantes
CREATE TABLE IF NOT EXISTS estudiantes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    edad INT,
    email VARCHAR(255) UNIQUE,
    carrera VARCHAR(100),
    promedio DECIMAL(4,2),
    fecha_ingreso DATE,
    activo BOOLEAN DEFAULT TRUE
);

-- Insertar datos de ejemplo en la tabla estudiantes
INSERT INTO estudiantes (nombre, apellido, edad, email, carrera, promedio, fecha_ingreso, activo) VALUES
('Juan', 'Pérez', 20, 'juan.perez@example.com', 'Ingeniería', 8.5, '2022-09-01', TRUE),
('María', 'García', 22, 'maria.garcia@example.com', 'Medicina', 9.2, '2021-09-01', TRUE),
('Carlos', 'Rodríguez', 19, 'carlos.rodriguez@example.com', 'Derecho', 7.8, '2023-02-01', TRUE),
('Ana', 'Martínez', 21, 'ana.martinez@example.com', 'Economía', 8.9, '2022-02-01', TRUE),
('Luis', 'González', 23, 'luis.gonzalez@example.com', 'Arquitectura', 8.1, '2020-09-01', TRUE);

-- Crear usuario administrador por defecto
INSERT INTO users (id, username, email, provider, provider_id, role, created_at)
VALUES ('admin1', 'admin', 'admin@example.com', 'local', 'admin1', 'admin', NOW());

-- Procedimiento almacenado para limpiar sesiones expiradas
DELIMITER //
CREATE PROCEDURE clean_expired_sessions()
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW();
END //
DELIMITER ;

-- Evento para ejecutar la limpieza de sesiones cada hora
CREATE EVENT IF NOT EXISTS clean_sessions_event
    ON SCHEDULE EVERY 1 HOUR
    DO CALL clean_expired_sessions();