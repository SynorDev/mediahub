from nicegui import ui
import re
from datetime import datetime
from database import (
    create_event, update_event, delete_event, get_all_staff, get_all_inventory, 
    get_all_locations, get_template_config, get_template_by_area,
    detect_personnel_transition_conflicts, get_transition_rules_config
)

# =====================================================================
# MOTOR DE RENDERIZADO DINÁMICO (V4)
# =====================================================================

# 1. EL DICCIONARIO UNIVERSAL (AHORA SOPORTA MÚLTIPLE SELECCIÓN Y VACIADO RÁPIDO)
COMPONENTES_UI = {
    # Agregamos 'clearable' a las propiedades del input de texto
    "text_input": lambda c, fd: ui.input(label=c['label']).bind_value(fd, c['name_id']).props('outlined clearable w-full'),
    
    # Agregamos 'clearable' y 'new-value-mode="add-unique"' a las listas simples
    "select": lambda c, ops, fd: ui.select(options=ops, label=c['label'], multiple=c.get('multiple', False))
                                 .bind_value(fd, c['name_id'])
                                 .props('outlined clearable w-full new-value-mode="add-unique" ' + ('use-chips' if c.get('multiple') else '')),
                                 
    # Agregamos 'clearable' y 'new-value-mode="add-unique"' a las listas con buscador
    "searchable_select": lambda c, ops, fd: ui.select(options=ops, label=c['label'], with_input=True, multiple=c.get('multiple', False))
                                            .bind_value(fd, c['name_id'])
                                            .props('outlined clearable w-full new-value-mode="add-unique" ' + ('use-chips' if c.get('multiple') else '')),
                                            
    "time_range": lambda c, fd: ui.row().classes('w-full gap-2 text-gray-700'),
    "switch": lambda c, fd: ui.switch(text=c['label']).bind_value(fd, c['name_id']).classes('font-bold text-red-600 mb-4 mt-2')
}

# 2. EL RESOLUTOR DE DATOS
def obtener_opciones_para_campo(data_source):
    if not data_source: return []
    if data_source.get('tipo') == 'estatico':
        return data_source.get('opciones', [])
    elif data_source.get('tipo') == 'dinamico':
        entidad = data_source.get('entidad')
        filtros = data_source.get('filtros', {})
        
        if entidad == 'staff':
            todo_el_staff = get_all_staff()
            opciones_filtradas = []
            roles_permitidos = [rol.lower() for rol in filtros.get('rol_tags', [])]
            for persona in todo_el_staff:
                roles_persona = [r.strip().lower() for r in persona['rol'].split(',')]
                if any(rol in roles_persona for rol in roles_permitidos) or not roles_permitidos:
                    opciones_filtradas.append(persona['nombre'])
            return opciones_filtradas
            
        elif entidad == 'inventory':
            todo_el_inventario = get_all_inventory()
            categorias_permitidas = filtros.get('categoria', [])
            return [item['nombre'] for item in todo_el_inventario if item['categoria'] in categorias_permitidas or not categorias_permitidas]
            
        elif entidad == 'locations': # NUEVA ENTIDAD
            todas_locaciones = get_all_locations()
            return [loc['nombre'] for loc in todas_locaciones]
            
    return []

