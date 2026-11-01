from nicegui import ui
import re
import math

def resolver_texto_con_variables(texto, registros, config_campos, cache_det=None, cache_opt=None, persona_fijada=None, user_info=None):
    """
    Sustituye variables dinámicas [RESPONSABLE], [CORREO], [FECHA], [ITEM], etc.,
    en las cláusulas de apertura, cierre y textos del reporte.
    """
    if not texto:
        return ""
        
    cache_det = cache_det or {}
    cache_opt = cache_opt or {}
    
    # 1. Variables globales del sistema y usuario emisor
    reemplazos = {
        'sistema': 'MediaHub V4',
        'software': 'MediaHub',
        'usuario_emisor': (user_info.get('nombres') or user_info.get('usuario') or 'Jose') if user_info else 'Jose',
        'area_emisora': (user_info.get('area') if user_info else '') or 'Ingeniería'
    }
    
    # 2. Si hay un colaborador fijado explícitamente en el acta
    if persona_fijada:
        reemplazos.update({
            'responsable': persona_fijada.get('nombre', ''),
            'colaborador': persona_fijada.get('nombre', ''),
            'nombre': persona_fijada.get('nombre', ''),
            'correo': persona_fijada.get('correo', ''),
            'email': persona_fijada.get('correo', ''),
            'cedula': persona_fijada.get('cedula', ''),
            'documento': persona_fijada.get('cedula', ''),
            'telefono': persona_fijada.get('celular') or persona_fijada.get('telefono', ''),
            'celular': persona_fijada.get('celular') or persona_fijada.get('telefono', ''),
            'cargo': persona_fijada.get('rol', ''),
            'rol': persona_fijada.get('rol', '')
        })
    else:
        # Búsqueda automática en los registros
        encontrado = False
        for reg in (registros or []):
            d = reg.get('data', {})
            for f_id, val in d.items():
                f_cfg = config_campos.get(f_id, {})
                if f_cfg.get('type') == 'linked_data':
                    mid = f_cfg.get('linked_module_id')
                    detalles_dict = cache_det.get(mid, {})
                    items_k = val if isinstance(val, list) else [val]
                    for k in items_k:
                        det = detalles_dict.get(k)
                        if det and det.get('es_persona'):
                            reemplazos.update({
                                'responsable': det.get('nombre', ''),
                                'colaborador': det.get('nombre', ''),
                                'nombre': det.get('nombre', ''),
                                'correo': det.get('correo', ''),
                                'email': det.get('correo', ''),
                                'cedula': det.get('cedula', ''),
                                'documento': det.get('cedula', ''),
                                'telefono': det.get('celular') or det.get('telefono', ''),
                                'celular': det.get('celular') or det.get('telefono', ''),
                                'cargo': det.get('rol', ''),
                                'rol': det.get('rol', '')
                            })
                            encontrado = True
                            break
                if encontrado: break
            if encontrado: break
            
    # 3. Mapear también los nombres exactos de los campos del formulario
    for f_id, f_cfg in config_campos.items():
        lbl = f_cfg.get('label', '').strip()
        if not lbl:
            continue
        vals_campo = []
        for reg in (registros or []):
            d = reg.get('data', {})
            val = d.get(f_id)
            if val is not None:
                f_type = f_cfg.get('type')
                if f_type == 'linked_data':
                    mid = f_cfg.get('linked_module_id')
                    opts = cache_opt.get(mid, {})
                    if isinstance(val, list):
                        vals_campo.extend([opts.get(k, str(k)) for k in val if k])
                    else:
                        vals_campo.append(opts.get(val, str(val)))
                elif f_type == 'accessories' and isinstance(val, list):
                    for a in val:
                        if isinstance(a, dict) and a.get('nombre'):
                            vals_campo.append(a['nombre'])
                elif f_type != 'images':
                    vals_campo.append(str(val).strip())
                    
        val_txt = ", ".join(dict.fromkeys(vals_campo)) if vals_campo else ""
        if val_txt:
            reemplazos[lbl.lower()] = val_txt
            reemplazos[f_id.lower()] = val_txt

    # 4. Realizar reemplazos insensibles a mayúsculas/minúsculas
    res = texto
    for var_name, var_val in reemplazos.items():
        res = re.sub(rf'\[{re.escape(var_name)}\]', var_val, res, flags=re.IGNORECASE)
        
    return res


