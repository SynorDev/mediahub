# Implementación del Tipo de Campo "Vinculado a Datos" (Relacional) en MediaHub

Este plan detalla la implementación del nuevo tipo de campo **"Vinculado a Datos (Relación)"** (`linked_data`) en el Creador de Gestiones Personalizadas (`custom_management.py`). Esto permitirá conectar dinámicamente cualquier gestión (por ejemplo: *"Acta de entrega de equipos"*) con registros de otras gestiones del sistema (*Gestión de Inventario*, *Gestión de Personal*, etc.), soportando selección única o múltiple.

---

## User Review Required

> [!IMPORTANT]
> **Experiencia de Usuario en el Creador de Gestiones:**
> 1. Al agregar un campo y seleccionar el tipo **"Vinculado a Datos (Relación)"**, se desplegarán dos configuraciones automáticas:
>    * **Gestión de Origen:** Menú desplegable con todas las gestiones disponibles en la plataforma (*Gestión de Inventario*, *Gestión de Personal*, etc.).
>    * **Modo de Selección:** Casilla para activar *"Permitir selección múltiple"* (útil para asignar varios equipos en una misma acta) o dejarla en selección única (ideal para seleccionar un solo colaborador).
> 2. Al diligenciar el formulario de la gestión:
>    * Los equipos o registros vinculados se seleccionan mediante un desplegable inteligente con búsqueda en tiempo real, mostrando nombre, modelo y serial (`[Nombre] - S/N: [Serial]`).
>    * Si el equipo en inventario posee accesorios o sub-ítems (cargador, batería, etc.), estos también estarán disponibles para seleccionarse individualmente en el acta.

---

## Proposed Changes

### Componente de Gestiones Personalizadas

#### [MODIFY] [custom_management.py](file:///c:/Sistemas%20Desarrollo/Gestion/MediaHub/components/custom_management.py)

1. **Nuevo helper de resolución de registros:**
   * Crear la función `obtener_opciones_modulo_vinculado(target_module_id)` que consulta la base de datos de la gestión objetivo y genera un diccionario amigable: `{ "item_id": "Descripción legible con serial/cargo" }`.
   * Para *Gestión de Inventario*, incluirá tanto el equipo principal como sus accesorios/componentes (permitiendo asociar, por ejemplo, tanto la laptop como su cargador).

2. **Extensión del Modal Constructor de Esquemas (`abrir_modal_creador`):**
   * Añadir `'linked_data': 'Vinculado a Datos (Relación)'` a las opciones de tipo de campo (`typ_sel`).
   * Renderizar reactivamente el selector de gestión de origen (`ui.select`) y el checkbox de selección múltiple (`ui.checkbox`) cuando el campo sea de este tipo.
   * Actualizar `guardar_campos_temporales()` y `compilar_y_guardar_modulo()` para validar y persistir los atributos `linked_module_id` y `linked_multiple`.

3. **Renderizado en el Formulario de Nuevo Registro:**
   * Generar un selector `ui.select` con búsqueda (`with_input=True` o `clearable=True`) cargado en vivo con los registros del módulo vinculado.
   * Si `linked_multiple=True`, activar `multiple=True` y presentación en chips para seleccionar varios ítems con facilidad.
   * Almacenar en el registro los identificadores y el detalle de los ítems seleccionados.

4. **Renderizado en el Modal de Edición de Registro (`abrir_dialogo_edicion`):**
   * Añadir el soporte para precargar y editar campos de tipo `linked_data`.

5. **Visualización en Tarjetas del Listado y Búsqueda:**
   * En las tarjetas de registro, mostrar los datos vinculados con un diseño visual distintivo (badge/etiqueta con icono de enlace `🔗` y los ítems asociados).
   * Permitir que el buscador principal filtre registros buscando dentro de los valores vinculados (por ejemplo, buscar por el serial de una laptop para encontrar el acta donde fue entregada).

---

### Componente de Reportes y Previsualización A4

#### [MODIFY] [custom_report_preview.py](file:///c:/Sistemas%20Desarrollo/Gestion/MediaHub/components/custom_report_preview.py)

* Adaptar el renderizador de celdas de la hoja A4 y el estimador de altura para formatear limpiamente los campos de tipo `linked_data` cuando se exporte a PDF o se visualice el reporte.

---

## Verification Plan

### Automated Verification
- Ejecutar verificación de sintaxis y compilación en Python:
  ```powershell
  python -m py_compile components/custom_management.py components/custom_report_preview.py
  ```

### Manual Verification
1. Ingresar a MediaHub en el navegador.
2. Abrir el modal **"Crear Nueva Gestión"** y verificar que aparezca la opción **"Vinculado a Datos (Relación)"**.
3. Seleccionar como origen **"Gestión de Inventario"** y marcar selección múltiple.
4. Crear una gestión de prueba o el módulo **"Acta de entrega de equipos"**.
5. Agregar un registro seleccionando equipos reales del inventario existente.
6. Verificar que se muestren correctamente en la lista de registros con sus seriales y que el buscador funcione por serial vinculado.
7. Verificar la edición del registro.