# 3. LA FUNCIÓN DE MAPEADO (AHORA CON BLOQUEO PARCIAL E INTELIGENTE)
def renderizar_campo(campo_json, form_data, es_creador):
    tipo_ui = campo_json.get('ui_component')
    name_id = campo_json.get('name_id')
    
    if tipo_ui not in COMPONENTES_UI: return None
        
    if tipo_ui in ['select', 'searchable_select']:
        opciones = list(obtener_opciones_para_campo(campo_json.get('data_source')))
        is_multiple = campo_json.get('multiple', False)
        val_actual = form_data.get(name_id)
        
        if is_multiple:
            if isinstance(val_actual, str):
                if val_actual:
                    val_lista = [x.strip() for x in re.split(r'[,;\n]+', val_actual) if x.strip()]
                    form_data[name_id] = val_lista
                else:
                    form_data[name_id] = []
            elif not isinstance(val_actual, list):
                form_data[name_id] = [val_actual] if val_actual else []
                
            for v in form_data.get(name_id, []):
                if v and v not in opciones:
                    opciones.append(v)
        else:
            if isinstance(val_actual, list):
                form_data[name_id] = val_actual[0] if val_actual else ''
                val_actual = form_data[name_id]
            if val_actual and val_actual not in opciones:
                opciones.insert(0, val_actual)

        elemento = COMPONENTES_UI[tipo_ui](campo_json, opciones, form_data)
        
    elif tipo_ui == 'time_range':
        elemento = COMPONENTES_UI[tipo_ui](campo_json, form_data)
        with elemento:
            input_ini = ui.input('Hora Inicio').props('type="time" outlined').bind_value(form_data, 'hora_inicio').classes('w-1/2')
            input_fin = ui.input('Hora Fin').props('type="time" outlined').bind_value(form_data, 'hora_fin').classes('w-1/2')
            
            # Bloqueo individual para el rango de tiempo si es invitado
            if not es_creador:
                input_ini.disable()
                input_fin.disable()
    else:
        elemento = COMPONENTES_UI[tipo_ui](campo_json, form_data)
        
    # BLOQUEO INTELIGENTE DE DATOS COMPARTIDOS (DUEÑO VS INVITADO):
    # Si NO eres el dueño, NO puedes modificar el Título Principal.
    # Todos tus demás campos (selectores de inventario, personal, notas) quedarán libres.
    if not es_creador:
        if name_id == 'nombre_programa':
            elemento.disable()
        
    return elemento

def construir_formulario_dinamico(template_json, form_data, es_creador):
    ui.label(template_json['template_meta']['nombre']).classes('text-2xl font-bold text-gray-800 mb-4')
    for seccion in template_json.get('layout', []):
        ui.label(seccion['titulo']).classes('text-lg font-bold text-blue-600 mt-4 mb-2 border-b pb-1')
        columnas = seccion.get('columnas', 1)
        clase_contenedor = 'w-full gap-4' if columnas == 1 else f'w-full grid grid-cols-{columnas} gap-4'
        with ui.element('div').classes(clase_contenedor):
            for campo in seccion.get('campos', []):
                # Pasamos el permiso a cada campo que se dibuja
                renderizar_campo(campo, form_data, es_creador)

# =====================================================================
# VENTANA MODAL UNIVERSAL
# =====================================================================

