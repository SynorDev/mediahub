from nicegui import ui
import sqlite3
import json
import os
import time # Añadido para generar IDs únicos
from database import get_template_by_area

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, 'mediahub.db')

def open_template_builder(user_info, on_save_callback):
    """Abre un modal visual para que el usuario construya su JSON sin programar."""
    area_usuario = user_info.get('area', 'general').lower()
    
    plantilla_existente = get_template_by_area(area_usuario)
    
    if plantilla_existente and 'layout' in plantilla_existente and len(plantilla_existente['layout']) > 0:
        campos_agregados = plantilla_existente['layout'][0].get('campos', [])
    else:
        campos_agregados = []

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl p-6 h-[85vh] overflow-y-auto bg-gray-50'):
        with ui.row().classes('w-full items-center justify-between mb-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('build_circle', size='md').classes('text-blue-600')
                ui.label(f'Constructor de Plantillas - {area_usuario.capitalize()}').classes('text-2xl font-bold text-gray-800')
            ui.button(icon='close', on_click=dialog.close).props('flat round text-color=gray')
        
        ui.label('Diseña tu formulario. Usa el botón de engranaje (⚙️) para configurar qué datos se muestran en cada lista.').classes('text-sm text-gray-600 mb-6 border-b pb-4')

        # Contenedor visual donde se pintará la lista de campos
        lista_campos_ui = ui.column().classes('w-full gap-3 mb-6')

        # ==========================================
        # MODAL DE CONFIGURACIÓN DE CAMPO (SUB-MENÚ)
        # ==========================================
        def abrir_configuracion(campo):
            with ui.dialog() as dlg_config, ui.card().classes('w-96 p-6 bg-white'):
                ui.label(f"Configurar: {campo.get('label', 'Campo')}").classes('text-xl font-bold text-gray-800 mb-4 border-b pb-2')
                
                # Editar el nombre visible
                ui.input('Nombre visible (Label)').bind_value(campo, 'label').classes('w-full mb-4')
                
                # ==========================================
                # CASO 1: Lista con Buscador (Bases de Datos Dinámicas)
                # ==========================================
                if campo['ui_component'] == 'searchable_select':
                    def actualizar_multiple(e):
                        campo['multiple'] = e.value
                    ui.switch('Permitir selección múltiple (Varios items)', 
                              value=campo.get('multiple', False), 
                              on_change=actualizar_multiple).classes('mb-4 font-bold text-indigo-600')
                    
                    ui.label('Fuente de Datos (Catálogos)').classes('text-sm font-bold text-gray-500 uppercase tracking-wider mb-2 border-t pt-4')
                    
                    if 'data_source' not in campo or type(campo['data_source']) is not dict or campo['data_source'].get('tipo') != 'dinamico':
                        campo['data_source'] = {"tipo": "dinamico", "entidad": "staff", "filtros": {}}
                        
                    def actualizar_entidad(e):
                        campo['data_source']['entidad'] = e.value
                        actualizar_filtros()
                        
                    entidad_selector = ui.select(
                        {'staff': 'Personal / Crew', 'inventory': 'Equipos Técnicos', 'locations': 'Locaciones / Estudios'},
                        label='¿A qué base de datos se conecta?',
                        value=campo['data_source'].get('entidad', 'staff'),
                        on_change=actualizar_entidad
                    ).classes('w-full mb-4')
                    
                    filtros_container = ui.column().classes('w-full gap-0')
                    
                    def actualizar_filtros():
                        filtros_container.clear()
                        entidad_actual = campo['data_source'].get('entidad', 'staff')
                        filtros = campo['data_source'].setdefault('filtros', {})
                        
                        with filtros_container:
                            if entidad_actual == 'staff':
                                tags_actuales = ", ".join(filtros.get('rol_tags', []))
                                def guardar_tags(e):
                                    filtros['rol_tags'] = [t.strip().lower() for t in e.value.split(',') if t.strip()]
                                ui.input('Filtrar por rol (Ej: sonido, camara)', value=tags_actuales, on_change=guardar_tags).classes('w-full')
                                ui.label('Si lo dejas vacío, mostrará a todo el personal.').classes('text-xs text-gray-400 mt-1 mb-4')
                                
                            elif entidad_actual == 'inventory':
                                cats_actuales = ", ".join(filtros.get('categoria', []))
                                def guardar_cats(e):
                                    filtros['categoria'] = [c.strip() for c in e.value.split(',') if c.strip()]
                                ui.input('Filtrar Categoría (Ej: Iluminación)', value=cats_actuales, on_change=guardar_cats).classes('w-full')
                                ui.label('Si lo dejas vacío, mostrará todo el inventario.').classes('text-xs text-gray-400 mt-1 mb-4')
                                
                            elif entidad_actual == 'locations':
                                ui.label('Las locaciones no requieren filtros. Se mostrarán todas.').classes('text-xs text-blue-500 font-bold bg-blue-50 p-2 rounded w-full mb-4')
                    
                    actualizar_filtros()

                # ==========================================
                # CASO 2: Lista Simple (Opciones Manuales Creadas por el Usuario)
                # ==========================================
                elif campo['ui_component'] == 'select':
                    ui.label('Opciones Personalizadas').classes('text-sm font-bold text-gray-500 uppercase tracking-wider mb-2 border-t pt-4')
                    
                    # Forzamos a que el campo sea de memoria estática
                    if 'data_source' not in campo or type(campo['data_source']) is not dict or campo['data_source'].get('tipo') != 'estatico':
                        campo['data_source'] = {"tipo": "estatico", "opciones": []}
                        
                    opciones_list = campo['data_source']['opciones']
                    
                    # Interfaz para agregar opciones
                    with ui.row().classes('w-full items-center gap-2 mb-4 flex-nowrap'):
                        nueva_opc = ui.input('Escribe una opción (Ej: Confirmado)').classes('flex-grow')
                        
                        def agregar_opcion():
                            val = nueva_opc.value.strip()
                            if val and val not in opciones_list:
                                opciones_list.append(val)
                                nueva_opc.value = ''
                                refrescar_opciones()
                            elif not val:
                                ui.notify('Escribe algo primero', type='warning')
                            else:
                                ui.notify('Esa opción ya existe', type='warning')
                                
                        ui.button(icon='add', on_click=agregar_opcion).classes('bg-blue-100 text-blue-700 shadow-none px-4')
                        
                    # Contenedor dinámico de los elementos agregados
                    contenedor_opciones = ui.column().classes('w-full gap-1 bg-gray-50 p-2 rounded border border-gray-200 min-h-[50px]')
                    
                    def refrescar_opciones():
                        contenedor_opciones.clear()
                        with contenedor_opciones:
                            if not opciones_list:
                                ui.label('Aún no has agregado opciones.').classes('text-xs text-gray-400 italic')
                            for op in opciones_list:
                                with ui.row().classes('w-full justify-between items-center bg-white p-2 rounded border border-gray-100 shadow-sm'):
                                    ui.label(op).classes('text-sm text-gray-700 font-medium')
                                    def borrar_op(op_a_borrar=op):
                                        opciones_list.remove(op_a_borrar)
                                        refrescar_opciones()
                                    ui.button(icon='delete', on_click=borrar_op).props('flat color=red round size=sm')
                                    
                    refrescar_opciones()

                # ==========================================
                # CASO 3: Campo de Texto Libre
                # ==========================================
                elif campo['ui_component'] == 'text_input':
                    ui.label('Campo de Texto').classes('text-sm font-bold text-gray-500 uppercase tracking-wider mb-2 border-t pt-4')
                    ui.label('Nota: Si este es el primer campo de texto en tu plantilla, el sistema lo enlazará automáticamente como el Título Oficial del evento compartido.').classes('text-xs text-gray-400 mb-4 leading-tight')
                        
                # ==========================================
                # CASO 4: Switch de Evento Compartido
                # ==========================================
                elif campo['ui_component'] == 'switch':
                    ui.label('Destino del Evento').classes('text-sm font-bold text-gray-500 uppercase tracking-wider mb-2 mt-4')
                    
                    def actualizar_target(e):
                        area_limpia = e.value.strip().lower()
                        campo['target_area'] = area_limpia
                        # Si borra el área, le devolvemos un ID genérico para que no colapse
                        campo['name_id'] = f"compartir_{area_limpia}" if area_limpia else generar_id()
                        
                    ui.input('¿A qué área se enviará? (Ej: programacion, ingenieria)', 
                             value=campo.get('target_area', ''), 
                             on_change=actualizar_target).classes('w-full mb-2')
                             
                    ui.label('Cuando se active, el evento aparecerá en el calendario del área destino.').classes('text-xs text-gray-400 mb-4 leading-tight')

                # ==========================================
                # BOTÓN DE GUARDAR DEL MODAL
                # ==========================================
                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('Listo', on_click=lambda: [dlg_config.close(), refrescar_vista_campos()]).classes('bg-blue-600 text-white font-bold px-6')
            
            dlg_config.open()

        # ==========================================
        # RENDERIZADO DE LA LISTA PRINCIPAL
        # ==========================================
        def refrescar_vista_campos():
            lista_campos_ui.clear()
            with lista_campos_ui:
                if not campos_agregados:
                    with ui.column().classes('w-full items-center py-8 bg-white border-2 border-dashed border-gray-300 rounded-lg'):
                        ui.icon('extension', size='lg').classes('text-gray-300 mb-2')
                        ui.label('Tu formulario está vacío').classes('text-gray-500 font-bold')
                
                for idx, campo in enumerate(campos_agregados):
                    with ui.row().classes('w-full items-center justify-between p-3 bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow'):
                        with ui.column().classes('gap-0'):
                            ui.label(campo['label']).classes('font-bold text-gray-800')
                            ui.label(f"Tipo: {campo['ui_component']}").classes('text-xs text-blue-500 uppercase font-semibold tracking-wider')
                        
                        with ui.row().classes('gap-1'):
                            ui.button(icon='settings', on_click=lambda c=campo: abrir_configuracion(c)).props('flat color=gray round size=sm').tooltip('Configurar origen de datos')
                            ui.button(icon='delete', on_click=lambda i=idx: eliminar_campo(i)).props('flat color=red round size=sm').tooltip('Eliminar campo')

        def eliminar_campo(idx):
            campos_agregados.pop(idx)
            refrescar_vista_campos()

        # ==========================================
        # FUNCIONES PARA AÑADIR BLOQUES AL JSON
        # ==========================================
        def generar_id():
            # Usamos el área para aislar las llaves y evitar que dos áreas sobreescriban sus datos
            return f"campo_{area_usuario}_{int(time.time() * 1000)}"

        def agregar_texto_libre():
            campos_agregados.append({
                "name_id": generar_id(),
                "label": "Nuevo Campo de Texto",
                "ui_component": "text_input"
            })
            refrescar_vista_campos()

        def agregar_horario():
            campos_agregados.append({
                "name_id": generar_id(),
                "label": "Horario de asignación",
                "ui_component": "time_range"
            })
            refrescar_vista_campos()

        def agregar_lista(searchable=False):
            campos_agregados.append({
                "name_id": generar_id(),
                "label": "Lista Desplegable Nueva",
                "ui_component": "searchable_select" if searchable else "select",
                "data_source": {
                    "tipo": "dinamico",
                    "entidad": "staff",
                    "filtros": {} 
                }
            })
            refrescar_vista_campos()

        def agregar_switch_compartir():
            campos_agregados.append({
                "name_id": generar_id(), # ID dinámico por defecto
                "label": "Switch (Evento Compartido)",
                "ui_component": "switch",
                "target_area": "" # Vacío por defecto, sin hardcodeo
            })
            refrescar_vista_campos()

        # ==========================================
        # BOTONERA DE HERRAMIENTAS
        # ==========================================
        ui.label('Añadir Elementos').classes('text-sm font-bold text-gray-500 uppercase tracking-wider mb-2')
        with ui.row().classes('w-full gap-2 mb-8'):
            ui.button('Texto Libre', icon='title', on_click=agregar_texto_libre).classes('bg-gray-200 text-gray-800 shadow-none hover:bg-gray-300')
            ui.button('Rango Horario', icon='schedule', on_click=agregar_horario).classes('bg-gray-200 text-gray-800 shadow-none hover:bg-gray-300')
            ui.button('Lista (Simple)', icon='arrow_drop_down_circle', on_click=lambda: agregar_lista(False)).classes('bg-indigo-100 text-indigo-800 shadow-none hover:bg-indigo-200')
            ui.button('Lista (Buscador)', icon='search', on_click=lambda: agregar_lista(True)).classes('bg-indigo-100 text-indigo-800 shadow-none hover:bg-indigo-200')
            ui.button('Switch (Evento Compartido)', icon='toggle_on', on_click=agregar_switch_compartir).classes('bg-red-100 text-red-800 shadow-none hover:bg-red-200')

        refrescar_vista_campos()

        # ==========================================
        # GUARDAR EN BASE DE DATOS
        # ==========================================
        def compilar_y_guardar():
            if not campos_agregados:
                ui.notify('Debes agregar al menos un campo a tu formulario.', type='warning')
                return
                
            template_json = {
                "template_meta": {
                    "tenant_id": area_usuario,
                    "template_id": f"tpl_{area_usuario}_v1",
                    "nombre": f"Ficha Técnica - {area_usuario.capitalize()}",
                    "estado": "activo"
                },
                "layout": [
                    {
                        "tipo_contenedor": "grid",
                        "titulo": "Configuración del Evento",
                        "columnas": 2, 
                        "campos": campos_agregados
                    }
                ]
            }
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            config_json_str = json.dumps(template_json)
            template_id = template_json["template_meta"]["template_id"]
            
            try:
                cursor.execute('INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)',
                               (template_id, area_usuario, config_json_str))
            except sqlite3.IntegrityError:
                cursor.execute('UPDATE event_templates SET config_json = ? WHERE template_id = ?',
                               (config_json_str, template_id))
            conn.commit()
            conn.close()
            
            ui.notify('¡Plantilla compilada y guardada con éxito!', type='positive')
            dialog.close()
            on_save_callback() 

        with ui.row().classes('w-full justify-between items-center mt-auto pt-4 border-t'):
            ui.button('Cerrar Constructor', on_click=dialog.close).props('flat text-gray-500')
            ui.button('Compilar y Guardar Cambios', icon='save', on_click=compilar_y_guardar).classes('bg-green-600 text-white font-bold px-6 py-2 shadow-md hover:bg-green-700')

    dialog.open()