from nicegui import ui
from datetime import datetime
from components.event_forms import open_event_modal
from database import get_events_by_date, check_area_has_template, detect_personnel_transition_conflicts
from components.template_builder import open_template_builder 
from components.parrilla_excel_importer import open_parrilla_importer_dialog

def de_cadena_a_minutos(hora_str):
    """Convierte 'HH:MM' a minutos absolutos desde la medianoche para cálculos matemáticos."""
    try:
        h, m = map(int, hora_str.split(':'))
        return h * 60 + m
    except Exception:
        return 0

def render_timeline(container, selected_day, month, year, user_info, on_import_success=None):
    container.clear()
    now = datetime.now()
    mes_nombre = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    fecha_str = f"{year}-{month:02d}-{selected_day:02d}"
    area_usuario = user_info.get('area', '').lower()
    eventos_del_dia = get_events_by_date(fecha_str, area_usuario)

    conflictos_del_dia = []
    try:
        conflictos_del_dia = detect_personnel_transition_conflicts(fecha_str)
    except Exception:
        conflictos_del_dia = []
    conflictos_map = {}
    for c in conflictos_del_dia:
        conflictos_map[c['evento_a']['id']] = c
        conflictos_map[c['evento_b']['id']] = c

    def refresh_panel():
        render_timeline(container, selected_day, month, year, user_info, on_import_success)
        
    def handle_import_success(target_fecha=None):
        if target_fecha and on_import_success:
            on_import_success(target_fecha)
        else:
            refresh_panel()
    
    with container:
        # Cabecera del Panel Lateral
        with ui.row().classes('w-full justify-between items-center mb-3 pb-2 border-b border-gray-100 flex-nowrap'):
            with ui.column().classes('gap-0'):
                ui.label(f"{selected_day} de {mes_nombre[month-1]}").classes('text-xl font-bold text-gray-800 leading-tight')
                with ui.row().classes('items-center gap-1.5 flex-wrap'):
                    ui.label(f"{len(eventos_del_dia)} eventos programados").classes('text-[11px] text-gray-400')
                    if conflictos_del_dia:
                        ui.badge(f"⚠️ {len(conflictos_del_dia)} Alerta Traslado").props('color=amber-8 text-color=white').classes('text-[9px] font-bold')
            
            tooltip_txt = 'Cargar Cronograma de Producción desde Excel' if area_usuario == 'produccion' else ('Cargar Parrilla de Emisión desde Excel' if area_usuario == 'programacion' else f'Cargar Cronograma de {area_usuario.capitalize()} desde Excel')
            ui.button(icon='upload_file', on_click=lambda: open_parrilla_importer_dialog(user_info, handle_import_success, default_date=fecha_str)) \
                .props('flat round dense color=indigo') \
                .tooltip(tooltip_txt)

        # =========================================================
        # MOTOR DE CALENDARIO ABSOLUTO (Estilo Google Calendar)
        # =========================================================
        # Si es programación o hay eventos de madrugada (< 06:00), abrimos la grilla 24 horas completa (00:00 - 24:00)
        tiene_madrugada = any(de_cadena_a_minutos(ev.get('hora_inicio', '12:00')) < 360 for ev in eventos_del_dia)
        es_parrilla = (area_usuario == 'programacion') or tiene_madrugada or any(ev.get('detalles', {}).get('es_parrilla_tv') for ev in eventos_del_dia)
        
        HORA_INICIO_TABLA = 0 if es_parrilla else 6
        HORA_FIN_TABLA = 24
        
        # 2 pixeles por minuto = Bloques de 30 min medirán 60px de alto
        PIXELES_POR_MINUTO = 2 
        ALTURA_TOTAL = (HORA_FIN_TABLA - HORA_INICIO_TABLA) * 60 * PIXELES_POR_MINUTO
        
        with ui.column().classes('w-full flex-grow overflow-y-auto overflow-x-hidden pr-2 wrap-none pb-4 relative'):
            
            # CONTENEDOR MAESTRO (Define el alto total del día en píxeles)
            with ui.element('div').classes('w-full relative').style(f'height: {ALTURA_TOTAL}px;'):
                
                # 1. DIBUJAR LA GRILLA DE FONDO (Líneas divisorias de tiempo)
                for h in range(HORA_INICIO_TABLA, HORA_FIN_TABLA):
                    for m in [0, 30]:
                        minutos_desde_inicio = (h * 60 + m) - (HORA_INICIO_TABLA * 60)
                        top_px = minutos_desde_inicio * PIXELES_POR_MINUTO
                        
                        es_hora_en_punto = (m == 0)
                        color_linea = 'border-gray-300' if es_hora_en_punto else 'border-gray-100'
                        grosor_linea = 'border-t-2' if es_hora_en_punto else 'border-t'
                        
                        # Dibujamos la línea de fondo anclada en su posición (z-index 0)
                        with ui.element('div').classes('absolute w-full flex flex-row items-start z-0').style(f'top: {top_px}px; height: {30 * PIXELES_POR_MINUTO}px;'):
                            bloque_texto = f"{h:02d}:{m:02d}"
                            ui.label(bloque_texto).classes(f'text-xs w-12 text-right pr-2 -mt-2 {"font-bold text-gray-500" if es_hora_en_punto else "text-gray-400"}')
                            ui.element('div').classes(f'flex-grow {grosor_linea} {color_linea}')
                
                # 2. INDICADOR DE HORA ACTUAL (Línea Roja en tiempo real)
                es_hoy = (month == now.month and year == now.year) and (selected_day == now.day)
                if es_hoy:
                    minutos_actuales = now.hour * 60 + now.minute
                    if (HORA_INICIO_TABLA * 60) <= minutos_actuales < (HORA_FIN_TABLA * 60):
                        top_actual_px = (minutos_actuales - (HORA_INICIO_TABLA * 60)) * PIXELES_POR_MINUTO
                        with ui.element('div').classes('absolute w-full flex flex-row items-center z-30 pointer-events-none').style(f'top: {top_actual_px}px;'):
                            ui.label(f"{now.hour:02d}:{now.minute:02d}").classes('text-[10px] text-red-500 font-bold w-12 text-right pr-2 -mt-2')
                            ui.element('div').classes('flex-grow border-t-2 border-red-500 -mt-2')
                            ui.html('<div class="w-2 h-2 bg-red-500 rounded-full absolute left-[44px] -mt-[10px]"></div>')

                # 3. ALGORITMO INTELIGENTE DE COLUMNAS (Maneja eventos a la misma hora)
                eventos_validos = []
                for ev in eventos_del_dia:
                    ev['min_ini'] = de_cadena_a_minutos(ev.get('hora_inicio', '00:00'))
                    ev['min_fin'] = de_cadena_a_minutos(ev.get('hora_fin', '00:00'))
                    
                    if ev['min_fin'] <= ev['min_ini']: 
                        ev['min_fin'] = ev['min_ini'] + 30 # Forzar min 30 min si alguien guardó hora_fin mal
                    
                    # Guardar solo los que entran en el rango visible del horario
                    if ev['min_fin'] > (HORA_INICIO_TABLA * 60) and ev['min_ini'] < (HORA_FIN_TABLA * 60):
                        eventos_validos.append(ev)
                        
                eventos_validos.sort(key=lambda x: x['min_ini'])
                
                columnas = []
                for ev in eventos_validos:
                    asignado = False
                    for col in columnas:
                        if ev['min_ini'] >= col[-1]['min_fin']:
                            col.append(ev)
                            asignado = True
                            break
                    if not asignado:
                        columnas.append([ev])
                        
                num_columnas = len(columnas) if columnas else 1
                ancho_porcentaje = 100 / num_columnas
                
                # 4. DIBUJAR LOS EVENTOS COMO BLOQUES ÚNICOS EXPANDIBLES
                for idx_col, col in enumerate(columnas):
                    for evento in col:
                        # Matemáticas Puras: Calculamos Alto y Posición
                        ini_limitado = max(evento['min_ini'], HORA_INICIO_TABLA * 60)
                        fin_limitado = min(evento['min_fin'], HORA_FIN_TABLA * 60)
                        duracion = fin_limitado - ini_limitado
                        
                        top_px = (ini_limitado - (HORA_INICIO_TABLA * 60)) * PIXELES_POR_MINUTO
                        height_px = duracion * PIXELES_POR_MINUTO
                        
                        # Margen reservado de 56px a la izquierda para los números de hora
                        left_css = f"calc(56px + ((100% - 56px) * {idx_col * ancho_porcentaje / 100}))"
                        width_css = f"calc(((100% - 56px) * {ancho_porcentaje / 100}) - 4px)"
                        
                        detalles = evento['detalles']
                        modalidad = detalles.get('modalidad', '')
                        es_compartido = any(k.startswith('compartir_') and v == True for k, v in detalles.items())
                        es_creador = evento['tipo'] == area_usuario
                        
                        dt_inicio_str = f"{evento['fecha']} {evento['hora_inicio']}"
                        try:
                            dt_inicio = datetime.strptime(dt_inicio_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            dt_inicio = now 
                            
                        conflicto_ev = conflictos_map.get(evento['id'])

                        # Colores basados en modalidad o estado
                        if modalidad == 'En Vivo':
                            borde, fondo = 'border-red-500', 'bg-red-50/70'
                        elif modalidad == 'Repetición':
                            borde, fondo = 'border-slate-400', 'bg-slate-50'
                        elif modalidad == 'Pregrabado':
                            borde, fondo = 'border-blue-500', 'bg-blue-50/60'
                        else:
                            borde, fondo = 'border-indigo-400', 'bg-indigo-50/50'
                            
                        etiqueta_texto, etiqueta_color = '', ''

                        if conflicto_ev:
                            borde = 'border-amber-500 border-2 ring-1 ring-amber-400'
                            fondo = 'bg-amber-50/90'
                            etiqueta_texto = f"⚠️ TRASLADO (-{conflicto_ev.get('ajuste_sugerido', 3)}m)"
                            etiqueta_color = 'text-amber-900 font-black'
                        elif es_compartido:
                            estado = detalles.get('estado_compartido', 'pendiente')
                            if estado == 'pendiente':
                                if now >= dt_inicio:
                                    borde, fondo = 'border-red-500', 'bg-red-50'
                                    etiqueta_texto, etiqueta_color = 'NO CONFIRMADO', 'text-red-600'
                                else:
                                    borde, fondo = 'border-yellow-400', 'bg-yellow-50'
                                    etiqueta_texto, etiqueta_color = 'PENDIENTE', 'text-yellow-600'
                            elif estado == 'confirmado':
                                str_conf = detalles.get('hora_confirmacion')
                                if str_conf:
                                    dt_conf = datetime.strptime(str_conf, "%Y-%m-%d %H:%M:%S")
                                    diff_minutos = (dt_inicio - dt_conf).total_seconds() / 60
                                    if diff_minutos < 0:
                                        borde, fondo = 'border-red-400', 'bg-red-100'
                                        etiqueta_texto, etiqueta_color = 'CONFIRMADO TARDE', 'text-red-700'
                                    elif diff_minutos <= 30: 
                                        borde, fondo = 'border-yellow-500', 'bg-yellow-100'
                                        etiqueta_texto, etiqueta_color = 'AL LÍMITE', 'text-yellow-700'
                                    else:
                                        borde, fondo = 'border-green-500', 'bg-green-50'
                                        etiqueta_texto, etiqueta_color = 'A TIEMPO', 'text-green-700'
                                else:
                                    borde, fondo = 'border-green-500', 'bg-green-50'
                                    etiqueta_texto, etiqueta_color = 'CONFIRMADO', 'text-green-700'
                        elif not modalidad:
                            borde, fondo = 'border-blue-400', 'bg-blue-50'
                            etiqueta_texto, etiqueta_color = 'INTERNO', 'text-blue-600'

                        # ========================================================
                        # RENDER DEL BLOQUE ADAPTABLE (RESPONSIVE EN ALTO Y ANCHO)
                        # ========================================================
                        is_micro = height_px <= 45      # Ej: 15 a 20 min
                        is_compact = 45 < height_px <= 75 # Ej: 25 a 35 min
                        is_narrow = num_columnas >= 3
                        
                        pad_cls = 'p-1' if is_micro else ('p-1.5' if is_compact else 'p-2')
                        
                        cap_tema = detalles.get('capitulo_tema')
                        prod = detalles.get('productor')
                        loc = detalles.get('locacion')
                        pautas = detalles.get('pautas_cortes') or detalles.get('observaciones')
                        camaras = detalles.get('camaras')
                        switcher = detalles.get('switcher')
                        sonido = detalles.get('sonido')
                        
                        with ui.column().classes(f'absolute {pad_cls} rounded shadow-sm border-l-4 {borde} {fondo} cursor-pointer hover:shadow-md transition-all overflow-hidden z-10 hover:z-20 flex flex-col justify-between') \
                             .style(f'top: {top_px}px; height: {height_px - 2}px; left: {left_css}; width: {width_css};') \
                             .on('click', lambda e, ev=evento: open_event_modal(user_info, selected_day, month, year, refresh_panel, ev)):
                            
                            # --- TOOLTIP FLOTANTE EN HOVER CON DETALLES COMPLETOS ---
                            with ui.tooltip().classes('bg-slate-900/95 text-white p-2.5 rounded-xl shadow-2xl border border-slate-700 max-w-xs z-50 pointer-events-none'):
                                ui.label(evento['nombre_programa']).classes('font-extrabold text-sm text-white leading-tight')
                                ui.label(f"⏰ {evento['hora_inicio']} - {evento['hora_fin']} ({duracion} min) • {modalidad or 'Emisión'}").classes('text-[11px] text-indigo-300 font-semibold')
                                if not es_creador:
                                    ui.label(f"📌 Origen: Área de {evento['tipo'].upper()}").classes('text-[10px] text-amber-300 font-medium')
                                if cap_tema:
                                    ui.label(f"🎬 Tema: {cap_tema}").classes('text-[10px] text-gray-200')
                                if prod:
                                    ui.label(f"👤 Productor: {prod}").classes('text-[10px] text-gray-200')
                                if loc:
                                    ui.label(f"📍 Locación: {loc}").classes('text-[10px] text-gray-200')
                                if camaras:
                                    cams_str = ", ".join(camaras) if isinstance(camaras, list) else str(camaras)
                                    ui.label(f"🎥 Cámaras: {cams_str}").classes('text-[10px] text-gray-300')
                                if switcher:
                                    ui.label(f"🎛️ Switcher: {switcher}").classes('text-[10px] text-gray-300')
                                if sonido:
                                    ui.label(f"🎙️ Sonido: {sonido}").classes('text-[10px] text-gray-300')
                                if conflicto_ev:
                                    ui.label(f"⚠️ {conflicto_ev['mensaje']}").classes('text-[10px] text-amber-300 font-bold bg-amber-950/80 p-1.5 rounded border border-amber-500/40 mt-1 leading-snug')
                                if pautas and pautas != cap_tema:
                                    ui.label(f"📋 Pauta: {pautas}").classes('text-[10px] text-yellow-200')
                                if etiqueta_texto:
                                    ui.label(f"Estado: {etiqueta_texto}").classes('text-[10px] font-bold text-emerald-300')

                            # --- CASO 1: TARJETA MICRO (<= 45px / <= 20 min) ---
                            if is_micro:
                                with ui.row().classes('w-full items-center justify-between gap-1 flex-nowrap overflow-hidden leading-none'):
                                    with ui.row().classes('items-center gap-1 min-w-0 flex-grow overflow-hidden'):
                                        if not es_creador:
                                            ui.label(evento['tipo'][:4].upper()).classes('text-[7px] font-black bg-indigo-600 text-white px-1 py-0.2 rounded shrink-0')
                                        ui.label(evento['nombre_programa']).classes('text-[10px] font-bold text-gray-900 truncate leading-none')
                                    ui.label(evento['hora_inicio']).classes('text-[8px] font-mono font-bold text-indigo-900 bg-white/90 px-1 py-0.2 rounded shrink-0 shadow-2xs')
                                
                                if height_px >= 36:
                                    with ui.row().classes('w-full items-center justify-between gap-1 flex-nowrap overflow-hidden text-[8px] leading-tight text-gray-500 mt-0.5'):
                                        if modalidad:
                                            badge_dot = '🔴' if modalidad == 'En Vivo' else ('🔵' if modalidad == 'Pregrabado' else '⚪')
                                            ui.label(f"{badge_dot} {modalidad}").classes('truncate')
                                        elif prod:
                                            ui.label(f"👤 {prod}").classes('truncate')
                                        elif loc:
                                            ui.label(f"📍 {loc}").classes('truncate')

                            # --- CASO 2: TARJETA COMPACTA (45px a 75px / 25 a 35 min) ---
                            elif is_compact:
                                with ui.column().classes('w-full gap-0 overflow-hidden shrink-0'):
                                    with ui.row().classes('w-full items-center justify-between gap-1 flex-nowrap leading-none mb-0.5'):
                                        if not es_creador:
                                            ui.label(f"DE: {evento['tipo'].upper()}").classes('text-[8px] font-bold text-indigo-600 tracking-wider truncate')
                                        else:
                                            ui.element('div') # spacer
                                        ui.label(f"{evento['hora_inicio']} - {evento['hora_fin']}").classes('text-[8px] text-indigo-800 font-bold bg-white/90 px-1 rounded font-mono shrink-0 ml-auto shadow-2xs')
                                    
                                    ui.label(evento['nombre_programa']).classes(f'{"text-[10px]" if is_narrow else "text-[11px]"} font-bold text-gray-900 leading-tight truncate w-full')

                                with ui.row().classes('w-full items-center justify-between gap-1 flex-nowrap overflow-hidden text-[8px] mt-0.5'):
                                    if modalidad:
                                        badge_icon = '🔴 ' if modalidad == 'En Vivo' else ('🔵 ' if modalidad == 'Pregrabado' else '⚪ ')
                                        badge_color = 'text-red-700 bg-red-100/90 border border-red-200' if modalidad == 'En Vivo' else ('text-blue-700 bg-blue-100/90 border border-blue-200' if modalidad == 'Pregrabado' else 'text-slate-700 bg-slate-100/90 border border-slate-200')
                                        ui.label(f"{badge_icon}{modalidad}").classes(f'font-bold px-1 rounded {badge_color} shrink-0 text-[8px]')
                                    
                                    if prod:
                                        ui.label(f"👤 {prod}").classes('text-indigo-900 font-semibold truncate flex-grow')
                                    elif loc:
                                        ui.label(f"📍 {loc}").classes('text-gray-600 truncate flex-grow')
                                    elif etiqueta_texto:
                                        ui.label(f"• {etiqueta_texto}").classes(f'font-bold tracking-wider shrink-0 {etiqueta_color}')

                            # --- CASO 3: TARJETA COMPLETA (> 75px / >= 40 min) ---
                            else:
                                with ui.column().classes('w-full gap-0.5 overflow-hidden shrink-0'):
                                    if not es_creador:
                                        ui.label(f"De: {evento['tipo'].upper()}").classes('text-[9px] font-bold text-indigo-600 uppercase tracking-wider mb-0 leading-tight truncate')
                                    with ui.row().classes('w-full justify-between items-start gap-1 flex-wrap'):
                                        ui.label(evento['nombre_programa']).classes(f'{"text-xs" if is_narrow else "text-sm"} font-bold text-gray-900 leading-snug truncate flex-grow')
                                        ui.label(f"{evento['hora_inicio']} - {evento['hora_fin']}").classes('text-[9px] text-indigo-800 font-bold bg-white/90 px-1 rounded shadow-xs font-mono shrink-0')
                                
                                # Modalidad badge
                                if modalidad:
                                    badge_icon = '🔴 ' if modalidad == 'En Vivo' else ('🔵 ' if modalidad == 'Pregrabado' else '⚪ ')
                                    badge_color = 'text-red-700 bg-red-100/80 border border-red-300' if modalidad == 'En Vivo' else ('text-blue-700 bg-blue-100/80 border border-blue-300' if modalidad == 'Pregrabado' else 'text-slate-700 bg-slate-100/80 border border-slate-300')
                                    ui.label(f"{badge_icon}{modalidad}").classes(f'text-[9px] font-bold px-1 rounded {badge_color} w-max mt-0.5 shrink-0')

                                # Capítulo / Tema
                                if cap_tema:
                                    ui.label(f"🎬 {cap_tema}").classes('text-[9px] text-gray-600 italic truncate w-full mt-0.5 leading-tight shrink-0')

                                # Productor Encargado
                                if prod:
                                    ui.label(f"👤 {prod}").classes('text-[9px] text-indigo-900 font-semibold truncate w-full mt-0.5 leading-tight shrink-0')

                                # Locación
                                if loc:
                                    ui.label(f"📍 {loc}").classes('text-[9px] text-gray-600 truncate w-full mt-0.5 leading-tight shrink-0')

                                # Pautas / Cortes / Observaciones
                                if pautas and pautas != cap_tema and pautas != prod and height_px > 90:
                                    ui.label(f"📋 {pautas}").classes('text-[9px] text-indigo-800 bg-indigo-50 px-1 rounded truncate w-full mt-0.5 leading-tight shrink-0 border border-indigo-100')
                                        
                                if etiqueta_texto:
                                    ui.label(f"• {etiqueta_texto}").classes(f'text-[9px] font-bold tracking-wider mt-1 shrink-0 {etiqueta_color}')


        # =========================================================
        # BOTONES INFERIORES
        # =========================================================
        tiene_plantilla = check_area_has_template(area_usuario)
        
        with ui.row().classes('w-full justify-center mt-2 pt-3 border-t border-gray-200 bg-white sticky bottom-0 z-40 gap-2 flex-col'):
            with ui.row().classes('w-full gap-2 flex-nowrap'):
                if tiene_plantilla:
                    ui.button('Nuevo Evento', icon='add', 
                              on_click=lambda: open_event_modal(user_info, selected_day, month, year, refresh_panel)) \
                      .classes('flex-grow bg-green-600 text-white font-bold rounded-lg shadow-sm py-2.5 hover:bg-green-700 transition-colors text-xs')
                    
                    ui.button(icon='edit_note', on_click=lambda: open_template_builder(user_info, refresh_panel)) \
                      .props('outline color=blue') \
                      .classes('w-12 rounded-lg shadow-sm hover:bg-blue-50') \
                      .tooltip('Editar configuración del formulario')
                else:
                    ui.button('Configurar Ficha', icon='build', 
                            on_click=lambda: open_template_builder(user_info, refresh_panel)) \
                    .classes('flex-grow bg-blue-600 text-white font-bold rounded-lg shadow-sm py-2.5 hover:bg-blue-700 transition-colors text-xs')

            # Botón de importar Parrilla / Cronograma Excel en el pie del panel (Multitenant)
            btn_pie_txt = 'Importar Cronograma de este Día (Excel)' if area_usuario == 'produccion' else ('Importar Parrilla de este Día (Excel)' if area_usuario == 'programacion' else 'Importar Cronograma de este Día (Excel)')
            ui.button(btn_pie_txt, icon='table_view', 
                      on_click=lambda: open_parrilla_importer_dialog(user_info, handle_import_success, default_date=fecha_str)) \
                .classes('w-full bg-indigo-50 text-indigo-700 font-bold border border-indigo-200 rounded-lg py-2 hover:bg-indigo-100 transition-colors text-xs')