def open_event_modal(user_info, selected_day, month, year, on_save_callback, evento_existente=None):
    area_usuario = user_info.get('area', '').lower()
    fecha_str = f"{year}-{month:02d}-{selected_day:02d}"
    is_editing = evento_existente is not None
    
    if is_editing:
        form_data = evento_existente.get('detalles', {}).copy()
        # Aseguramos que los campos universales del evento se sincronicen en form_data:
        if not form_data.get('hora_inicio'):
            form_data['hora_inicio'] = evento_existente.get('hora_inicio', '')
        if not form_data.get('hora_fin'):
            form_data['hora_fin'] = evento_existente.get('hora_fin', '')
        if not form_data.get('nombre_programa'):
            form_data['nombre_programa'] = evento_existente.get('nombre_programa', '')
        if not form_data.get('observaciones') and form_data.get('pautas_cortes'):
            form_data['observaciones'] = form_data.get('pautas_cortes', '')
    else:
        form_data = {'estado_tecnica': 'pendiente', 'hora_inicio': '08:00', 'hora_fin': '08:30'}
        
    template_config = get_template_by_area(area_usuario)

    # =========================================================
    # PARCHE AUTO-MIGRACIÓN: ESTANDARIZACIÓN DE DATOS COMPARTIDOS
    # =========================================================
    if template_config:
        titulo_asignado = False
        for seccion in template_config.get('layout', []):
            for campo in seccion.get('campos', []):
                # Encontramos el primer campo de texto
                if campo.get('ui_component') == 'text_input' and not titulo_asignado:
                    old_id = campo.get('name_id')
                    # Lo forzamos a ser el identificador universal compartido
                    campo['name_id'] = 'nombre_programa'
                    titulo_asignado = True
                    
                    # Si el evento ya tenía datos guardados bajo el ID viejo, los mudamos al nuevo ID
                    if old_id and old_id != 'nombre_programa' and old_id in form_data:
                        form_data['nombre_programa'] = form_data.pop(old_id)
                        
        # Limpiamos fantasmas antiguos de Producción ("campo_texto_0") en los datos
        if 'campo_texto_0' in form_data and 'nombre_programa' not in form_data:
            form_data['nombre_programa'] = form_data.pop('campo_texto_0')
    # =========================================================

    # 1. PERMISOS ANTES DE RENDERIZAR
    if is_editing:
        tipo_evento = evento_existente.get('tipo', '').lower()
        es_creador = (tipo_evento == area_usuario)
        
        es_invitado = False
        if not es_creador:
            # V4 Pura: Solo validamos por el switch dinámico
            if form_data.get(f'compartir_{area_usuario}', False):
                es_invitado = True
    else:
        es_creador = True
        es_invitado = False

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-6 h-[80vh] overflow-y-auto bg-gray-50'):
        with ui.row().classes('w-full justify-between items-center mb-6 border-b pb-2'):
            titulo = 'Editar Evento' if is_editing else f'Programar para el {selected_day}'
            ui.label(titulo).classes('text-2xl font-bold text-gray-800')
            ui.button(icon='close', on_click=dialog.close).props('flat round text-color=gray')

        def handle_save(notify_msg=None, notify_type='positive'):
            if not form_data.get('hora_inicio'):
                ui.notify('La Hora de Inicio es obligatoria', type='warning')
                return
            
            # Como el parche estandarizó los datos, podemos llamar el título directamente
            nombre_prog = form_data.get('nombre_programa')
            if not nombre_prog:
                nombre_prog = f'Evento de {area_usuario.capitalize()}'

            # Validar reglas de traslado de personal técnico (Camarógrafos, Sonidistas, etc.)
            rules_cfg = get_transition_rules_config()
            candidate = dict(form_data)
            candidate['id'] = evento_existente['id'] if is_editing else None
            candidate['fecha'] = fecha_str
            candidate['hora_inicio'] = form_data.get('hora_inicio')
            candidate['hora_fin'] = form_data.get('hora_fin')
            candidate['nombre_programa'] = nombre_prog
            candidate['tipo'] = area_usuario
            candidate['detalles'] = form_data

            conflictos_traslado = detect_personnel_transition_conflicts(fecha_str, candidate_event=candidate)

            if conflictos_traslado:
                primer_conflicto = conflictos_traslado[0]
                if rules_cfg.get('modo_bloqueo', False):
                    ui.notify(f"⛔ Bloqueo de Traslado: {primer_conflicto['mensaje']}", type='negative', duration=9000)
                    return
                else:
                    ui.notify(f"⚠️ Alerta de Traslado: {primer_conflicto['persona']} ({primer_conflicto['rol_a']}) tiene margen de {primer_conflicto['margen']} min. Notificado a Programación y Emisión para ajuste de hasta {rules_cfg.get('tiempo_ajuste_parrilla_sugerido', 3)} min.", type='warning', duration=9000)
                
            if is_editing:
                update_event(
                    evento_existente['id'], 
                    form_data.get('hora_inicio'), 
                    form_data.get('hora_fin', ''), 
                    nombre_prog, 
                    form_data
                )
                if notify_msg:
                    ui.notify(notify_msg, type=notify_type)
                else:
                    ui.notify('Evento actualizado', type='info')
            else:
                create_event(
                    fecha=fecha_str, hora_inicio=form_data.get('hora_inicio'),
                    hora_fin=form_data.get('hora_fin', ''), tipo=area_usuario,
                    nombre_programa=nombre_prog, detalles_dict=form_data
                )
                if notify_msg:
                    ui.notify(notify_msg, type=notify_type)
                else:
                    ui.notify('Evento guardado exitosamente!', type='positive')
                
            dialog.close()
            on_save_callback()

        def handle_delete():
            delete_event(evento_existente['id'])
            ui.notify('Evento eliminado', type='negative')
            dialog.close()
            on_save_callback()

        # ==========================================
        # EL ENRUTADOR DE FORMULARIOS V4
        # ==========================================
        if template_config:
            with ui.card().classes('w-full p-6 shadow-sm border border-gray-200 bg-white'):
                if not es_creador:
                    ui.label('EVENTO COMPARTIDO: Los datos principales (Nombre y Horario) son del creador y están bloqueados. Completa tus asignaciones técnicas y confirma.').classes('text-xs text-indigo-800 font-bold bg-indigo-100 p-3 rounded-lg w-full mb-4 text-center')
                
                construir_formulario_dinamico(template_config, form_data, es_creador)
                
            # =======================================================
            # LA NUEVA MAGIA: LECTOR CRUZADO DE DATOS (OTRAS ÁREAS)
            # =======================================================
            if is_editing:
                # 1. Calculamos quiénes están involucrados en este evento
                areas_involucradas = [evento_existente['tipo'].lower()]
                for key, val in form_data.items():
                    if key.startswith('compartir_') and val == True:
                        invitado = key.replace('compartir_', '').lower()
                        if invitado not in areas_involucradas:
                            areas_involucradas.append(invitado)
                            
                # 2. Excluimos nuestra propia área para ver solo la información de los demás
                otras_areas = [a for a in areas_involucradas if a != area_usuario]
                
                if otras_areas:
                    # EL NUEVO ACORDEÓN DESPLEGABLE (Reemplaza al texto fijo)
                    with ui.expansion('Mostrar información de otras áreas', icon='visibility').classes('w-full bg-blue-50/50 border border-blue-100 rounded-lg mt-6 text-blue-800 font-bold shadow-sm'):
                        
                        # 3. Dibujamos un bloque de lectura por cada área adicional invitada
                        for otra_area in otras_areas:
                            template_otra_area = get_template_by_area(otra_area)
                            
                            if template_otra_area:
                                with ui.card().classes('w-full p-4 shadow-none border-b border-blue-100 bg-transparent mb-0'):
                                    ui.label(f'Datos configurados por: {otra_area.upper()}').classes('text-xs font-bold text-blue-800 mb-2')
                                    
                                    hay_datos = False
                                    for seccion in template_otra_area.get('layout', []):
                                        for campo in seccion.get('campos', []):
                                            key = campo['name_id']
                                            
                                            # Ignoramos datos universales (Nombre, hora, switches de compartir)
                                            if key in ['nombre_programa', 'hora_inicio', 'hora_fin'] or key.startswith('compartir_'):
                                                continue
                                                
                                            val = form_data.get(key)
                                            if val: # Si la otra área llenó este dato, lo mostramos
                                                hay_datos = True
                                                val_str = ", ".join(val) if isinstance(val, list) else str(val)
                                                ui.label(f"• {campo['label']}: {val_str}").classes('text-sm text-gray-700 font-normal')
                                    
                                    if not hay_datos:
                                        ui.label('Esta área aún no ha registrado detalles técnicos/notas.').classes('text-xs text-gray-400 italic font-normal')
        else:
            with ui.column().classes('w-full items-center justify-center py-12 text-center'):
                ui.icon('build_circle', size='lg').classes('text-blue-500 mb-4')
                ui.label('Falta Configuración').classes('text-xl font-bold text-gray-700 mb-2')
            return

        # ==========================================
        # BOTONERA DINÁMICA V4
        # ==========================================
        with ui.row().classes('w-full justify-between mt-8'):
            # LADO IZQUIERDO: ELIMINAR O RECHAZAR
            if is_editing:
                if es_creador:
                    ui.button('Eliminar Evento', icon='delete', color='red', on_click=handle_delete).classes('px-4 py-2 rounded-lg shadow-md')
                elif es_invitado:
                    def rechazar_participacion():
                        if f'compartir_{area_usuario}' in form_data:
                            form_data[f'compartir_{area_usuario}'] = False
                        if 'requiere_tecnica' in form_data and area_usuario == 'produccion':
                            form_data['requiere_tecnica'] = False
                            
                        form_data['estado_compartido'] = 'rechazado'
                        handle_save(notify_msg='Has rechazado este evento.', notify_type='warning')
                        
                    ui.button('Rechazar / Quitar', icon='event_busy', color='orange', on_click=rechazar_participacion).classes('px-4 py-2 rounded-lg shadow-md hover:bg-orange-600')
            else:
                ui.label() # Espaciador
                
            # LADO DERECHO: GUARDAR Y CONFIRMAR
            with ui.row().classes('gap-2'):
                if es_invitado:
                    if form_data.get('estado_compartido', 'pendiente') != 'confirmado':
                        def confirmar_evento():
                            form_data['estado_compartido'] = 'confirmado'
                            form_data['hora_confirmacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            handle_save(notify_msg='¡Evento confirmado exitosamente!', notify_type='positive')
                            
                        ui.button('Confirmar Participación', icon='check_circle', on_click=confirmar_evento).classes('bg-blue-600 text-white px-6 py-2 rounded-lg shadow-md hover:bg-blue-700')
                    
                    # AHORA SÍ: El invitado puede guardar sus asignaciones técnicas sin confirmar aún
                    ui.button('Guardar Asignaciones', icon='save', on_click=handle_save).classes('bg-green-600 text-white px-6 py-2 rounded-lg shadow-md hover:bg-green-700')
                
                elif es_creador:
                    ui.button('Guardar Cambios', icon='save', on_click=handle_save).classes('bg-green-600 text-white px-6 py-2 rounded-lg shadow-md hover:bg-green-700')
    
    dialog.open()

def render_form_parrilla(form_data):
    """Ficha de programación para el Caso A con Switch de En Vivo"""
    with ui.row().classes('w-full items-center justify-between mb-4'):
        with ui.row().classes('items-center gap-2'):
            ui.icon('tv', size='md').classes('text-blue-600')
            ui.label('Programación').classes('text-xl font-bold text-gray-800')
            
        ui.switch('EN VIVO (Solicitar Técnica)').bind_value(form_data, 'requiere_tecnica').props('color=red').classes('font-bold text-red-600')

    with ui.card().classes('w-full p-6 shadow-sm border border-gray-200 bg-white'):
        with ui.row().classes('w-full gap-4 mb-2 flex-nowrap'):
            ui.input('Nombre del programa').bind_value(form_data, 'nombre_programa').classes('w-1/2')
            ui.input('Entidad').bind_value(form_data, 'entidad').classes('w-1/2')
        
        with ui.row().classes('w-full gap-4 mb-2 flex-nowrap'):
            ui.input('Hora inicio').props('type=time').bind_value(form_data, 'hora_inicio').classes('w-1/2')
            ui.input('Hora fin').props('type=time').bind_value(form_data, 'hora_fin').classes('w-1/2')
            
        with ui.row().classes('w-full items-center gap-4 mb-4 flex-nowrap'):
            ui.select(['Pauta comercial', 'Interna', 'Exterior', 'Institucional'], label='Estado del programa').bind_value(form_data, 'estado').classes('w-1/2')
            with ui.column().classes('w-1/2 justify-center pl-2 pt-2'):
                ui.switch('¿Entidad aliada del canal?').bind_value(form_data, 'aliada').classes('font-semibold text-gray-700')
        
        ui.textarea('Notas / Requerimientos').bind_value(form_data, 'notas').classes('w-full')

def render_form_produccion(form_data, bloquear_cabecera=False):
    """Ficha técnica para el Caso B con Validación de No Duplicación del Crew"""
    with ui.row().classes('items-center gap-2 mb-4'):
        ui.icon('videocam', size='md').classes('text-blue-600')
        ui.label('Ficha Técnica de Producción').classes('text-xl font-bold text-gray-800')
    
    staff_data = get_all_staff()
    inventory_data = get_all_inventory()
    
    def filter_staff(keywords):
        opciones = {}
        for p in staff_data:
            rol_norm = p['rol'].lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            if any(kw in rol_norm for kw in keywords):
                opciones[p['nombre']] = f"{p['nombre']} ({p['rol']})"
        return opciones

    # Listas bases para la validación relacional
    opciones_productores = filter_staff(['productor', 'produccion', 'coordinador'])
    opciones_camaras = filter_staff(['camara', 'camarografo', 'operador', 'fotografia'])
    opciones_switcher = filter_staff(['switcher', 'director', 'realizador'])
    opciones_sonido = filter_staff(['sonido', 'sonidista', 'audio', 'microfonista'])
    opciones_gaffer = filter_staff(['gaffer', 'iluminacion', 'luces', 'electrico'])
    opciones_vestuario = filter_staff(['vestuario', 'arte', 'utileria'])
    opciones_maquillaje = filter_staff(['maquillaje', 'makeup', 'estilista'])
    
    opciones_locacion = [i['nombre'] for i in inventory_data if i['categoria'] == 'Estudio/Locación']
    opciones_transporte = [i['nombre'] for i in inventory_data if i['categoria'] == 'Transporte']
    opciones_equipos = {i['nombre']: f"{i['nombre']} ({i['categoria']})" for i in inventory_data if i['categoria'] not in ['Estudio/Locación', 'Transporte']}
    
    with ui.card().classes('w-full p-6 shadow-sm border border-gray-200 bg-white'):
        with ui.grid(columns=2).classes('w-full gap-x-4 gap-y-2'):
            
            input_nombre = ui.input('Nombre del programa').bind_value(form_data, 'nombre_programa').classes('col-span-2')
            
            # 1. PREPARAMOS EL DICCIONARIO VACÍO PRIMERO
            selectores_crew = {}
            
            # 2. 🛠️ ALGORITMO REACTIVO (Recibe 'e' para capturar el evento de NiceGUI)
            def enforce_unique_crew(e=None):
                nombres_ocupados = {sel.value for sel, _ in selectores_crew.values() if sel.value}
                
                for key, (selector, opciones_base) in selectores_crew.items():
                    opciones_filtradas = {
                        nombre: etiqueta for nombre, etiqueta in opciones_base.items()
                        if nombre not in nombres_ocupados or nombre == selector.value
                    }
                    selector.options = opciones_filtradas
                    selector.update()

            # 3. ASIGNAMOS EL 'on_change' DIRECTAMENTE EN LA CREACIÓN DEL ui.select
            sel_prod = ui.select(opciones_productores, label='Productor encargado', on_change=enforce_unique_crew).bind_value(form_data, 'productor').classes('col-span-2 mb-4')
            
            input_inicio = ui.input('Hora inicio').props('type=time').bind_value(form_data, 'hora_inicio')
            input_fin = ui.input('Hora fin').props('type=time').bind_value(form_data, 'hora_fin')
            
            if bloquear_cabecera:
                input_nombre.disable()
                input_inicio.disable()
                input_fin.disable()
                input_nombre.tooltip('El nombre y horario son administrados por Parrilla')
            
            ui.select(opciones_locacion, label='Locación').bind_value(form_data, 'locacion').classes('mt-4')
            ui.select(opciones_transporte, label='Transporte').bind_value(form_data, 'transporte').classes('mt-4')
            ui.select(opciones_equipos, label='Equipos (Cámaras, luces, etc.)', multiple=True).bind_value(form_data, 'equipos').classes('col-span-2 mb-4')
            
            ui.label('Asignación de Crew').classes('col-span-2 text-xs text-gray-400 font-bold mt-2 border-b pb-1')
            
            # Asignamos el on_change en el resto del crew
            sel_cam1 = ui.select(opciones_camaras, label='Cámara 1', on_change=enforce_unique_crew).bind_value(form_data, 'cam1')
            sel_cam2 = ui.select(opciones_camaras, label='Cámara 2', on_change=enforce_unique_crew).bind_value(form_data, 'cam2')
            sel_cam3 = ui.select(opciones_camaras, label='Cámara 3', on_change=enforce_unique_crew).bind_value(form_data, 'cam3')
            sel_sw = ui.select(opciones_switcher, label='Switcher / Dir. Cámara', on_change=enforce_unique_crew).bind_value(form_data, 'switcher')
            sel_son = ui.select(opciones_sonido, label='Sonido', on_change=enforce_unique_crew).bind_value(form_data, 'sonido')
            sel_gaf = ui.select(opciones_gaffer, label='Gaffer', on_change=enforce_unique_crew).bind_value(form_data, 'gaffer')
            sel_ves = ui.select(opciones_vestuario, label='Vestuario', on_change=enforce_unique_crew).bind_value(form_data, 'vestuario')
            sel_maq = ui.select(opciones_maquillaje, label='Maquillaje', on_change=enforce_unique_crew).bind_value(form_data, 'maquillaje')

            # 4. AHORA SÍ, LLENAMOS EL DICCIONARIO
            selectores_crew.update({
                'productor': (sel_prod, opciones_productores),
                'cam1': (sel_cam1, opciones_camaras),
                'cam2': (sel_cam2, opciones_camaras),
                'cam3': (sel_cam3, opciones_camaras),
                'switcher': (sel_sw, opciones_switcher),
                'sonido': (sel_son, opciones_sonido),
                'gaffer': (sel_gaf, opciones_gaffer),
                'vestuario': (sel_ves, opciones_vestuario),
                'maquillaje': (sel_maq, opciones_maquillaje)
            })

            # Ejecutamos la función manualmente una vez para limpiar si estamos editando un evento
            enforce_unique_crew()
