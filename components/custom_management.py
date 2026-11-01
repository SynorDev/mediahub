from nicegui import ui
import json
import base64
import io
import time
from PIL import Image
from database import (
    add_custom_module, get_all_custom_modules, update_custom_module, delete_custom_module,
    add_custom_record, get_all_custom_records, update_custom_record, delete_custom_record,
    get_custom_module, obtener_opciones_modulo_vinculado, obtener_detalles_modulo_vinculado,
    is_module_quick_access, toggle_admin_quick_access
)
from components.excel_importer import open_excel_importer_dialog


def optimize_image(image_bytes: bytes, max_size=(600, 600), quality=75) -> str:
    """
    Redimensiona y comprime la imagen a formato JPEG Base64 para optimizar espacio.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = output_buffer.getvalue()
        base64_encoded = base64.b64encode(compressed_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_encoded}"
    except Exception as e:
        print("Error al optimizar la imagen:", e)
        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_encoded}"

def abrir_visor_lightbox(record_title, array_fotos):
    """Abre un diálogo modal para visualizar fotos en carrusel o vista ampliada."""
    if not array_fotos:
        return
    with ui.dialog() as dlg_light, ui.card().classes('w-[520px] p-6 bg-white items-center'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(record_title).classes('text-base font-bold text-gray-800 truncate')
            ui.button(icon='close', on_click=dlg_light.close).props('flat round size=sm')
        
        if len(array_fotos) > 1:
            with ui.carousel(animated=True, arrows=True, navigation=True).classes('w-full h-80 rounded bg-gray-100 shadow-inner'):
                for f in array_fotos:
                    with ui.carousel_slide().classes('p-0 items-center justify-center'):
                        ui.image(f).classes('h-full object-contain')
        elif array_fotos:
            ui.image(array_fotos[0]).classes('w-full max-h-80 object-contain rounded')
    dlg_light.open()

# Iconos predefinidos para elegir
ICONOS_DISPONIBLES = {
    'build': 'Herramientas / Equipos (🔧)',
    'directions_car': 'Vehículos / Transporte (🚗)',
    'computer': 'Tecnología / PCs (💻)',
    'place': 'Locación / Estudios (📍)',
    'description': 'Documentos / Fichas (📄)',
    'extension': 'Accesorios / Componentes (🧩)',
    'person': 'Personal / Staff (👤)',
    'work': 'Proyectos / Trabajos (💼)',
    'photo_camera': 'Cámaras / Video (📷)',
    'inventory': 'Inventario General (📦)',
    'assignment': 'Tareas / Asignaciones (📝)'
}

def render_custom_management_builder(initial_module_id=None, show_list=True, on_quick_access_toggle=None):
    """
    Dibuja la pestaña del creador de gestiones personalizadas con estructura dividida o vista individual.
    Permite fijar/desfijar gestiones en la barra de selección rápida superior.
    """
    # Contenedor principal de la pestaña
    main_row = ui.row().classes('w-full gap-6 items-start flex-nowrap mt-4')
    
    # Referencias de contenedores para refresco reactivo
    list_container = ui.column().classes('w-1/4 gap-4 bg-white p-4 rounded-lg border border-gray-200 shadow-sm') if show_list else None
    right_panel = ui.column().classes('w-3/4 gap-6 bg-transparent' if show_list else 'w-full gap-6 bg-transparent')
    
    mod_inicial = get_custom_module(initial_module_id) if initial_module_id else None
    state = {
        'selected_module': mod_inicial
    }
    
    def seleccionar_modulo(modulo):
        state['selected_module'] = modulo
        if show_list:
            refrescar_listado_modulos()
        dibujar_panel_derecho()

    def refrescar_listado_modulos():
        if not list_container:
            return
        list_container.clear()
        modulos = get_all_custom_modules()
        
        with list_container:
            ui.label('Gestiones Creadas').classes('text-md font-bold text-gray-700 mb-2 border-b pb-2 w-full')
            
            if not modulos:
                ui.label('No hay gestiones creadas aún.').classes('text-xs text-gray-400 italic mb-4')
            else:
                for mod in modulos:
                    # Resaltar si está seleccionado
                    es_seleccionado = state['selected_module'] and state['selected_module']['id'] == mod['id']
                    clases_card = 'w-full p-2.5 flex flex-row items-center justify-between gap-2 transition-colors '
                    clases_card += 'bg-indigo-50 border border-indigo-300' if es_seleccionado else 'bg-gray-50 hover:bg-gray-100 border border-gray-200'
                    
                    is_pinned = is_module_quick_access(mod['id'])
                    
                    with ui.card().classes(clases_card):
                        with ui.row().classes('items-center gap-2 flex-grow cursor-pointer min-w-0').on('click', lambda _, m=mod: seleccionar_modulo(m)):
                            ui.icon(mod['icono'], size='sm').classes('text-indigo-600' if es_seleccionado else 'text-gray-500 shrink-0')
                            ui.label(mod['nombre']).classes('font-bold text-xs text-gray-800 truncate')
                        
                        def toggle_pin(m_id=mod['id']):
                            st = toggle_admin_quick_access(m_id)
                            ui.notify(f"{'✓ Agregado a la barra de acceso rápido' if st else 'Removido de la barra de acceso rápido'}", type='info')
                            refrescar_listado_modulos()
                            if state.get('selected_module') and state['selected_module']['id'] == m_id:
                                dibujar_panel_derecho()
                            if on_quick_access_toggle:
                                on_quick_access_toggle()

                        ui.button(
                            icon='bookmark' if is_pinned else 'bookmark_border',
                            on_click=toggle_pin
                        ).props(f"flat round size=xs {'color=indigo' if is_pinned else 'color=grey-5'}") \
                         .tooltip('En barra de acceso rápido (Clic para quitar)' if is_pinned else 'Agregar a la barra superior de acceso rápido')
            
            ui.button('Nueva Gestión', icon='add_circle', on_click=abrir_modal_creador).classes('w-full bg-indigo-600 text-white font-bold py-2 mt-4 shadow-sm text-xs')

    # ==========================================
    # MODAL CONSTRUCTOR DE FORMULARIOS / SCHEMAS
    # ==========================================
    def abrir_modal_creador(module_to_edit=None):
        with ui.dialog() as dlg_builder, ui.card().classes('w-[500px] p-6 max-h-[85vh] overflow-y-auto bg-gray-50'):
            titulo = 'Editar Esquema de Gestión' if module_to_edit else 'Crear Nueva Gestión'
            ui.label(titulo).classes('text-xl font-bold text-gray-800 mb-4 border-b pb-2')
            
            nom_inicial = module_to_edit['nombre'] if module_to_edit else ''
            icon_inicial = module_to_edit['icono'] if module_to_edit else 'inventory'
            
            nombre_input = ui.input('Nombre del Módulo (Ej: Control de Flota)', value=nom_inicial).classes('w-full mb-3')
            icono_select = ui.select(ICONOS_DISDRA_DISPONIBLES if 'ICONOS_DISDRA_DISPONIBLES' in globals() else ICONOS_DISPONIBLES, label='Icono del Módulo', value=icon_inicial).classes('w-full mb-4')
            
            ui.label('Campos del Formulario').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mb-2')
            
            fields_data = []
            if module_to_edit:
                for idx, f in enumerate(module_to_edit['config']):
                    f_dict = dict(f)
                    if 'key' not in f_dict:
                        f_dict['key'] = f"field_{idx}"
                    fields_data.append(f_dict)
                    
            fields_container = ui.column().classes('w-full gap-3 mb-4')
            fields_inputs = [] # Mantiene referencias a los inputs de la vista para poder leerlos
            
            def guardar_campos_temporales():
                new_list = []
                for item in fields_inputs:
                    lbl_in = item['lbl']
                    typ_sel = item['typ']
                    opt_in = item.get('opt')
                    linked_mod = item.get('linked_mod')
                    linked_mult = item.get('linked_mult')
                    key_val = item['key']
                    
                    opciones = [o.strip() for o in opt_in.value.split(',') if o.strip()] if opt_in and opt_in.value else []
                    linked_mod_id = linked_mod.value if linked_mod else None
                    linked_mult_val = linked_mult.value if linked_mult else False
                    
                    new_list.append({
                        'key': key_val,
                        'label': lbl_in.value.strip(),
                        'type': typ_sel.value,
                        'options': opciones,
                        'linked_module_id': linked_mod_id,
                        'linked_multiple': linked_mult_val
                    })
                fields_data.clear()
                fields_data.extend(new_list)

            def refrescar_campos_builder_ui():
                fields_container.clear()
                fields_inputs.clear()
                
                with fields_container:
                    if not fields_data:
                        ui.label('No has añadido campos aún.').classes('text-xs text-gray-400 italic mb-2')
                    for idx, field in enumerate(fields_data):
                        field_key = field.get('key', f"field_{idx}")
                        with ui.card().classes('w-full p-4 bg-white border border-gray-200 relative shadow-sm'):
                            # Botones de orden (Subir / Bajar) y eliminar campo
                            with ui.row().classes('absolute -top-2 -right-1 gap-1 items-center z-10'):
                                def mover_arriba(i=idx):
                                    guardar_campos_temporales()
                                    if i > 0:
                                        fields_data[i], fields_data[i-1] = fields_data[i-1], fields_data[i]
                                        refrescar_campos_builder_ui()
                                        
                                btn_up = ui.button(icon='keyboard_arrow_up', on_click=mover_arriba).props('flat round size=xs color=primary').classes('bg-white border border-gray-300 shadow-sm').tooltip('Subir')
                                if idx == 0:
                                    btn_up.props('disabled')
                                    
                                def mover_abajo(i=idx):
                                    guardar_campos_temporales()
                                    if i < len(fields_data) - 1:
                                        fields_data[i], fields_data[i+1] = fields_data[i+1], fields_data[i]
                                        refrescar_campos_builder_ui()
                                        
                                btn_down = ui.button(icon='keyboard_arrow_down', on_click=mover_abajo).props('flat round size=xs color=primary').classes('bg-white border border-gray-300 shadow-sm').tooltip('Bajar')
                                if idx == len(fields_data) - 1:
                                    btn_down.props('disabled')
                                    
                                def crear_borrador_campo(i=idx):
                                    return lambda: [guardar_campos_temporales(), fields_data.pop(i), refrescar_campos_builder_ui()]
                                ui.button(icon='close', on_click=crear_borrador_campo(idx)).props('flat round size=xs color=red').classes('bg-white border border-gray-300 shadow-sm').tooltip('Eliminar')
                            
                            with ui.row().classes('w-full gap-2 mb-2 flex-nowrap'):
                                lbl_in = ui.input('Etiqueta (Label)', value=field['label']).classes('flex-grow')
                                
                                def al_cambiar_tipo(e, f_dict=field):
                                    guardar_campos_temporales()
                                    f_dict['type'] = e.value
                                    refrescar_campos_builder_ui()

                                typ_sel = ui.select({
                                    'text': 'Texto',
                                    'number': 'Número',
                                    'select': 'Lista (Opciones)',
                                    'images': 'Galería de Fotos',
                                    'accessories': 'Accesorios con Serial',
                                    'linked_data': 'Vinculado a Datos (Relación)'
                                }, label='Tipo', value=field['type'], on_change=al_cambiar_tipo).classes('w-2/5')
                            
                            # Opciones adicionales según el tipo
                            opt_in_ref = None
                            linked_mod_ref = None
                            linked_mult_ref = None

                            if field['type'] == 'select':
                                opt_in_ref = ui.input('Opciones (separadas por coma)', value=",".join(field.get('options', []))).classes('w-full text-xs mb-1')
                            elif field['type'] == 'linked_data':
                                modulos_disp = get_all_custom_modules()
                                mod_opts = {m['id']: m['nombre'] for m in modulos_disp if not (module_to_edit and m['id'] == module_to_edit['id'])}
                                val_mod = field.get('linked_module_id')
                                if not val_mod and mod_opts:
                                    val_mod = list(mod_opts.keys())[0]
                                with ui.row().classes('w-full gap-2 items-center mb-1 flex-nowrap'):
                                    linked_mod_ref = ui.select(mod_opts, label='Gestión a Vincular', value=val_mod).classes('flex-grow text-xs')
                                    linked_mult_ref = ui.checkbox('Múltiples', value=field.get('linked_multiple', False)).classes('text-xs shrink-0').tooltip('Permitir seleccionar múltiples registros')
                                    
                            fields_inputs.append({
                                'lbl': lbl_in,
                                'typ': typ_sel,
                                'opt': opt_in_ref,
                                'linked_mod': linked_mod_ref,
                                'linked_mult': linked_mult_ref,
                                'key': field_key
                            })

            def agregar_campo():
                guardar_campos_temporales()
                new_key = f"field_{int(time.time()*1000)}"
                fields_data.append({'key': new_key, 'label': '', 'type': 'text', 'options': [], 'linked_module_id': None, 'linked_multiple': False})
                refrescar_campos_builder_ui()
                
            ui.button('Añadir Campo', icon='add', on_click=agregar_campo).classes('bg-indigo-50 text-indigo-700 shadow-none mb-6 px-4 py-1 text-xs')
            
            refrescar_campos_builder_ui()
            
            # Guardar el módulo completo en base de datos
            def compilar_y_guardar_modulo():
                guardar_campos_temporales()
                nombre_modulo = nombre_input.value.strip()
                if not nombre_modulo:
                    ui.notify('Escribe un nombre para la gestión', type='warning')
                    return
                if not fields_data:
                    ui.notify('Debes añadir al menos un campo al formulario', type='warning')
                    return
                for f in fields_data:
                    if not f['label']:
                        ui.notify('Los campos no pueden tener etiquetas vacías', type='warning')
                        return
                    if f['type'] == 'select' and not f['options']:
                        ui.notify(f"El campo '{f['label']}' de tipo Lista requiere opciones", type='warning')
                        return
                    if f['type'] == 'linked_data' and not f.get('linked_module_id'):
                        ui.notify(f"El campo '{f['label']}' de tipo Vinculado a Datos requiere seleccionar una gestión", type='warning')
                        return
                
                if module_to_edit:
                    success, msg = update_custom_module(module_to_edit['id'], nombre_modulo, icono_select.value, fields_data)
                else:
                    module_id = f"custom_mod_{int(time.time())}"
                    success, msg = add_custom_module(module_id, nombre_modulo, icono_select.value, fields_data)
                
                if success:
                    ui.notify(msg, type='positive')
                    dlg_builder.close()
                    # Actualizar estado seleccionado
                    if module_to_edit and state['selected_module'] and state['selected_module']['id'] == module_to_edit['id']:
                        state['selected_module'] = {
                            'id': module_to_edit['id'],
                            'nombre': nombre_modulo,
                            'icono': icono_select.value,
                            'config': fields_data
                        }
                    refrescar_listado_modulos()
                    dibujar_panel_derecho()
                else:
                    ui.notify(msg, type='negative')
            
            with ui.row().classes('w-full justify-between items-center mt-6 pt-4 border-t'):
                ui.button('Cancelar', on_click=dlg_builder.close).props('flat text-gray-500')
                ui.button('Guardar Esquema', icon='save', on_click=compilar_y_guardar_modulo).classes('bg-green-600 text-white font-bold px-6 py-2 shadow-md')
                
        dlg_builder.open()

    # ==========================================
    # VISUALIZACIÓN DINÁMICA DE REGISTROS (CRUD)
    # ==========================================
    def dibujar_panel_derecho():
        right_panel.clear()
        
        mod = state['selected_module']
        if not mod:
            with right_panel:
                with ui.column().classes('w-full h-96 items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-6 bg-white'):
                    ui.icon('dashboard_customize', size='lg').classes('text-gray-300 mb-2')
                    ui.label('Selecciona o crea una gestión del menú izquierdo').classes('text-gray-500 font-semibold text-center')
            return
            
        module_id = mod['id']
        fields = mod['config']
        
        with right_panel:
            # Cabecera de la gestión seleccionada
            with ui.row().classes('w-full justify-between items-center mb-2'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon(mod['icono'], size='md').classes('text-indigo-600')
                    ui.label(mod['nombre']).classes('text-2xl font-bold text-gray-800')
                
                # Botones de edición de campos y eliminación del módulo
                with ui.row().classes('gap-2 items-center flex-wrap'):
                    is_pinned = is_module_quick_access(module_id)
                    def toggle_pin_header():
                        st = toggle_admin_quick_access(module_id)
                        ui.notify(f"{'✓ Agregado a la barra superior' if st else 'Removido de la barra superior'}", type='info')
                        if show_list:
                            refrescar_listado_modulos()
                        dibujar_panel_derecho()
                        if on_quick_access_toggle:
                            on_quick_access_toggle()

                    ui.button(
                        'En Barra de Selección' if is_pinned else '+ Acceso Rápido en Barra',
                        icon='bookmark' if is_pinned else 'bookmark_add',
                        on_click=toggle_pin_header
                    ).props(f"{'unelevated color=indigo' if is_pinned else 'outline color=indigo'} size=xs font-bold") \
                     .tooltip('Quitar de la barra de pestañas' if is_pinned else 'Fijar como pestaña de acceso rápido en el panel de ingeniería')

                    ui.button('Importar Excel', icon='upload_file', on_click=lambda: open_excel_importer_dialog(mod, on_success_callback=lambda: refrescar_listado_registros())).classes('bg-emerald-600 text-white font-bold text-xs shadow-sm')
                    ui.button('Editar Campos', icon='edit', on_click=lambda: abrir_modal_creador(mod)).classes('bg-indigo-50 text-indigo-700 shadow-none text-xs')
                    ui.button('Exportar Reporte', icon='picture_as_pdf', on_click=lambda: ui.navigate.to(f'/reportes_inventario/{module_id}', new_tab=True)).classes('bg-green-50 text-green-700 shadow-none text-xs')
                    
                    if module_id.startswith('system_'):
                        ui.button('Módulo Protegido', icon='lock').props('flat disabled size=sm').classes('text-xs text-gray-400')
                    else:
                        def confirmar_borrar_modulo():
                            with ui.dialog() as dlg_confirm, ui.card().classes('w-96 p-6'):
                                ui.label('¿Eliminar esta gestión?').classes('text-lg font-bold mb-2')
                                ui.label('Se borrará de forma permanente el módulo y todos sus registros almacenados. Esta acción no se puede deshacer.').classes('text-xs text-gray-500 mb-6')
                                def proceder_borrado():
                                    success, msg = delete_custom_module(module_id)
                                    if success:
                                        ui.notify(msg, type='positive')
                                        dlg_confirm.close()
                                        state['selected_module'] = None
                                        refrescar_listado_modulos()
                                        dibujar_panel_derecho()
                                    else:
                                        ui.notify(msg, type='negative')
                                with ui.row().classes('w-full justify-end gap-2'):
                                    ui.button('Cancelar', on_click=dlg_confirm.close).props('flat')
                                    ui.button('Sí, Eliminar', on_click=proceder_borrado).classes('bg-red-600 text-white')
                            dlg_confirm.open()
                            
                        ui.button('Eliminar Módulo', icon='delete_forever', on_click=confirmar_borrar_modulo).classes('bg-red-50 text-red-700 shadow-none text-xs')
            
            with ui.row().classes('w-full gap-6 items-start flex-col xl:flex-row'):
                # --- COLUMNA DE REGISTRO (Inputs Dinámicos) ---
                with ui.column().classes('w-full xl:w-5/12 gap-4'):
                    with ui.card().classes('w-full p-6 shadow-sm border border-gray-200 bg-white'):
                        ui.label(f'Agregar {mod["nombre"]}').classes('text-md font-bold mb-4 text-gray-700')
                        
                        # Generador reactivo de inputs
                        inputs_ref = {}
                        
                        # Almacena fotos en progreso para el módulo actual
                        inv_fotos_locales = []
                        # Almacena accesorios en progreso
                        inv_accs_locales = []
                        inv_accs_inputs = []
                        
                        def guardar_accs_locales():
                            inv_accs_locales.clear()
                            for cat_i, nom_i, ser_i, cant_i, est_sel, acc_ref in inv_accs_inputs:
                                inv_accs_locales.append({
                                    'categoria': cat_i.value.strip(),
                                    'nombre': nom_i.value.strip(),
                                    'serial': ser_i.value.strip(),
                                    'cantidad': int(cant_i.value or 1),
                                    'estado': est_sel.value,
                                    'foto': acc_ref.get('foto')
                                })

                        for f_idx, field in enumerate(fields):
                            f_id = field.get('key', f"field_{f_idx}")
                            f_type = field['type']
                            f_label = field['label']
                            
                            if f_type == 'text':
                                inputs_ref[f_id] = ui.input(f_label).classes('w-full mb-3')
                            elif f_type == 'number':
                                inputs_ref[f_id] = ui.number(f_label).classes('w-full mb-3')
                            elif f_type == 'select':
                                inputs_ref[f_id] = ui.select(field['options'], label=f_label).classes('w-full mb-3')
                            elif f_type == 'images':
                                ui.label(f_label).classes('text-xs font-bold text-gray-500 uppercase mt-2 mb-1')
                                
                                async def local_photo_handler(e, list_fotos=inv_fotos_locales):
                                    bytes_f = await e.file.read()
                                    inv_fotos_locales.append(optimize_image(bytes_f))
                                    refrescar_previsualizacion_fotos()
                                    ui.notify('Foto cargada', type='positive')
                                    
                                def refrescar_previsualizacion_fotos():
                                    fotos_preview_box.clear()
                                    with fotos_preview_box:
                                        if inv_fotos_locales:
                                            for idx, f in enumerate(inv_fotos_locales):
                                                with ui.element('div').classes('w-14 h-14 relative border border-gray-200 rounded p-1 bg-gray-50 flex items-center justify-center'):
                                                    ui.image(f).classes('w-full h-full object-cover rounded')
                                                    def borrar_idx(i=idx):
                                                        inv_fotos_locales.pop(i)
                                                        refrescar_previsualizacion_fotos()
                                                    ui.button(icon='close', on_click=borrar_idx).props('flat round size=xs color=red').classes('absolute -top-1 -right-1 bg-white border shadow-sm')

                                with ui.row().classes('w-full gap-1 mb-2 flex-wrap') as fotos_preview_box:
                                    pass
                                    
                                ui.upload(label='Cargar Fotos (.JPG/.PNG)', on_upload=local_photo_handler, auto_upload=True).props('accept=.png,.jpg,.jpeg multiple').classes('w-full mb-4')
                                inputs_ref[f_id] = ('images', inv_fotos_locales)
                                
                            elif f_type == 'linked_data':
                                target_mod_id = field.get('linked_module_id')
                                es_multiple = field.get('linked_multiple', False)
                                target_mod = get_custom_module(target_mod_id) if target_mod_id else None
                                target_nom = target_mod['nombre'] if target_mod else 'Gestión'
                                detalles_vinculados = obtener_detalles_modulo_vinculado(target_mod_id)
                                opciones_vinculadas = {k: v['label'] for k, v in detalles_vinculados.items()}
                                
                                with ui.column().classes('w-full gap-1 mb-3'):
                                    with ui.row().classes('items-center gap-1'):
                                        ui.icon('link', size='xs').classes('text-indigo-600')
                                        ui.label(f"{f_label} (Vinculado a {target_nom})").classes('text-xs font-bold text-gray-700')
                                        if es_multiple:
                                            ui.label('(Múltiple)').classes('text-[10px] text-gray-400 italic')
                                    
                                    val_def = [] if es_multiple else None
                                    props_str = 'use-chips clearable' if es_multiple else 'clearable'
                                    sel_input = ui.select(
                                        options=opciones_vinculadas,
                                        value=val_def,
                                        multiple=es_multiple,
                                        with_input=True
                                    ).classes('w-full text-xs').props(props_str)
                                    inputs_ref[f_id] = ('linked_data', sel_input, es_multiple)
                                    
                                    # Previsualización dinámica interactiva de los equipos anclados seleccionados
                                    linked_preview_box = ui.column().classes('w-full gap-1 mt-1')
                                    def refrescar_linked_preview_box():
                                        linked_preview_box.clear()
                                        val_sel = sel_input.value
                                        items = val_sel if isinstance(val_sel, list) else ([val_sel] if val_sel else [])
                                        if items:
                                            with linked_preview_box:
                                                for itm_k in items:
                                                    det = detalles_vinculados.get(itm_k)
                                                    if det:
                                                        if det.get('es_persona'):
                                                            with ui.row().classes('w-full items-center gap-2 p-2 bg-blue-50/80 border border-blue-200 rounded-lg shadow-xs'):
                                                                with ui.element('div').classes('w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center border border-blue-200 shrink-0'):
                                                                    ui.icon('person', size='sm').classes('text-blue-700')
                                                                with ui.column().classes('flex-grow gap-0.5 overflow-hidden'):
                                                                    ui.label(det.get('nombre', '')).classes('text-xs font-bold text-gray-900 leading-tight truncate w-full')
                                                                    with ui.row().classes('items-center gap-1.5 flex-wrap'):
                                                                        if det.get('rol'):
                                                                            ui.label(f"[{det['rol']}]").classes('text-[10px] text-blue-800 bg-blue-100 font-semibold px-1.5 py-0.5 rounded leading-none')
                                                                        if det.get('correo'):
                                                                            ui.label(f"✉️ {det['correo']}").classes('text-[10px] text-gray-600 leading-none truncate')
                                                                        if det.get('telefono') or det.get('celular'):
                                                                            ui.label(f"📞 {det.get('celular') or det.get('telefono')}").classes('text-[10px] text-gray-600 font-mono leading-none')
                                                        else:
                                                            with ui.row().classes('w-full items-center gap-2 p-2 bg-indigo-50/80 border border-indigo-200 rounded-lg shadow-xs'):
                                                                if det.get('fotos'):
                                                                    thumb_ed = ui.image(det['fotos'][0]).classes('w-10 h-10 rounded-md object-cover border border-indigo-200 cursor-pointer shadow-xs shrink-0')
                                                                    thumb_ed.on('click', lambda _, lp=det.get('nombre', 'Equipo'), fl=det['fotos']: abrir_visor_lightbox(lp, fl))
                                                                else:
                                                                    with ui.element('div').classes('w-10 h-10 rounded-md bg-indigo-100 flex items-center justify-center border border-indigo-200 shrink-0'):
                                                                        ui.icon('devices', size='sm').classes('text-indigo-600')
                                                                
                                                                with ui.column().classes('flex-grow gap-0.5 overflow-hidden'):
                                                                    ui.label(det.get('nombre', '')).classes('text-xs font-bold text-gray-900 leading-tight truncate w-full')
                                                                    with ui.row().classes('items-center gap-1 flex-wrap'):
                                                                        if det.get('serial'):
                                                                            ui.label(f"S/N: {det['serial']}").classes('text-[10px] text-gray-700 font-mono bg-white px-1.5 py-0.5 border border-indigo-200 rounded leading-none')
                                                                        if det.get('cantidad') is not None:
                                                                            ui.label(f"Cant: {det['cantidad']}").classes('text-[10px] font-bold text-indigo-800 bg-indigo-200/80 px-1.5 py-0.5 rounded leading-none')
                                                                        if det.get('categoria'):
                                                                            ui.label(f"[{det['categoria']}]").classes('text-[10px] text-indigo-600 font-medium leading-none')
                                                                        if det.get('estado'):
                                                                            ui.label(f"• {det['estado']}").classes('text-[10px] text-emerald-700 font-semibold leading-none')
                                    
                                    sel_input.on('update:model-value', lambda _: refrescar_linked_preview_box())
                                
                            elif f_type == 'accessories':
                                ui.label(f_label).classes('text-xs font-bold text-gray-500 uppercase mt-2 mb-1')
                                accs_box = ui.column().classes('w-full gap-0')
                                
                                def refrescar_accs_ui():
                                    accs_box.clear()
                                    inv_accs_inputs.clear()
                                    with accs_box:
                                        if not inv_accs_locales:
                                            ui.label('Sin accesorios').classes('text-xs text-gray-400 italic mb-2')
                                        for idx, acc in enumerate(inv_accs_locales):
                                            with ui.card().classes('w-full p-2 bg-gray-50 border border-gray-200 shadow-none mb-2 gap-1'):
                                                with ui.row().classes('w-full items-center gap-1 flex-nowrap'):
                                                    cat_i = ui.input('Categoría', value=acc.get('categoria', '')).classes('w-1/5 text-xs')
                                                    nom_i = ui.input('Modelo / Nombre', value=acc.get('nombre', '')).classes('flex-grow text-xs')
                                                    ser_i = ui.input('S/N', value=acc.get('serial', '')).classes('w-1/5 text-xs')
                                                    cant_i = ui.number('Cant.', value=acc.get('cantidad', 1), min=1, precision=0).classes('w-16 text-xs')
                                                    est_sel = ui.select(['En uso', 'En bodega', 'Dañado', 'En reparación', 'De baja'], value=acc.get('estado', 'En uso'), label='Estado').classes('w-1/5 text-xs')
                                                    def borrar_fila_acc(i=idx):
                                                        guardar_accs_locales()
                                                        inv_accs_locales.pop(i)
                                                        refrescar_accs_ui()
                                                    ui.button(icon='delete', on_click=borrar_fila_acc).props('flat color=red round size=sm')
                                                
                                                with ui.row().classes('w-full items-center gap-2 mt-1 flex-nowrap'):
                                                    if acc.get('foto'):
                                                        with ui.element('div').classes('w-9 h-9 relative border rounded overflow-hidden shrink-0'):
                                                            ui.image(acc['foto']).classes('w-full h-full object-cover')
                                                            def quitar_foto_acc(acc_ref=acc):
                                                                acc_ref['foto'] = None
                                                                refrescar_accs_ui()
                                                            ui.button(icon='close', on_click=quitar_foto_acc).props('flat round size=xs color=red').classes('absolute -top-1 -right-1 bg-white border shadow-sm')
                                                    
                                                    async def upload_acc_photo(e, acc_ref=acc):
                                                        bytes_f = await e.file.read()
                                                        acc_ref['foto'] = optimize_image(bytes_f)
                                                        refrescar_accs_ui()
                                                        ui.notify('Foto de accesorio cargada', type='positive')
                                                        
                                                    ui.upload(label='Adjuntar Foto de Accesorio (.JPG/.PNG)', on_upload=upload_acc_photo, auto_upload=True).props('accept=.png,.jpg,.jpeg').classes('flex-grow text-xs')
                                                    inv_accs_inputs.append((cat_i, nom_i, ser_i, cant_i, est_sel, acc))
                                                
                                refrescar_accs_ui()
                                
                                def agregar_fila_acc():
                                    guardar_accs_locales()
                                    inv_accs_locales.append({'categoria': '', 'nombre': '', 'serial': '', 'cantidad': 1, 'estado': 'En uso', 'foto': None})
                                    refrescar_accs_ui()
                                    
                                ui.button('Añadir Item', icon='add', on_click=agregar_fila_acc).classes('bg-blue-50 text-blue-700 shadow-none mb-4 px-3 py-1 text-xs')
                                inputs_ref[f_id] = ('accessories', inv_accs_locales, guardar_accs_locales, refrescar_accs_ui)
                        
                        def guardar_nuevo_registro():
                            record_data = {}
                            
                            for f_idx, field in enumerate(fields):
                                f_id = field.get('key', f"field_{f_idx}")
                                f_type = field['type']
                                
                                if f_type in ['text', 'number', 'select']:
                                    record_data[f_id] = inputs_ref[f_id].value
                                elif f_type == 'linked_data':
                                    sel_ref = inputs_ref[f_id][1]
                                    val_link = sel_ref.value
                                    record_data[f_id] = val_link if val_link else None
                                elif f_type == 'images':
                                    # Leer directamente de la lista
                                    list_fotos = inputs_ref[f_id][1]
                                    record_data[f_id] = list_fotos if list_fotos else None
                                elif f_type == 'accessories':
                                    # Guardar temporales antes de leer
                                    guardar_accs_fn = inputs_ref[f_id][2]
                                    guardar_accs_fn()
                                    list_accs = inputs_ref[f_id][1]
                                    accs_filtrados = [a for a in list_accs if a.get('nombre', '').strip() or a.get('categoria', '').strip()]
                                    record_data[f_id] = accs_filtrados if accs_filtrados else None
                                    
                            # Validar que al menos un campo tenga datos
                            if not any(v for v in record_data.values()):
                                ui.notify('Debes rellenar al menos un campo del formulario', type='warning')
                                return
                                
                            success, msg = add_custom_record(module_id, record_data)
                            if success:
                                ui.notify(msg, type='positive')
                                # Resetear entradas
                                for f_idx, field in enumerate(fields):
                                    f_id = field.get('key', f"field_{f_idx}")
                                    f_type = field['type']
                                    if f_type in ['text', 'number', 'select']:
                                        inputs_ref[f_id].value = None
                                    elif f_type == 'linked_data':
                                        sel_ref = inputs_ref[f_id][1]
                                        es_mult = inputs_ref[f_id][2]
                                        sel_ref.value = [] if es_mult else None
                                    elif f_type == 'images':
                                        inputs_ref[f_id][1].clear()
                                        refrescar_previsualizacion_fotos()
                                    elif f_type == 'accessories':
                                        inputs_ref[f_id][1].clear()
                                        refrescar_accs_ui = inputs_ref[f_id][3]
                                        refrescar_accs_ui()
                                refrescar_listado_registros()
                            else:
                                ui.notify(msg, type='negative')
                        
                        ui.button('Guardar Registro', icon='save', on_click=guardar_nuevo_registro).classes('w-full bg-green-600 text-white font-bold rounded-lg shadow-sm py-2 mt-2')

                # --- COLUMNA DE REGISTROS GUARDADOS ---
                records_wrapper = ui.column().classes('w-full xl:w-7/12 flex-grow gap-2')
                
                with records_wrapper:
                    # Barra de Filtros y Búsqueda
                    with ui.row().classes('w-full justify-between items-center gap-2 bg-white p-3 rounded-lg border border-gray-200 shadow-sm flex-wrap sm:flex-nowrap mb-2'):
                        search_input = ui.input(placeholder='Buscar por nombre, serial...').props('dense clearable icon=search debounce="300"').classes('flex-grow text-xs')
                        category_select = ui.select(options=['Todas las categorías'], value='Todas las categorías', label='Categoría').props('dense options-dense').classes('w-36 sm:w-44 text-xs')
                        contenedor_select = ui.select(options=['Todos los contenedores'], value='Todos los contenedores', label='Contenedor / Grupo').props('dense options-dense').classes('w-36 sm:w-44 text-xs')
                        
                    records_container = ui.column().classes('w-full gap-2')
                    
                    registros_cache = {'datos': None, 'detalles_modulos': {}, 'opciones_modulos': {}, 'opciones_cat': [], 'opciones_cont': []}
                    
                    search_input.on('update:model-value', lambda _: refrescar_listado_registros(recargar_db=False))
                    category_select.on('update:model-value', lambda _: refrescar_listado_registros(recargar_db=False))
                    contenedor_select.on('update:model-value', lambda _: refrescar_listado_registros(recargar_db=False))
                
                def refrescar_listado_registros(recargar_db=True):
                    records_container.clear()
                    if recargar_db or registros_cache['datos'] is None:
                        registros_cache['datos'] = get_all_custom_records(module_id)
                        
                        # Precarga de opciones y detalles para campos de tipo linked_data
                        cache_detalles = {}
                        cache_opciones = {}
                        for f in fields:
                            if f.get('type') == 'linked_data' and f.get('linked_module_id'):
                                mid = f['linked_module_id']
                                if mid not in cache_detalles:
                                    cache_detalles[mid] = obtener_detalles_modulo_vinculado(mid)
                                    cache_opciones[mid] = {k: v['label'] for k, v in cache_detalles[mid].items()}
                        registros_cache['detalles_modulos'] = cache_detalles
                        registros_cache['opciones_modulos'] = cache_opciones
                    
                    todos_registros = registros_cache['datos']
                    cache_detalles_modulos = registros_cache['detalles_modulos']
                    cache_opciones_modulos = registros_cache['opciones_modulos']
                    
                    # Detectar campo de categoría y campo de contenedor/grupo
                    cat_field_key = None
                    cont_field_key = None
                    for f_idx, field in enumerate(fields):
                        lbl_l = field['label'].lower()
                        if 'cat' in lbl_l and not cat_field_key:
                            cat_field_key = field.get('key', f"field_{f_idx}")
                        elif any(k in lbl_l for k in ['contenedor', 'grupo', 'ubicacion', 'locacion']) and not cont_field_key:
                            cont_field_key = field.get('key', f"field_{f_idx}")
                    
                    # Extraer categorías únicas disponibles (tanto principales como de accesorios/sub-ítems)
                    if recargar_db or not registros_cache['opciones_cat']:
                        categorias_existentes = set()
                        for reg in todos_registros:
                            if cat_field_key:
                                cat_val = reg['data'].get(cat_field_key)
                                if cat_val and isinstance(cat_val, str) and cat_val.strip():
                                    categorias_existentes.add(cat_val.strip())
                            for val in reg['data'].values():
                                if isinstance(val, list):
                                    for item in val:
                                        if isinstance(item, dict) and item.get('categoria'):
                                            if str(item['categoria']).strip():
                                                categorias_existentes.add(str(item['categoria']).strip())
                        
                        opciones_cat = ['Todas las categorías'] + sorted(list(categorias_existentes))
                        registros_cache['opciones_cat'] = opciones_cat
                        if category_select.options != opciones_cat:
                            category_select.options = opciones_cat
                            if category_select.value not in opciones_cat:
                                category_select.value = 'Todas las categorías'

                    # Extraer contenedores / grupos únicos disponibles
                    if recargar_db or not registros_cache['opciones_cont']:
                        cont_existentes = set()
                        if cont_field_key:
                            for reg in todos_registros:
                                cval = reg['data'].get(cont_field_key)
                                if cval and isinstance(cval, str) and cval.strip():
                                    cont_existentes.add(cval.strip())
                        opciones_cont = ['Todos los contenedores'] + sorted(list(cont_existentes))
                        registros_cache['opciones_cont'] = opciones_cont
                        if contenedor_select.options != opciones_cont:
                            contenedor_select.options = opciones_cont
                            if contenedor_select.value not in opciones_cont:
                                contenedor_select.value = 'Todos los contenedores'
                            
                    # Filtrar registros
                    cat_filtro = category_select.value
                    cont_filtro = contenedor_select.value
                    busqueda_txt = (search_input.value or '').strip().lower()
                    
                    registros = []
                    for reg in todos_registros:
                        # 0. Filtro por Contenedor / Grupo
                        if cont_filtro and cont_filtro != 'Todos los contenedores':
                            if cont_field_key:
                                val_c = str(reg['data'].get(cont_field_key, '')).strip()
                                if val_c.lower() != cont_filtro.lower():
                                    continue

                        # 1. Filtro por categoría (revisa campo principal y sub-ítems del kit)
                        if cat_filtro and cat_filtro != 'Todas las categorías':
                            coincide_cat = False
                            if cat_field_key:
                                cat_val = str(reg['data'].get(cat_field_key, '')).strip()
                                if cat_val.lower() == cat_filtro.lower():
                                    coincide_cat = True
                            if not coincide_cat:
                                for val in reg['data'].values():
                                    if isinstance(val, list):
                                        for item in val:
                                            if isinstance(item, dict) and item.get('categoria'):
                                                if str(item['categoria']).strip().lower() == cat_filtro.lower():
                                                    coincide_cat = True
                                                    break
                                        if coincide_cat:
                                            break
                            if not coincide_cat:
                                continue
                                
                        # 2. Filtro por texto de búsqueda
                        if busqueda_txt:
                            manda_match = False
                            for val in reg['data'].values():
                                if not val:
                                    continue
                                if isinstance(val, str):
                                    if busqueda_txt in val.lower():
                                        manda_match = True
                                        break
                                    # Revisar si es una clave de datos vinculados
                                    for opts_m in cache_opciones_modulos.values():
                                        if val in opts_m and busqueda_txt in opts_m[val].lower():
                                            manda_match = True
                                            break
                                    if manda_match:
                                        break
                                elif isinstance(val, (int, float)) and busqueda_txt in str(val):
                                    manda_match = True
                                    break
                                elif isinstance(val, list):
                                    for item in val:
                                        if isinstance(item, dict):
                                            if (busqueda_txt in str(item.get('categoria', '')).lower() or 
                                                busqueda_txt in str(item.get('nombre', '')).lower() or 
                                                busqueda_txt in str(item.get('serial', '')).lower() or
                                                busqueda_txt in str(item.get('estado', '')).lower()):
                                                manda_match = True
                                                break
                                        elif isinstance(item, str):
                                            if busqueda_txt in item.lower():
                                                manda_match = True
                                                break
                                            for opts_m in cache_opciones_modulos.values():
                                                if item in opts_m and busqueda_txt in opts_m[item].lower():
                                                    manda_match = True
                                                    break
                                            if manda_match:
                                                break
                                    if manda_match:
                                        break
                            if not manda_match:
                                continue
                                
                        registros.append(reg)
                    
                    def abrir_visor_lightbox(record_title, array_fotos):
                        with ui.dialog() as dlg_light, ui.card().classes('w-[500px] p-6 bg-white items-center'):
                            with ui.row().classes('w-full justify-between items-center mb-4'):
                                ui.label(record_title).classes('text-lg font-bold text-gray-800')
                                ui.button(icon='close', on_click=dlg_light.close).props('flat round size=sm')
                            
                            if len(array_fotos) > 1:
                                with ui.carousel(animated=True, arrows=True, navigation=True).classes('w-full h-80 rounded bg-gray-100 shadow-inner'):
                                    for f in array_fotos:
                                        with ui.carousel_slide().classes('p-0 items-center justify-center'):
                                            ui.image(f).classes('h-full object-contain')
                            elif array_fotos:
                                ui.image(array_fotos[0]).classes('w-full max-h-80 object-contain rounded')
                        dlg_light.open()
                        
                    def abrir_dialogo_edicion(reg):
                        with ui.dialog() as dlg_edit, ui.card().classes('w-[450px] p-6 max-h-[85vh] overflow-y-auto bg-gray-50'):
                            ui.label(f"Editar Registro").classes('text-xl font-bold mb-4 border-b pb-2 text-gray-800')
                            
                            edit_inputs = {}
                            edit_fotos_array = reg['data'].get('field_images', []) # Dummy/Fallback
                            edit_accs_array = []
                            edit_accs_inputs = []
                            
                            def guardar_edit_accs_temporales():
                                edit_accs_array.clear()
                                for cat_i, nom_i, ser_i, cant_i, est_sel, acc_ref in edit_accs_inputs:
                                    edit_accs_array.append({
                                        'categoria': cat_i.value.strip(),
                                        'nombre': nom_i.value.strip(),
                                        'serial': ser_i.value.strip(),
                                        'cantidad': int(cant_i.value or 1),
                                        'estado': est_sel.value,
                                        'foto': acc_ref.get('foto')
                                    })

                            for f_idx, field in enumerate(fields):
                                f_id = field.get('key', f"field_{f_idx}")
                                f_type = field['type']
                                f_label = field['label']
                                valor_actual = reg['data'].get(f_id)
                                
                                if f_type == 'text':
                                    edit_inputs[f_id] = ui.input(f_label, value=valor_actual).classes('w-full mb-3')
                                elif f_type == 'number':
                                    edit_inputs[f_id] = ui.number(f_label, value=valor_actual).classes('w-full mb-3')
                                elif f_type == 'select':
                                    opts = list(field.get('options') or [])
                                    if valor_actual and valor_actual not in opts:
                                        opts.append(valor_actual)
                                    edit_inputs[f_id] = ui.select(opts, value=valor_actual, label=f_label).classes('w-full mb-3')
                                elif f_type == 'images':
                                    ui.label(f_label).classes('text-xs font-bold text-gray-500 uppercase mt-2 mb-1')
                                    edit_fotos_array = valor_actual if valor_actual else []
                                    
                                    async def edit_photo_handler(e, list_fotos=edit_fotos_array):
                                        bytes_f = await e.file.read()
                                        edit_fotos_array.append(optimize_image(bytes_f))
                                        refrescar_edit_photos()
                                        ui.notify('Foto añadida', type='positive')
                                        
                                    def refrescar_edit_photos():
                                        edit_photos_box.clear()
                                        with edit_photos_box:
                                            if edit_fotos_array:
                                                for idx, f in enumerate(edit_fotos_array):
                                                    with ui.element('div').classes('w-14 h-14 relative border border-gray-200 rounded p-1 bg-gray-50 flex items-center justify-center'):
                                                        ui.image(f).classes('w-full h-full object-cover rounded')
                                                        def borrar_edit_idx(i=idx):
                                                            edit_fotos_array.pop(i)
                                                            refrescar_edit_photos()
                                                        ui.button(icon='close', on_click=borrar_edit_idx).props('flat round size=xs color=red').classes('absolute -top-1 -right-1 bg-white border shadow-sm')

                                    with ui.row().classes('w-full gap-1 mb-2 flex-wrap') as edit_photos_box:
                                        pass
                                        
                                    refrescar_edit_photos()
                                    ui.upload(label='Añadir Fotos (.JPG/.PNG)', on_upload=edit_photo_handler, auto_upload=True).props('accept=.png,.jpg,.jpeg multiple').classes('w-full mb-4')
                                    edit_inputs[f_id] = ('images', edit_fotos_array)
                                    
                                elif f_type == 'linked_data':
                                    target_mod_id = field.get('linked_module_id')
                                    es_multiple = field.get('linked_multiple', False)
                                    target_mod = get_custom_module(target_mod_id) if target_mod_id else None
                                    target_nom = target_mod['nombre'] if target_mod else 'Gestión'
                                    detalles_vinculados = obtener_detalles_modulo_vinculado(target_mod_id)
                                    opciones_vinculadas = {k: v['label'] for k, v in detalles_vinculados.items()}
                                    
                                    with ui.column().classes('w-full gap-1 mb-3'):
                                        with ui.row().classes('items-center gap-1'):
                                            ui.icon('link', size='xs').classes('text-indigo-600')
                                            ui.label(f"{f_label} (Vinculado a {target_nom})").classes('text-xs font-bold text-gray-700')
                                            if es_multiple:
                                                ui.label('(Múltiple)').classes('text-[10px] text-gray-400 italic')
                                        
                                        val_init = valor_actual
                                        if es_multiple:
                                            if not isinstance(val_init, list):
                                                val_init = [val_init] if val_init else []
                                            val_init = [v for v in val_init if v in opciones_vinculadas]
                                        else:
                                            if val_init not in opciones_vinculadas:
                                                val_init = None
                                            
                                        props_str = 'use-chips clearable' if es_multiple else 'clearable'
                                        edit_sel = ui.select(
                                            options=opciones_vinculadas,
                                            value=val_init,
                                            multiple=es_multiple,
                                            with_input=True
                                        ).classes('w-full text-xs').props(props_str)
                                        edit_inputs[f_id] = ('linked_data', edit_sel, es_multiple)
                                        
                                        # Previsualización dinámica en edición
                                        edit_linked_preview_box = ui.column().classes('w-full gap-1 mt-1')
                                        def refrescar_edit_linked_preview():
                                            edit_linked_preview_box.clear()
                                            val_sel = edit_sel.value
                                            items = val_sel if isinstance(val_sel, list) else ([val_sel] if val_sel else [])
                                            if items:
                                                with edit_linked_preview_box:
                                                    for itm_k in items:
                                                        det = detalles_vinculados.get(itm_k)
                                                        if det:
                                                            with ui.row().classes('w-full items-center gap-2 p-2 bg-indigo-50/80 border border-indigo-200 rounded-lg shadow-xs'):
                                                                if det.get('fotos'):
                                                                    thumb_ed = ui.image(det['fotos'][0]).classes('w-10 h-10 rounded-md object-cover border border-indigo-200 cursor-pointer shadow-xs')
                                                                    thumb_ed.on('click', lambda _, lp=det.get('nombre', 'Equipo'), fl=det['fotos']: abrir_visor_lightbox(lp, fl))
                                                                else:
                                                                    with ui.element('div').classes('w-10 h-10 rounded-md bg-indigo-100 flex items-center justify-center border border-indigo-200'):
                                                                        ui.icon('devices', size='sm').classes('text-indigo-600')
                                                                
                                                                with ui.column().classes('flex-grow gap-0.5 overflow-hidden'):
                                                                    ui.label(det.get('nombre', '')).classes('text-xs font-bold text-gray-900 leading-tight truncate w-full')
                                                                    with ui.row().classes('items-center gap-1 flex-wrap'):
                                                                        if det.get('serial'):
                                                                            ui.label(f"S/N: {det['serial']}").classes('text-[10px] text-gray-700 font-mono bg-white px-1.5 py-0.5 border border-indigo-200 rounded leading-none')
                                                                        if det.get('cantidad') is not None:
                                                                            ui.label(f"Cant: {det['cantidad']}").classes('text-[10px] font-bold text-indigo-800 bg-indigo-200/80 px-1.5 py-0.5 rounded leading-none')
                                                                        if det.get('categoria'):
                                                                            ui.label(f"[{det['categoria']}]").classes('text-[10px] text-indigo-600 font-medium leading-none')
                                                                        if det.get('estado'):
                                                                            ui.label(f"• {det['estado']}").classes('text-[10px] text-emerald-700 font-semibold leading-none')
                                        
                                        edit_sel.on('update:model-value', lambda _: refrescar_edit_linked_preview())
                                        refrescar_edit_linked_preview()

                                elif f_type == 'accessories':
                                    ui.label(f_label).classes('text-xs font-bold text-gray-500 uppercase mt-2 mb-1')
                                    edit_accs_array = valor_actual if valor_actual else []
                                    edit_accs_box = ui.column().classes('w-full gap-0')
                                    
                                    def refrescar_edit_accs():
                                        edit_accs_box.clear()
                                        edit_accs_inputs.clear()
                                        with edit_accs_box:
                                            if not edit_accs_array:
                                                ui.label('Sin accesorios').classes('text-xs text-gray-400 italic mb-2')
                                            for idx, acc in enumerate(edit_accs_array):
                                                with ui.card().classes('w-full p-2 bg-gray-50 border border-gray-200 shadow-none mb-2 gap-1'):
                                                    with ui.row().classes('w-full items-center gap-1 flex-nowrap'):
                                                        cat_i = ui.input('Categoría', value=acc.get('categoria', '')).classes('w-1/5 text-xs')
                                                        nom_i = ui.input('Modelo / Nombre', value=acc.get('nombre', '')).classes('flex-grow text-xs')
                                                        ser_i = ui.input('S/N', value=acc.get('serial', '')).classes('w-1/5 text-xs')
                                                        cant_i = ui.number('Cant.', value=acc.get('cantidad', 1), min=1, precision=0).classes('w-16 text-xs')
                                                        est_sel = ui.select(['En uso', 'En bodega', 'Dañado', 'En reparación', 'De baja'], value=acc.get('estado', 'En uso'), label='Estado').classes('w-1/5 text-xs')
                                                        def borrar_edit_acc_idx(i=idx):
                                                            guardar_edit_accs_temporales()
                                                            edit_accs_array.pop(i)
                                                            refrescar_edit_accs()
                                                        ui.button(icon='delete', on_click=borrar_edit_acc_idx).props('flat color=red round size=sm')
                                                    
                                                    with ui.row().classes('w-full items-center gap-2 mt-1 flex-nowrap'):
                                                        if acc.get('foto'):
                                                            with ui.element('div').classes('w-9 h-9 relative border rounded overflow-hidden shrink-0'):
                                                                ui.image(acc['foto']).classes('w-full h-full object-cover')
                                                                def quitar_edit_foto_acc(acc_ref=acc):
                                                                    acc_ref['foto'] = None
                                                                    refrescar_edit_accs()
                                                                ui.button(icon='close', on_click=quitar_edit_foto_acc).props('flat round size=xs color=red').classes('absolute -top-1 -right-1 bg-white border shadow-sm')
                                                        
                                                        async def upload_edit_acc_photo(e, acc_ref=acc):
                                                            bytes_f = await e.file.read()
                                                            acc_ref['foto'] = optimize_image(bytes_f)
                                                            refrescar_edit_accs()
                                                            ui.notify('Foto de accesorio agregada', type='positive')
                                                            
                                                        ui.upload(label='Adjuntar Foto de Accesorio (.JPG/.PNG)', on_upload=upload_edit_acc_photo, auto_upload=True).props('accept=.png,.jpg,.jpeg').classes('flex-grow text-xs')
                                                        edit_accs_inputs.append((cat_i, nom_i, ser_i, cant_i, est_sel, acc))
                                                    
                                    refrescar_edit_accs()
                                    
                                    def agregar_edit_acc_fila():
                                        guardar_edit_accs_temporales()
                                        edit_accs_array.append({'categoria': '', 'nombre': '', 'serial': '', 'cantidad': 1, 'estado': 'En uso', 'foto': None})
                                        refrescar_edit_accs()
                                        
                                    ui.button('Añadir Item', icon='add', on_click=agregar_edit_acc_fila).classes('bg-blue-50 text-blue-700 shadow-none mb-4 px-3 py-1 text-xs')
                                    edit_inputs[f_id] = ('accessories', edit_accs_array)
                            
                            def guardar_cambios_registro():
                                updated_data = {}
                                for f_idx, field in enumerate(fields):
                                    f_id = field.get('key', f"field_{f_idx}")
                                    f_type = field['type']
                                    
                                    if f_type in ['text', 'number', 'select']:
                                        updated_data[f_id] = edit_inputs[f_id].value
                                    elif f_type == 'linked_data':
                                        val_link = edit_inputs[f_id][1].value
                                        updated_data[f_id] = val_link if val_link else None
                                    elif f_type == 'images':
                                        updated_data[f_id] = edit_inputs[f_id][1]
                                    elif f_type == 'accessories':
                                        guardar_edit_accs_temporales()
                                        list_accs = edit_inputs[f_id][1]
                                        accs_filtrados = [a for a in list_accs if a.get('nombre', '').strip() or a.get('categoria', '').strip()]
                                        updated_data[f_id] = accs_filtrados if accs_filtrados else None
                                        
                                success, msg = update_custom_record(reg['id'], updated_data)
                                if success:
                                    ui.notify(msg, type='positive')
                                    dlg_edit.close()
                                    refrescar_listado_registros()
                                else:
                                    ui.notify(msg, type='negative')
                                    
                            with ui.row().classes('w-full justify-end gap-2 border-t pt-4 mt-6'):
                                ui.button('Cancelar', on_click=dlg_edit.close).props('flat')
                                ui.button('Guardar Cambios', on_click=guardar_cambios_registro).classes('bg-indigo-600 text-white font-bold')
                                
                        dlg_edit.open()

                    with records_container:
                        if not registros:
                            with ui.column().classes('w-full h-40 items-center justify-center border border-dashed border-gray-300 rounded-lg bg-white p-4'):
                                ui.icon('assignment_late', size='md').classes('text-gray-300 mb-1')
                                ui.label('No hay registros. Crea el primero a la izquierda.').classes('text-xs text-gray-400 italic')
                        else:
                            for reg in registros:
                                # Buscar campo de fotos y accesorios si los hay
                                fotos_del_registro = []
                                accs_del_registro = []
                                label_principal = ""
                                otras_filas_datos = []
                                campos_vinculados = []
                                
                                for f_idx, field in enumerate(fields):
                                    f_id = field.get('key', f"field_{f_idx}")
                                    f_type = field['type']
                                    f_label = field['label']
                                    val = reg['data'].get(f_id)
                                    
                                    if not val:
                                        continue
                                        
                                    if f_type == 'images':
                                        fotos_del_registro = val
                                    elif f_type == 'accessories':
                                        accs_del_registro = val
                                    elif f_type == 'linked_data':
                                        target_mid = field.get('linked_module_id')
                                        items_claves = val if isinstance(val, list) else [val]
                                        items_validos = [k for k in items_claves if k]
                                        if items_validos:
                                            campos_vinculados.append((f_label, target_mid, items_validos))
                                            if not label_principal and not field.get('linked_multiple', False):
                                                det_primer = cache_detalles_modulos.get(target_mid, {}).get(items_validos[0])
                                                label_principal = det_primer['nombre'] if det_primer else str(items_validos[0])
                                    elif f_type in ['text', 'number', 'select']:
                                        if not label_principal:
                                            label_principal = f"{val}"
                                        else:
                                            otras_filas_datos.append((f_label, val))
                                
                                if not label_principal:
                                    label_principal = f"Registro #{reg['id']}"

                                # Comprobar si se busca un sub-equipo/accesorio específico dentro del kit
                                accs_coincidentes = []
                                es_busqueda_kit = ('kit' in busqueda_txt) if busqueda_txt else False
                                
                                if accs_del_registro and not es_busqueda_kit:
                                    for a in accs_del_registro:
                                        match_cat = (cat_filtro and cat_filtro != 'Todas las categorías' and str(a.get('categoria', '')).strip().lower() == cat_filtro.lower())
                                        match_txt = (busqueda_txt and (
                                            busqueda_txt in str(a.get('categoria', '')).lower() or 
                                            busqueda_txt in str(a.get('nombre', '')).lower() or 
                                            busqueda_txt in str(a.get('serial', '')).lower() or
                                            busqueda_txt in str(a.get('estado', '')).lower()
                                        ))
                                        if match_cat or match_txt:
                                            accs_coincidentes.append(a)

                                if accs_coincidentes:
                                    # DESGLOSE INDIVIDUAL DE SUB-EQUIPO CON SU PROPIA FOTO Y CINTA DE PERTENENCIA A KIT
                                    for acc_match in accs_coincidentes:
                                        with ui.card().classes('w-full p-0 bg-white shadow-sm border border-indigo-200 hover:shadow-md transition-shadow rounded-lg overflow-hidden mb-3'):
                                            # Banner / Cinta Superior de Pertenencia
                                            with ui.row().classes('w-full bg-gradient-to-r from-indigo-700 via-indigo-600 to-purple-600 text-white px-3 py-1.5 text-xs font-bold items-center justify-between shadow-sm'):
                                                with ui.row().classes('items-center gap-1.5'):
                                                    ui.icon('extension', size='xs').classes('text-yellow-300')
                                                    ui.label(f"Componente de Kit: {label_principal}")
                                                ui.label('UNIDAD DEL KIT').classes('text-[9px] bg-white/20 px-1.5 py-0.5 rounded tracking-wider uppercase font-extrabold')
                                            
                                            with ui.row().classes('w-full p-4 items-center gap-4'):
                                                # Foto propia del accesorio (o foto del kit / icono)
                                                foto_acc = acc_match.get('foto')
                                                if foto_acc:
                                                    thumb_acc = ui.image(foto_acc).classes('w-16 h-16 rounded-lg object-cover shadow-sm border border-gray-100 cursor-pointer')
                                                    thumb_acc.on('click', lambda _, lp=acc_match.get('nombre', 'Accesorio'), fl=[foto_acc]: abrir_visor_lightbox(lp, fl))
                                                elif fotos_del_registro:
                                                    thumb_acc = ui.image(fotos_del_registro[0]).classes('w-16 h-16 rounded-lg object-cover shadow-sm border border-gray-100 cursor-pointer')
                                                    thumb_acc.on('click', lambda _, lp=label_principal, fl=fotos_del_registro: abrir_visor_lightbox(lp, fl))
                                                else:
                                                    with ui.column().classes('w-16 h-16 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100'):
                                                        ui.icon('photo_camera', size='sm').classes('text-indigo-400')
                                                        
                                                # Datos del accesorio desglosado
                                                with ui.column().classes('flex-grow gap-0.5'):
                                                    ui.label(acc_match.get('nombre') or 'Accesorio sin nombre').classes('font-bold text-gray-900 text-base')
                                                    if acc_match.get('categoria'):
                                                        ui.label(f"Categoría: {acc_match['categoria']}").classes('text-xs text-indigo-700 font-semibold')
                                                    if acc_match.get('serial'):
                                                        ui.label(f"Número de Serie (S/N): {acc_match['serial']}").classes('text-xs text-gray-600')
                                                    ui.label(f"Cantidad: {acc_match.get('cantidad', 1)}").classes('text-xs text-gray-700 font-semibold')
                                                    if acc_match.get('estado'):
                                                        ui.label(f"Estado del Artículo: {acc_match['estado']}").classes('text-xs font-bold text-emerald-700')
                                                        
                                                # Acciones (Editar kit contenedor)
                                                with ui.row().classes('gap-0 self-start'):
                                                    ui.button(icon='edit', on_click=lambda r=reg: abrir_dialogo_edicion(r)).props('flat color=blue round size=sm').tooltip('Editar Kit Contenedor')
                                else:
                                    # RENDERIZADO MASTER HABITUAL DEL KIT
                                    with ui.card().classes('w-full p-4 flex flex-row items-center bg-white shadow-sm border-l-4 border-indigo-500 hover:shadow-md transition-shadow gap-4 mb-3'):
                                        
                                        # Renderizado de la Miniatura/Foto del Registro
                                        if fotos_del_registro:
                                            if len(fotos_del_registro) > 1:
                                                with ui.element('div').classes('w-16 h-16 relative cursor-pointer') as photo_box:
                                                    photo_box.on('click', lambda _, lp=label_principal, fl=fotos_del_registro: abrir_visor_lightbox(lp, fl))
                                                    ui.image(fotos_del_registro[0]).classes('w-full h-full object-cover rounded-lg border border-gray-100')
                                                    with ui.element('div').classes('absolute bottom-0.5 right-0.5 bg-black/60 text-white text-[10px] px-1 rounded font-bold'):
                                                        ui.label(f"+{len(fotos_del_registro)-1}")
                                            else:
                                                thumb = ui.image(fotos_del_registro[0]).classes('w-16 h-16 rounded-lg object-cover shadow-sm border border-gray-100 cursor-pointer')
                                                thumb.on('click', lambda _, lp=label_principal, fl=fotos_del_registro: abrir_visor_lightbox(lp, fl))
                                        else:
                                            with ui.column().classes('w-16 h-16 rounded-lg bg-gray-100 flex items-center justify-center border border-gray-200'):
                                                ui.icon(mod['icono'], size='sm').classes('text-gray-400')
                                                
                                        # Información de texto dinámica
                                        with ui.column().classes('flex-grow gap-0.5'):
                                            ui.label(label_principal).classes('font-bold text-gray-800 text-base')
                                            
                                            for lbl, value in otras_filas_datos:
                                                ui.label(f"{lbl}: {value}").classes('text-xs text-gray-500')
                                                
                                            for lbl, target_mid, items_keys in campos_vinculados:
                                                with ui.column().classes('w-full gap-1.5 mt-2'):
                                                    with ui.row().classes('items-center gap-1.5'):
                                                        ui.icon('link', size='xs').classes('text-indigo-600')
                                                        ui.label(f"{lbl}:").classes('text-xs font-bold text-gray-700')
                                                        ui.label(f"({len(items_keys)} ítems)").classes('text-[10px] text-gray-400 font-normal')
                                                    
                                                    with ui.row().classes('w-full gap-2 flex-wrap'):
                                                        for itm_k in items_keys:
                                                            det = cache_detalles_modulos.get(target_mid, {}).get(itm_k)
                                                            if det:
                                                                if det.get('es_persona'):
                                                                    with ui.row().classes('items-center gap-2 bg-gradient-to-r from-blue-50/90 to-slate-50 border border-blue-200 text-blue-950 p-2 rounded-lg text-xs shadow-xs'):
                                                                        with ui.element('div').classes('w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center border border-blue-200 shrink-0'):
                                                                            ui.icon('person', size='xs').classes('text-blue-700')
                                                                        with ui.column().classes('gap-0.5 overflow-hidden'):
                                                                            ui.label(det.get('nombre', '')).classes('text-xs font-bold text-gray-900 leading-tight truncate')
                                                                            with ui.row().classes('items-center gap-1.5 flex-wrap'):
                                                                                if det.get('rol'):
                                                                                    ui.label(f"[{det['rol']}]").classes('text-[9.5px] text-blue-800 bg-blue-100 font-semibold px-1.5 py-0.5 rounded leading-none')
                                                                                if det.get('correo'):
                                                                                    ui.label(f"✉️ {det['correo']}").classes('text-[9.5px] text-gray-600 leading-none truncate')
                                                                                if det.get('telefono') or det.get('celular'):
                                                                                    ui.label(f"📞 {det.get('celular') or det.get('telefono')}").classes('text-[9.5px] text-gray-600 font-mono leading-none')
                                                                else:
                                                                    with ui.row().classes('items-center gap-2 bg-gradient-to-r from-indigo-50/90 to-slate-50 border border-indigo-200 text-indigo-950 p-2 rounded-lg text-xs shadow-xs hover:shadow-sm hover:border-indigo-300 transition-all'):
                                                                        if det.get('fotos'):
                                                                            thumb_c = ui.image(det['fotos'][0]).classes('w-9 h-9 rounded-md object-cover border border-indigo-200 cursor-pointer shadow-2xs shrink-0')
                                                                            thumb_c.on('click', lambda _, lp=det.get('nombre', 'Equipo'), fl=det['fotos']: abrir_visor_lightbox(lp, fl))
                                                                        else:
                                                                            with ui.element('div').classes('w-9 h-9 rounded-md bg-indigo-100/80 flex items-center justify-center border border-indigo-200 shrink-0'):
                                                                                ui.icon('devices', size='xs').classes('text-indigo-600')
                                                                                
                                                                        with ui.column().classes('gap-0.5 overflow-hidden'):
                                                                            ui.label(det.get('nombre', '')).classes('text-xs font-bold text-gray-900 leading-tight truncate')
                                                                            with ui.row().classes('items-center gap-1.5'):
                                                                                if det.get('serial'):
                                                                                    ui.label(f"S/N: {det['serial']}").classes('text-[9.5px] text-gray-700 font-mono bg-white px-1.5 py-0.5 border border-indigo-200 rounded leading-none')
                                                                                if det.get('cantidad') is not None:
                                                                                    ui.label(f"Cant: {det['cantidad']}").classes('text-[9.5px] font-bold text-indigo-800 bg-indigo-200/80 px-1.5 py-0.5 rounded leading-none')
                                                                                if det.get('categoria'):
                                                                                    ui.label(f"[{det['categoria']}]").classes('text-[9.5px] text-indigo-600 font-medium leading-none')
                                                            else:
                                                                itm_txt = cache_opciones_modulos.get(target_mid, {}).get(itm_k, str(itm_k))
                                                                with ui.row().classes('items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-800 px-2 py-1 rounded-md text-xs shadow-none'):
                                                                    ui.icon('check_circle', size='xs').classes('text-indigo-500')
                                                                    ui.label(itm_txt).classes('text-xs font-medium')
                                                
                                            if accs_del_registro:
                                                with ui.expansion(f'Ramificación de Equipos ({len(accs_del_registro)} items)', icon='account_tree', value=False).classes('w-full text-xs font-bold text-indigo-900 bg-gray-50 rounded p-1 border border-gray-200 mt-1'):
                                                    with ui.column().classes('gap-1 p-2 w-full bg-white rounded'):
                                                        for idx_a, a in enumerate(accs_del_registro):
                                                            partes = []
                                                            if a.get('categoria'):
                                                                partes.append(f"[{a['categoria']}]")
                                                            if a.get('nombre'):
                                                                partes.append(a['nombre'])
                                                            line_acc = " ".join(partes)
                                                            if a.get('serial'):
                                                                line_acc += f" (S/N: {a['serial']})"
                                                            if a.get('cantidad'):
                                                                line_acc += f" • Cant: {a['cantidad']}"
                                                            if a.get('estado'):
                                                                line_acc += f" • {a['estado']}"
                                                            ui.label(f"• {line_acc}").classes('text-xs text-gray-600')
                                                            
                                        # Acciones CRUD individuales y Generar Acta
                                        with ui.row().classes('gap-1 self-start items-center'):
                                            ui.button(icon='description', on_click=lambda r=reg: ui.navigate.to(f'/reportes_inventario/{module_id}?record_id={r["id"]}', new_tab=True)).props('flat color=indigo round size=sm').tooltip('Generar Acta de este registro')
                                            ui.button(icon='edit', on_click=lambda r=reg: abrir_dialogo_edicion(r)).props('flat color=blue round size=sm').tooltip('Editar registro')
                                            
                                            def borrar_registro(rid=reg['id']):
                                                success, msg = delete_custom_record(rid)
                                                if success:
                                                    ui.notify(msg, type='positive')
                                                    refrescar_listado_registros()
                                                else:
                                                    ui.notify(msg, type='negative')
                                                    
                                            ui.button(icon='delete', on_click=borrar_registro).props('flat color=red round size=sm')
                                        
                refrescar_listado_registros()

    # Inicialización de la vista
    if show_list:
        refrescar_listado_modulos()
    dibujar_panel_derecho()
    
    return main_row
