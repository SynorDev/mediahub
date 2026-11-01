from nicegui import ui
import math
from database import get_system_logo

def render_a4_paper(container, estado_reporte, eventos_hoy, opciones_campos, area_usuario, fecha_legible, user_info, toggle_panel=None):
    """Renderiza hojas A4 nativas con un Motor de Paginación Inteligente para evitar superposición."""
    container.clear()
    
    # ==========================================
    # EL MOTOR DE PAGINACIÓN INTELIGENTE
    # (Calcula los píxeles de cada evento antes de dibujarlo)
    # ==========================================
    def estimar_altura_evento(evento, columnas):
        altura_base = 40 # Padding y bordes fijos de la fila
        if not columnas:
            return altura_base + 30
            
        num_col = len(columnas)
        # En una hoja de 794px, restando los márgenes nos quedan ~700px usables.
        # Una letra en tamaño 11px ocupa aprox 6px de ancho.
        caracteres_por_linea = (700 // num_col) // 6 
        if caracteres_por_linea < 15: caracteres_por_linea = 15 # Margen de seguridad
        
        max_altura_celda = 0
        
        for col in columnas:
            altura_celda = 0
            for campo_id in col['campos']:
                texto = ""
                detalles = evento.get('detalles', {})
                if campo_id == '__nombre__':
                    texto = str(evento.get('nombre_programa', ''))
                elif campo_id == '__horario__':
                    texto = "00:00 - 00:00"
                elif campo_id == '__locacion__':
                    texto = str(detalles.get('locacion', ''))
                else:
                    val = detalles.get(campo_id)
                    if val:
                        texto = ", ".join(val) if isinstance(val, list) else str(val)
                
                # Cada campo suma: Líneas de texto (16px c/u) + Título del campo (16px)
                lineas = math.ceil(len(texto) / caracteres_por_linea) if len(texto) > 0 else 1
                altura_celda += (lineas * 16) + 16 
                
            if altura_celda > max_altura_celda:
                max_altura_celda = altura_celda
                
        return altura_base + max_altura_celda

    # Límite estricto de la hoja antes de tocar el pie de página (De 1123px, usamos 750px para la tabla)
    ESPACIO_DISPONIBLE_POR_PAGINA = 950
    
    paginas_de_eventos = []
    pagina_actual = []
    altura_acumulada = 0
    
    # Repartidor Inteligente
    for ev in (eventos_hoy if eventos_hoy else []):
        altura_ev = estimar_altura_evento(ev, estado_reporte.get('columnas', []))
        
        # Si el evento cabe en la hoja, lo metemos. (Forzamos a meterlo si la hoja está vacía para no dejar páginas en blanco)
        if altura_acumulada + altura_ev <= ESPACIO_DISPONIBLE_POR_PAGINA or not pagina_actual:
            pagina_actual.append(ev)
            altura_acumulada += altura_ev
        else:
            # Si se desborda, cerramos esta hoja y pasamos el evento a una hoja NUEVA
            paginas_de_eventos.append(pagina_actual)
            pagina_actual = [ev]
            altura_acumulada = altura_ev
            
    if pagina_actual:
        paginas_de_eventos.append(pagina_actual)
        
    if not paginas_de_eventos:
        paginas_de_eventos = [[]] # Si no hay eventos, creamos 1 página en blanco
        
    total_paginas = len(paginas_de_eventos)

    # Medidas estrictas del A4 (Rígido)
    A4_CLASSES = 'bg-white shadow-2xl w-[794px] min-w-[794px] max-w-[794px] h-[1123px] min-h-[1123px] max-h-[1123px] shrink-0 px-12 pt-12 pb-6 relative report-page overflow-hidden'

    with container:
        with ui.column().classes('w-full max-w-full h-[calc(100vh-100px)] overflow-x-auto overflow-y-auto bg-gray-200 py-6 px-2 sm:px-4 flex-nowrap scroll-smooth'):
            
            with ui.column().classes('w-fit min-w-full flex flex-col items-center gap-6 mx-auto'):
                # 1. BARRA SUPERIOR RESPONSIVE
                with ui.row().classes('w-full max-w-[794px] justify-between items-center bg-white p-3 sm:p-4 rounded-xl shadow-md border border-gray-200 shrink-0 flex-wrap gap-2'):
                    with ui.row().classes('items-center gap-2'):
                        if toggle_panel:
                            ui.button(icon='space_dashboard', on_click=toggle_panel).props('flat round color=blue').tooltip('Ocultar/Mostrar Maquetador')
                        ui.label('Vista Previa de Impresión').classes('text-gray-800 font-bold text-sm sm:text-base')
                    
                    ui.label(f'Total: {len(eventos_hoy) if eventos_hoy else 0} eventos | {total_paginas} Hojas A4').classes('text-gray-600 font-bold text-xs sm:text-sm')

                # 2. DIBUJO DE LAS HOJAS (Usando las páginas calculadas por el motor)
                logo_actual = estado_reporte.get('logo_b64') or get_system_logo()

                for num_pag, eventos_pagina in enumerate(paginas_de_eventos):

                    with ui.column().classes(A4_CLASSES).props(f'id="report-paper-{num_pag}"'):
                        
                        # --- Cabecera con Logo Persistente ---
                        with ui.row().classes('w-full justify-between items-start border-b-2 border-gray-800 pb-6 mb-6 flex-nowrap shrink-0'):
                            if logo_actual:
                                ui.image(logo_actual).props('fit=contain').classes('w-56 h-20 object-contain shrink-0 p-1')
                            else:
                                with ui.row().classes('w-40 h-14 items-center justify-center bg-gradient-to-r from-slate-900 to-indigo-950 rounded-lg shadow-sm border border-slate-700 shrink-0 px-3'):
                                    ui.icon('live_tv', size='md').classes('text-indigo-400 mr-2')
                                    ui.label('MEDIAHUB').classes('text-lg font-black text-white tracking-widest')
                            
                            with ui.column().classes('items-end gap-0 shrink-0'):
                                ui.label('MEDIAHUB V4').classes('text-2xl font-black text-gray-800 tracking-tighter')
                                ui.label('Documento Operativo Oficial').classes('text-xs text-gray-500 font-bold uppercase tracking-widest')
                                ui.label(f"Área: {area_usuario.upper()}").classes('text-xs text-gray-400 mt-2 font-semibold')
                                ui.label(f"Fecha: {fecha_legible}").classes('text-xs text-gray-400')

                        ui.label(estado_reporte['titulo']).classes('text-xl font-bold text-gray-800 mb-8 w-full block text-center uppercase tracking-widest shrink-0')

                        # ==========================================
                        # LA TABLA NATIVA 
                        # ==========================================
                        if not eventos_hoy:
                            ui.label('No hay eventos programados para hoy.').classes('text-center w-full block text-gray-400 italic mt-12 flex-grow')
                        elif not estado_reporte['columnas']:
                            ui.label('No has configurado ninguna columna en el panel derecho.').classes('text-center w-full block text-red-400 font-bold mt-12 flex-grow')
                        else:
                            num_col = len(estado_reporte['columnas'])
                            
                            with ui.column().classes('w-full gap-0 border border-gray-200 rounded-sm shrink-0 overflow-hidden'):
                                
                                # Cabeceras
                                with ui.grid(columns=num_col).classes('w-full bg-slate-900 text-white gap-0'):
                                    for col in estado_reporte['columnas']:
                                        ui.label(col["titulo"].upper()).classes('p-2 text-[10px] font-bold text-left w-full')
                                        
                                # Filas
                                for ev in eventos_pagina:
                                    detalles = ev.get('detalles', {})
                                    
                                    with ui.grid(columns=num_col).classes('w-full border-t border-slate-300 bg-white gap-0 hover:bg-slate-50'):
                                        for idx, col in enumerate(estado_reporte['columnas']):
                                            borde_derecho = 'border-r border-dashed border-slate-200' if idx < num_col - 1 else ''
                                            
                                            with ui.column().classes(f'p-3 gap-2 {borde_derecho} overflow-hidden w-full'):
                                                hay_datos = False
                                                
                                                for campo_id in col['campos']:
                                                    if campo_id == '__nombre__':
                                                        ui.label(ev['nombre_programa']).classes('text-[13px] font-bold text-slate-900 leading-tight whitespace-normal break-words w-full')
                                                        hay_datos = True
                                                    elif campo_id == '__horario__':
                                                        ui.label(f"⏰ {ev['hora_inicio']} - {ev['hora_fin']}").classes('text-[10px] font-bold text-slate-600 whitespace-normal break-words w-full')
                                                        hay_datos = True
                                                    elif campo_id == '__locacion__':
                                                        loc = detalles.get('locacion')
                                                        if loc: 
                                                            ui.label(f"📍 {loc}").classes('text-[10px] text-blue-900 whitespace-normal break-words w-full')
                                                            hay_datos = True
                                                    else:
                                                        val = detalles.get(campo_id)
                                                        if val:
                                                            val_str = ", ".join(val) if isinstance(val, list) else str(val)
                                                            lbl = opciones_campos.get(campo_id, campo_id.upper())
                                                            
                                                            with ui.column().classes('gap-0 w-full'):
                                                                ui.label(f"{lbl}:").classes('text-[10px] font-bold text-slate-500 leading-tight')
                                                                ui.label(val_str).classes('text-[11px] text-slate-800 whitespace-normal break-words leading-tight w-full')
                                                            hay_datos = True
                                                
                                                if not hay_datos:
                                                    ui.label('-').classes('text-slate-400 italic text-[11px]')

                        # ESTE ES EL ESCUDO: ui.space() empuja todo hacia abajo y protege el pie de página
                        ui.space() 
                        
                        # --- Pie de página SEGURO Y PROTEGIDO ---
                        with ui.row().classes('w-full justify-between items-center border-t border-gray-300 pt-4 mt-auto shrink-0'):
                            ui.label(f'Generado por MediaHub V4 • ID: {user_info.get("usuario", "N/A")}').classes('text-[10px] text-gray-400')
                            ui.label(f'Página {num_pag + 1} de {total_paginas}').classes('text-[10px] font-bold text-gray-500')