def estimar_altura_texto(texto, caracteres_por_linea=85, altura_linea=18):
    """Estima la altura en píxeles de un bloque de texto multilínea para el paginador A4."""
    if not texto or not texto.strip():
        return 0
    parrafos = texto.strip().split('\n')
    total_lineas = 0
    for p in parrafos:
        p_strip = p.strip()
        if not p_strip:
            total_lineas += 1
        else:
            total_lineas += max(1, math.ceil(len(p_strip) / caracteres_por_linea))
    return (total_lineas * altura_linea) + 20


def render_report_header(estado_reporte, modulo_nombre, fecha_legible, now, logo_actual=None):
    """Renderiza el encabezado institucional con logo, metadatos oficiales y título del reporte."""
    doc_id = estado_reporte.get('doc_id') or f"ACT-{now.strftime('%Y%m%d')}"
    
    with ui.row().classes('w-full justify-between items-start border-b-2 border-gray-800 pb-5 mb-3 flex-nowrap shrink-0'):
        if logo_actual:
            ui.image(logo_actual).props('fit=contain').classes('w-52 h-16 object-contain shrink-0 p-1')
        else:
            with ui.row().classes('w-40 h-14 items-center justify-center bg-gradient-to-r from-slate-900 to-indigo-950 rounded-lg shadow-sm border border-slate-700 shrink-0 px-3'):
                ui.icon('live_tv', size='md').classes('text-indigo-400 mr-2')
                ui.label('MEDIAHUB').classes('text-lg font-black text-white tracking-widest')

        with ui.column().classes('items-end gap-0 shrink-0 max-w-[50%]'):
            ui.label(estado_reporte.get('header_title', 'MEDIAHUB V4')).classes('text-2xl font-black text-gray-800 tracking-tighter truncate w-full text-right')
            ui.label(estado_reporte.get('header_subtitle', 'Documento Operativo Oficial')).classes('text-xs text-gray-500 font-bold uppercase tracking-widest truncate w-full text-right')
            ui.label(f"Área / Gestión: {modulo_nombre.upper()}").classes('text-xs text-gray-400 mt-1 font-semibold truncate w-full text-right')
            ui.label(f"Fecha: {fecha_legible} • Código: {doc_id}").classes('text-xs text-gray-400 truncate w-full text-right')

    ui.label(estado_reporte.get('titulo', '')).classes('text-xl font-bold text-gray-800 mb-3 w-full block text-center uppercase tracking-widest shrink-0')


def render_report_apertura(texto_apertura, estado_reporte):
    """Renderiza la cláusula legal de apertura al inicio de la primera hoja."""
    if texto_apertura and estado_reporte.get('mostrar_clausula_apertura', True):
        with ui.column().classes('w-full mb-3 px-1 shrink-0'):
            ui.label(texto_apertura).classes('text-[11px] text-slate-800 leading-relaxed whitespace-normal break-words text-justify')


def render_report_cierre(texto_cierre, estado_reporte):
    """Renderiza la cláusula de aceptación y cierre en la página final."""
    if texto_cierre and estado_reporte.get('mostrar_clausula_cierre', True):
        with ui.column().classes('w-full mt-3 px-1 shrink-0'):
            ui.label(texto_cierre).classes('text-[10px] text-slate-700 leading-relaxed whitespace-normal break-words text-justify')


