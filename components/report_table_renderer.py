from nicegui import ui
import math

def estimar_altura_registro(registro, columnas, config_campos, estado_reporte=None, cache_detalles_modulos=None):
    """
    Estima con alta precisión la altura en píxeles de una fila de la tabla para optimizar 
    el aprovechamiento del papel físico sin desbordes ni saltos prematuros.
    """
    data = registro.get('data', {})
    if not columnas:
        return 45
        
    num_col = len(columnas)
    caracteres_por_linea = max(16, (700 // num_col) // 6)
    foto_size_pct = estado_reporte.get('foto_size_pct', 120) if estado_reporte else 120
    acomodacion = estado_reporte.get('acomodacion', 'auto') if estado_reporte else 'auto'
    foto_mult = 1.25 if acomodacion == 'comodo' else (0.95 if acomodacion == 'compacto' else 1.1)
    ancho_px = min(max(32, int(44 * (foto_size_pct / 100) * foto_mult)), 85)
    ancho_col = 700 // num_col
    
    max_altura_celda = 0
    for col_idx, col in enumerate(columnas):
        altura_celda = 0
        campos = col.get('campos', [])
        for campo_id in campos:
            tipo_campo = config_campos.get(campo_id, {}).get('type', 'text')
            val = data.get(campo_id)
            if not val:
                continue
                
            if tipo_campo == 'images':
                num_fotos = min(3, len(val)) if isinstance(val, list) else 1
                ancho_item = ancho_px + 6
                fotos_por_fila = max(1, ancho_col // ancho_item)
                filas_fotos = math.ceil(num_fotos / fotos_por_fila)
                altura_celda += 14 + (ancho_px * filas_fotos) + ((filas_fotos - 1) * 6)
            elif tipo_campo == 'accessories':
                num_items = len(val) if isinstance(val, list) else 1
                altura_celda += 12 + (num_items * 16)
            elif tipo_campo == 'linked_data':
                target_mid = config_campos.get(campo_id, {}).get('linked_module_id')
                detalles_dict = (cache_detalles_modulos or {}).get(target_mid, {})
                items_claves = val if isinstance(val, list) else [val]
                altura_items = 0
                for itm_k in items_claves:
                    if not itm_k:
                        continue
                    det = detalles_dict.get(itm_k)
                    if det:
                        if det.get('es_persona'):
                            altura_items += 40
                        elif det.get('fotos'):
                            altura_items += max(ancho_px + 6, 36)
                        else:
                            altura_items += 24
                    else:
                        altura_items += 22
                altura_celda += 12 + max(16, altura_items)
            else:
                texto = str(val)
                lineas = math.ceil(len(texto) / caracteres_por_linea) if len(texto) > 0 else 1
                altura_celda += 12 + (lineas * 13)
                
        if len(campos) > 1:
            altura_celda += (len(campos) - 1) * 3
            
        # El badge de kit solo se dibuja en la primera columna (ITEM)
        if col_idx == 0 and data.get('_kit_pertenece'):
            altura_celda += 20
            
        if altura_celda > max_altura_celda:
            max_altura_celda = altura_celda
            
    padding_fila = 22 if acomodacion == 'comodo' else (14 if acomodacion == 'compacto' else 18)
    return max(42, max_altura_celda + padding_fila)


def render_report_table(registros_pagina, estado_reporte, config_campos, opciones_campos, 
                        cache_detalles_modulos=None, cache_opciones_modulos=None, 
                        resolver_texto_fn=None, persona_fijada=None, user_info=None,
                        num_pag=0, pie_final_en_pagina=0, mostrar_firmas=False):
    """
    Renderiza la tabla de registros en CSS Grid con diseño blindado anti-desbordamiento,
    acomodación inteligente de celdas, fotos y metadatos de kits.
    """
    columnas = estado_reporte.get('columnas', [])
    if not columnas:
        if num_pag == 0:
            ui.label('No has configurado ninguna columna en el panel derecho.').classes('text-center w-full block text-red-400 font-bold mt-6')
        return

    if not registros_pagina:
        if num_pag == 0:
            ui.label('No hay registros guardados en esta gestión de inventario.').classes('text-center w-full block text-gray-400 italic mt-6')
        return

    num_col = len(columnas)
    num_items_pag = len(registros_pagina)
    acomodacion_modo = estado_reporte.get('acomodacion', 'auto')
    tiene_firmas_en_esta_pag = (num_pag == pie_final_en_pagina and mostrar_firmas)
    
    # Calibración de tipografías y espaciados según modo de acomodación
    if acomodacion_modo == 'compacto':
        py_celda = 'py-1.5'
        px_celda = 'px-2.5'
        gap_celda = 'gap-1'
        foto_mult = 0.95
        font_size_lbl = 'text-[9px]'
        font_size_val = 'text-[9.5px]'
    elif acomodacion_modo == 'comodo':
        py_celda = 'py-3'
        px_celda = 'px-3'
        gap_celda = 'gap-2'
        foto_mult = 1.25
        font_size_lbl = 'text-[10px]'
        font_size_val = 'text-[11px]'
    else:  # auto (inteligente)
        if num_items_pag <= 4 and not tiene_firmas_en_esta_pag:
            py_celda = 'py-3'
            px_celda = 'px-3'
            gap_celda = 'gap-2'
            foto_mult = 1.25
            font_size_lbl = 'text-[10px]'
            font_size_val = 'text-[11px]'
        elif num_items_pag <= 6:
            py_celda = 'py-2'
            px_celda = 'px-3'
            gap_celda = 'gap-1.5'
            foto_mult = 1.05
            font_size_lbl = 'text-[9.5px]'
            font_size_val = 'text-[10px]'
        else:
            py_celda = 'py-1.5'
            px_celda = 'px-2.5'
            gap_celda = 'gap-1'
            foto_mult = 0.95
            font_size_lbl = 'text-[9px]'
            font_size_val = 'text-[9.5px]'

    # Plantilla de grid fraccional inviolable
    grid_template = f"repeat({num_col}, minmax(0, 1fr))"

    with ui.element('div').classes('w-full min-w-full max-w-full border border-slate-300 rounded-md shrink-0 overflow-hidden bg-white shadow-xs box-border'):
        
        # 1. ENCABEZADO DE LA TABLA
        with ui.element('div').classes('w-full bg-slate-900 text-white box-border').style(f'display: grid; grid-template-columns: {grid_template}; width: 100%;'):
            for col in columnas:
                with ui.element('div').classes('py-2 px-2.5 overflow-hidden border-r border-slate-700 min-w-0 box-border'):
                    ui.label(col["titulo"].upper()).classes('text-[10px] font-bold text-left w-full overflow-hidden text-ellipsis whitespace-nowrap tracking-wider')
        
        # 2. FILAS DE DATOS
        for idx_r, reg in enumerate(registros_pagina):
            data = reg.get('data', {})
            kit_badge_rendered = False
            bg_fila = 'bg-slate-50/40' if idx_r % 2 == 1 else 'bg-white'
        
            with ui.element('div').classes(f'w-full border-t border-slate-200 {bg_fila} hover:bg-indigo-50/30 transition-colors box-border').style(f'display: grid; grid-template-columns: {grid_template}; width: 100%;'):
                for idx, col in enumerate(columnas):
                    borde_derecho = 'border-r border-dashed border-slate-200' if idx < num_col - 1 else ''
                
                    with ui.element('div').classes(f'{py_celda} {px_celda} flex flex-col {gap_celda} {borde_derecho} overflow-hidden min-w-0 box-border').style('overflow-wrap: anywhere; word-break: break-word; max-width: 100%;'):
                        hay_datos = False
                    
                        for campo_id in col.get('campos', []):
                            tipo_campo = config_campos.get(campo_id, {}).get('type', 'text')
                            val = data.get(campo_id)
                            if not val:
                                continue
                            
                            lbl = opciones_campos.get(campo_id, campo_id.upper())
                        
                            with ui.element('div').classes('flex flex-col gap-0 w-full min-w-0 overflow-hidden'):
                                ui.label(f"{lbl}:").classes(f'{font_size_lbl} font-bold text-slate-500 leading-tight')
                            
                                if tipo_campo == 'images':
                                    with ui.element('div').classes('flex flex-row w-full gap-1.5 mt-1 flex-wrap overflow-hidden'):
                                        foto_size_pct = estado_reporte.get('foto_size_pct', 120)
                                        ancho_px = min(max(32, int(44 * (foto_size_pct / 100) * foto_mult)), 85)
                                        alto_px = ancho_px
                                        for f in val[:3]:
                                            ui.image(f).style(f"width: {ancho_px}px; height: {alto_px}px; max-width: 100%; object-fit: cover;").classes('rounded border border-gray-200 shadow-sm')
                                elif tipo_campo == 'accessories':
                                    for a in val:
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
                                        ui.label(line_acc).classes('text-[10px] text-slate-800 leading-tight').style('overflow-wrap: anywhere;')
                                elif tipo_campo == 'linked_data':
                                    target_mid = config_campos.get(campo_id, {}).get('linked_module_id')
                                    detalles_dict = (cache_detalles_modulos or {}).get(target_mid, {})
                                    items_claves = val if isinstance(val, list) else [val]
                                    foto_size_pct = estado_reporte.get('foto_size_pct', 120)
                                    ancho_px = min(max(24, int(30 * (foto_size_pct / 100))), 50)
                                    alto_px = ancho_px
                                
                                    for itm_k in items_claves:
                                        if not itm_k:
                                            continue
                                        det = detalles_dict.get(itm_k)
                                        if det:
                                            es_persona = det.get('es_persona', False)
                                            if es_persona:
                                                with ui.element('div').classes('flex flex-row items-start gap-2 my-1 p-2 bg-blue-50/70 border border-blue-200 rounded w-full overflow-hidden').style('max-width: 100%;'):
                                                    with ui.element('div').style('width: 26px; height: 26px; min-width: 26px;').classes('rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-[10px] shadow-sm'):
                                                        nom_p = det.get('nombre', 'P').strip()
                                                        inits = "".join([part[0].upper() for part in nom_p.split()[:2]]) if nom_p else "U"
                                                        ui.label(inits).classes('leading-none')
                                                
                                                    with ui.element('div').classes('flex flex-col gap-0.5 flex-grow overflow-hidden min-w-0'):
                                                        with ui.element('div').classes('flex flex-row items-center gap-1.5 flex-wrap min-w-0 w-full'):
                                                            ui.label(det.get('nombre', 'Colaborador')).classes('text-[10px] font-bold text-slate-900 leading-tight').style('overflow-wrap: anywhere;')
                                                            if det.get('rol'):
                                                                ui.label(f"[{det['rol']}]").classes('text-[8.5px] font-semibold text-blue-700 bg-blue-100 px-1 rounded leading-none py-0.5 overflow-hidden text-ellipsis whitespace-nowrap').style('max-width: 100%;')
                                                    
                                                        if det.get('correo'):
                                                            with ui.element('div').classes('flex flex-row items-center gap-1 mt-0.5 min-w-0 w-full'):
                                                                ui.icon('email', size='xs').classes('text-slate-500 text-[10px]')
                                                                ui.label(det['correo']).classes('text-[8.5px] text-slate-700 leading-tight min-w-0').style('overflow-wrap: anywhere;')
                                                        
                                                        tel_p = det.get('celular') or det.get('telefono')
                                                        if tel_p:
                                                            with ui.element('div').classes('flex flex-row items-center gap-1 mt-0.5 min-w-0 w-full'):
                                                                ui.icon('phone', size='xs').classes('text-slate-500 text-[10px]')
                                                                ui.label(tel_p).classes('text-[8.5px] text-slate-700 leading-tight min-w-0').style('overflow-wrap: anywhere;')
                                                        
                                                        if det.get('cedula'):
                                                            ui.label(f"C.C. {det['cedula']}").classes('text-[8px] text-slate-500 font-mono leading-none mt-0.5').style('overflow-wrap: anywhere;')
                                            else:
                                                with ui.element('div').classes('flex flex-row items-center gap-2 my-1 p-1.5 bg-slate-50 border border-slate-200 rounded w-full overflow-hidden').style('max-width: 100%;'):
                                                    if det.get('fotos'):
                                                        ui.image(det['fotos'][0]).style(f"width: {ancho_px}px; height: {alto_px}px; min-width: {ancho_px}px; object-fit: cover;").classes('rounded border border-gray-200')
                                                    else:
                                                        with ui.element('div').style(f"width: {ancho_px}px; height: {alto_px}px; min-width: {ancho_px}px;").classes('rounded bg-indigo-50 flex items-center justify-center border border-indigo-100'):
                                                            ui.icon('devices', size='xs').classes('text-indigo-600')
                                                    
                                                    with ui.element('div').classes('flex flex-col gap-0.5 flex-grow overflow-hidden min-w-0'):
                                                        ui.label(det.get('nombre', 'Artículo')).classes('text-[10px] font-bold text-slate-900 leading-tight w-full').style('overflow-wrap: anywhere;')
                                                        with ui.element('div').classes('flex flex-row items-center gap-1 flex-wrap mt-0.5 min-w-0 w-full'):
                                                            if det.get('serial'):
                                                                ui.label(f"S/N: {det['serial']}").classes('text-[8.5px] font-mono text-slate-700 bg-white px-1 border border-slate-200 rounded leading-none py-0.5').style('overflow-wrap: anywhere; max-width: 100%;')
                                                            if det.get('cantidad') is not None:
                                                                ui.label(f"Cant: {det['cantidad']}").classes('text-[8.5px] font-bold text-indigo-800 bg-indigo-100 px-1 rounded leading-none py-0.5')
                                                            if det.get('categoria'):
                                                                ui.label(f"[{det['categoria']}]").classes('text-[8.5px] text-slate-500 leading-none overflow-hidden text-ellipsis whitespace-nowrap').style('max-width: 100%;')
                                        else:
                                            itm_txt = (cache_opciones_modulos or {}).get(target_mid, {}).get(itm_k, str(itm_k))
                                            with ui.element('div').classes('flex flex-row items-center gap-1 my-0.5 min-w-0 w-full'):
                                                ui.icon('link', size='xs').classes('text-indigo-600')
                                                ui.label(itm_txt).classes('text-[10px] text-slate-800 leading-tight font-medium min-w-0').style('overflow-wrap: anywhere;')
                                else:
                                    raw_val = str(val)
                                    val_res = resolver_texto_fn(raw_val, [reg], config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info) if resolver_texto_fn else raw_val
                                    ui.label(val_res).classes(f'{font_size_val} text-slate-800 leading-tight w-full overflow-hidden').style('overflow-wrap: anywhere;')
                                    
                                    if data.get('_kit_pertenece') and idx == 0 and not kit_badge_rendered:
                                        kit_badge_rendered = True
                                        with ui.element('div').classes('flex flex-row items-center gap-1 mt-1 px-1.5 py-0.5 rounded bg-indigo-50 border border-indigo-200 w-full min-w-0 flex-wrap'):
                                            ui.icon('extension', size='xs').classes('text-indigo-600')
                                            ui.label(f"Kit: {data['_kit_pertenece']}").classes('text-[9px] font-bold text-indigo-800 leading-none min-w-0').style('overflow-wrap: anywhere;')
                                hay_datos = True
                    
                        if not hay_datos:
                            ui.label('-').classes('text-slate-400 italic text-[11px]')
