// Cambiar a la base de datos dbservice
db = db.getSiblingDB('dbservice');

// Crear colección para sesiones
db.createCollection('sessions');

// Crear índices para la colección de sesiones
db.sessions.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });
db.sessions.createIndex({ "user_id": 1 });

// Crear colección para usuarios
db.createCollection('users');

// Crear índices para la colección de usuarios
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "provider": 1, "provider_id": 1 });

// Insertar usuario administrador por defecto
db.users.insertOne({
    "_id": "admin1",
    "username": "admin",
    "email": "admin@example.com",
    "provider": "local",
    "provider_id": "admin1",
    "role": "admin",
    "created_at": new Date()
});

// Crear colección de estudiantes (ejemplo)
db.createCollection('estudiantes');

// Insertar datos de ejemplo en la colección de estudiantes
db.estudiantes.insertMany([
    {
        "nombre": "Juan",
        "apellido": "Pérez",
        "edad": 20,
        "email": "juan.perez@example.com",
        "carrera": "Ingeniería",
        "promedio": 8.5,
        "fecha_ingreso": new Date("2022-09-01"),
        "activo": true
    },
    {
        "nombre": "María",
        "apellido": "García",
        "edad": 22,
        "email": "maria.garcia@example.com",
        "carrera": "Medicina",
        "promedio": 9.2,
        "fecha_ingreso": new Date("2021-09-01"),
        "activo": true
    },
    {
        "nombre": "Carlos",
        "apellido": "Rodríguez",
        "edad": 19,
        "email": "carlos.rodriguez@example.com",
        "carrera": "Derecho",
        "promedio": 7.8,
        "fecha_ingreso": new Date("2023-02-01"),
        "activo": true
    },
    {
        "nombre": "Ana",
        "apellido": "Martínez",
        "edad": 21,
        "email": "ana.martinez@example.com",
        "carrera": "Economía",
        "promedio": 8.9,
        "fecha_ingreso": new Date("2022-02-01"),
        "activo": true
    },
    {
        "nombre": "Luis",
        "apellido": "González",
        "edad": 23,
        "email": "luis.gonzalez@example.com",
        "carrera": "Arquitectura",
        "promedio": 8.1,
        "fecha_ingreso": new Date("2020-09-01"),
        "activo": true
    }
]);

// Crear TTL index para limpiar automáticamente las sesiones expiradas
db.sessions.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });