# Arquitectura y Funciones del Sistema MediaHub

## Visión General
**MediaHub** es un sistema web de gestión de recursos, personal y calendarios, diseñado para centralizar las operaciones de departamentos técnicos (como Ingeniería o Sistemas). Está construido en Python utilizando el framework **NiceGUI**, lo que permite una integración fluida entre el frontend (interfaz de usuario) y el backend (lógica y base de datos) en un mismo entorno de código.

## Arquitectura del Sistema

El sistema sigue una arquitectura monolítica basada en componentes, con almacenamiento de datos local.

### 1. Interfaz y Lógica (NiceGUI)
- **Framework:** NiceGUI (basado en FastAPI y Vue.js bajo el capó), sirviendo la aplicación en el puerto `5480`.
- **Estructura de Componentes:** La interfaz está modularizada en la carpeta `components/` (barras de navegación, calendarios, formularios, importadores) para facilitar la reutilización de código.
- **Enrutamiento:** Las vistas principales están separadas en la carpeta `pages/` (Login, Home, Panel de Administración, Reportes).

### 2. Base de Datos (SQLite)
- Utiliza **SQLite** (`mediahub.db`) para almacenamiento ligero y local.
- **Evolución del Esquema:** Combina tablas relacionales clásicas (usuarios, eventos) con tablas dinámicas que almacenan configuraciones y registros en formato **JSON** (`custom_modules`, `custom_module_records`, `event_templates`). Esto permite que el sistema adapte sus formularios de inventario o reportes sin necesidad de alterar la estructura de la base de datos.

### 3. Módulos Principales
- **`main.py`**: Punto de entrada de la aplicación, inicializa la base de datos y define las rutas principales.
- **`database.py`**: Capa de acceso a datos (ORM manual). Contiene todas las consultas SQL, lógica de migración de datos, hasheo de contraseñas y gestión de estructuras dinámicas (JSON).
- **`pages/`**:
  - `home.py`: Pantalla principal que alberga la vista de Calendario y el acceso al creador de reportes.
  - `admin_panel.py`: Panel de control exclusivo para áreas técnicas.
  - `login.py` / `register.py`: Autenticación y registro de usuarios.
- **`components/`**:
  - **Constructores (Builders):** `report_builder.py`, `template_builder.py`, `custom_management.py`. Motores para crear formularios y reportes dinámicos.
  - **Visualización:** `calendar_view.py`, `timeline_panel.py` para la gestión gráfica del tiempo y eventos.
  - **Utilidades:** `excel_importer.py` para cargas masivas, `topbar.py` y `sidebar.py` para la navegación.

---

## Funciones Principales ¿Para qué sirve?

### 1. Gestión de Calendario y Eventos (Scheduling)
Permite programar eventos diarios o mensuales. Incluye una **lógica de visibilidad (V4)** que determina quién puede ver qué evento dependiendo de su área y los permisos de privacidad asignados al crearlo.

### 2. Control de Inventario Técnico
Sirve para mantener un registro exhaustivo de equipos. 
- Permite catalogar equipos por nombre, categoría, número de serie (S/N) y cantidad.
- Soporta la adición de múltiples accesorios/complementos por equipo.
- Permite subir fotos de los equipos, las cuales son optimizadas (comprimidas y redimensionadas) automáticamente para ahorrar espacio.
- **Importación Masiva:** Capacidad de importar inventarios completos desde archivos Excel (`excel_importer.py`).

### 3. Gestión de Personal y Roles
Un directorio para administrar a los miembros del equipo (Staff), asignándoles roles específicos, información de contacto (teléfono, correo) y áreas de trabajo. Incluye soporte para importación desde archivos CSV.

### 4. Panel de Administración Restringido
Un entorno seguro (`admin_panel.py`) que valida el rol del usuario (restringido a "ingeniería" o "sistemas"). Desde aquí los administradores controlan el personal, los roles, las categorías de inventario y crean/editan los registros del sistema.

### 5. Motor de Módulos y Reportes Dinámicos
En lugar de tener formularios fijos, MediaHub cuenta con un sistema flexible (`custom_modules`) que permite crear nuevos tipos de registros definiendo sus campos en un archivo JSON. Esto incluye la creación de reportes visuales personalizados y plantillas de eventos, adaptándose a las necesidades cambiantes del departamento sin programar código adicional.