def render_report_firmas(estado_reporte, texto_f1_tit=None, texto_f1_sub=None, texto_f2_tit=None, texto_f2_sub=None,
                        firma_1_img_b64=None, firma_1_fecha=None, firma_2_img_b64=None, firma_2_fecha=None):
    """Renderiza el bloque simétrico de firmas institucionales con soporte para firmas virtuales estampadas."""
    if not estado_reporte.get('mostrar_firmas', False):
        return

    tiene_f2 = estado_reporte.get('mostrar_firma_2', False)
    justify_firmas = 'justify-around' if tiene_f2 else 'justify-center'

    f1_tit = texto_f1_tit if texto_f1_tit is not None else estado_reporte.get('firma_1_titulo', 'Firma de Recibido')
    f1_sub = texto_f1_sub if texto_f1_sub is not None else estado_reporte.get('firma_1_subtitulo')
    f2_tit = texto_f2_tit if texto_f2_tit is not None else estado_reporte.get('firma_2_titulo', 'Entregado Por')
    f2_sub = texto_f2_sub if texto_f2_sub is not None else estado_reporte.get('firma_2_subtitulo')

    # Si no se pasan explícitos, intentar leer de estado_reporte
    f1_img = firma_1_img_b64 or estado_reporte.get('firma_receptor_b64') or estado_reporte.get('firma_1_b64')
    f1_fec = firma_1_fecha or estado_reporte.get('firma_receptor_fecha') or estado_reporte.get('firma_1_fecha')
    f2_img = firma_2_img_b64 or estado_reporte.get('firma_emisor_b64') or estado_reporte.get('firma_2_b64')
    f2_fec = firma_2_fecha or estado_reporte.get('firma_emisor_fecha') or estado_reporte.get('firma_2_fecha')

    with ui.row().classes(f'w-full max-w-full mt-4 mb-2 {justify_firmas} items-end shrink-0 px-2 flex-nowrap overflow-hidden box-border'):
        # FIRMA 1: RECEPTOR / COLABORADOR
        with ui.column().classes('items-center w-60 max-w-[45%] text-center shrink-0 min-w-0'):
            with ui.element('div').classes('h-12 w-full flex items-center justify-center overflow-hidden'):
                if f1_img:
                    ui.image(f1_img).props('fit=contain').classes('h-11 max-w-[180px] object-contain')
                else:
                    ui.element('div').classes('h-12 w-full')
            ui.element('div').classes('w-full border-t border-slate-700 mb-1')
            ui.label(f1_tit).classes('text-[10px] font-bold text-slate-800 uppercase truncate w-full')
            if f1_sub:
                ui.label(f1_sub).classes('text-[9px] text-slate-600 truncate w-full')
            if f1_fec:
                ui.label(f"✓ Firmado: {f1_fec}").classes('text-[8px] text-emerald-700 font-mono font-semibold truncate w-full mt-0.5')

        # FIRMA 2: EMISOR / INGENIERÍA
        if tiene_f2:
            with ui.column().classes('items-center w-60 max-w-[45%] text-center shrink-0 min-w-0'):
                with ui.element('div').classes('h-12 w-full flex items-center justify-center overflow-hidden'):
                    if f2_img:
                        ui.image(f2_img).props('fit=contain').classes('h-11 max-w-[180px] object-contain')
                    else:
                        ui.element('div').classes('h-12 w-full')
                ui.element('div').classes('w-full border-t border-slate-700 mb-1')
                ui.label(f2_tit).classes('text-[10px] font-bold text-slate-800 uppercase truncate w-full')
                if f2_sub:
                    ui.label(f2_sub).classes('text-[9px] text-slate-600 truncate w-full')
                if f2_fec:
                    ui.label(f"✓ Firmado: {f2_fec}").classes('text-[8px] text-indigo-700 font-mono font-semibold truncate w-full mt-0.5')


def render_report_footer(estado_reporte, user_info, num_pag, total_paginas, now):
    """
    Renderiza el pie de página sagrado, 100% garantizado al borde inferior,
    con línea divisoria, metadatos institucionales y numeración Página X de Y.
    """
    with ui.row().classes('w-full min-w-full max-w-full justify-between items-center border-t border-gray-300 pt-2 pb-0.5 shrink-0 bg-white z-10 box-border'):
        footer_base = estado_reporte.get('footer_text', 'Generado por MediaHub V4')
        user_nom_raw = (user_info.get('nombres') or user_info.get('usuario') or 'Jose') if user_info else 'Jose'
        user_display = user_nom_raw.strip().split()[0].capitalize() if user_nom_raw.strip() else 'Jose'
        user_area = (user_info.get('area') if user_info else '') or 'Ingeniería'
        doc_id = estado_reporte.get('doc_id') or f"ACT-{now.strftime('%Y%m%d')}"
    
        ui.label(f'{footer_base} • ID Doc: {doc_id} • Área: {user_area} • Usuario: {user_display}').classes('text-[9px] text-gray-500 font-medium truncate min-w-0 max-w-[80%]')
        ui.label(f'Página {num_pag + 1} de {total_paginas}').classes('text-[9px] font-bold text-gray-600 shrink-0')
