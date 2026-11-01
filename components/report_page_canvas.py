from nicegui import ui
from datetime import datetime
from database import get_system_logo, obtener_detalles_modulo_vinculado
from components.report_table_renderer import estimar_altura_registro, render_report_table
from components.report_header_footer import (
    resolver_texto_con_variables,
    estimar_altura_texto,
    render_report_header,
    render_report_apertura,
    render_report_cierre,
    render_report_firmas,
    render_report_footer
)

def obtener_especificacion_papel(formato_papel='letter'):
    """
    Retorna la configuración física del formato de hoja (Carta / A4),
    incluyendo espacio vertical útil, dimensiones en píxeles y clases CSS base.
    """
    if str(formato_papel).lower() == 'a4':
        return {
            'formato': 'a4',
            'label': 'A4',
            'ancho_px': 794,
            'alto_px': 1123,
            'espacio_disponible': 800,
            'paper_classes': 'bg-white shadow-2xl w-[794px] min-w-[794px] max-w-[794px] h-[1123px] min-h-[1123px] max-h-[1123px] shrink-0 px-10 pt-7 pb-5 relative report-page overflow-hidden flex flex-col justify-between box-border'
        }
    else:
        return {
            'formato': 'letter',
            'label': 'Carta',
            'ancho_px': 816,
            'alto_px': 1056,
            'espacio_disponible': 740,
            'paper_classes': 'bg-white shadow-2xl w-[816px] min-w-[816px] max-w-[816px] h-[1056px] min-h-[1056px] max-h-[1056px] shrink-0 px-10 pt-7 pb-5 relative report-page overflow-hidden flex flex-col justify-between box-border'
        }


def calcular_paginacion_reporte(registros, estado_reporte, config_campos, cache_detalles_modulos=None, 
                                altura_apertura=0, altura_pie_final=0, espacio_disponible=740):
    """
    Motor determinista de paginación:
    1. Garantiza cero hojas en blanco (cada página tiene al menos 1 registro).
    2. El primer registro siempre se incluye en la hoja inicial.
    3. Reubica inteligentemente el último registro a una nueva hoja junto a las firmas si no cabe,
       evitando que las firmas expulsen el pie de página fuera de la hoja.
    """
    num_total_reg = len(registros) if registros else 0
    if num_total_reg == 0:
        return [[]], 0

    paginas_de_registros = []
    pagina_actual = []
    altura_acumulada = 0

    for idx_reg, reg in enumerate(registros):
        altura_reg = estimar_altura_registro(
            reg, estado_reporte.get('columnas', []), config_campos, estado_reporte, cache_detalles_modulos
        )
        es_primera_hoja = (len(paginas_de_registros) == 0)
        limite_hoja = espacio_disponible - (altura_apertura if es_primera_hoja else 0)

        # Regla: Si la página actual no tiene elementos, SIEMPRE lo agregamos para evitar hojas en blanco
        if not pagina_actual:
            pagina_actual.append(reg)
            altura_acumulada = altura_reg
        elif altura_acumulada + altura_reg <= limite_hoja:
            pagina_actual.append(reg)
            altura_acumulada += altura_reg
        else:
            paginas_de_registros.append(pagina_actual)
            pagina_actual = [reg]
            altura_acumulada = altura_reg

    if pagina_actual:
        paginas_de_registros.append(pagina_actual)

    # Ubicación inteligente del pie final (cláusula de cierre y firmas)
    ultima_pag_idx = len(paginas_de_registros) - 1
    es_primera_hoja = (ultima_pag_idx == 0)
    limite_ultima_hoja = espacio_disponible - (altura_apertura if es_primera_hoja else 0)

    altura_items_ultima_pag = sum(
        estimar_altura_registro(r, estado_reporte.get('columnas', []), config_campos, estado_reporte, cache_detalles_modulos)
        for r in paginas_de_registros[ultima_pag_idx]
    )

    if altura_items_ultima_pag + altura_pie_final <= limite_ultima_hoja:
        pie_final_en_pagina = ultima_pag_idx
    else:
        # Si no cabe con todos los ítems de la última hoja, trasladamos el último ítem
        # a una nueva hoja para que acompañe el cierre y firmas sin dejar hojas vacías
        if len(paginas_de_registros[ultima_pag_idx]) > 1:
            item_trasladado = paginas_de_registros[ultima_pag_idx].pop()
            paginas_de_registros.append([item_trasladado])
            pie_final_en_pagina = len(paginas_de_registros) - 1
        else:
            pie_final_en_pagina = ultima_pag_idx

    return paginas_de_registros, pie_final_en_pagina


def render_custom_a4_paper(container, estado_reporte, registros, opciones_campos, config_campos, 
                           modulo_nombre, modulo_icono, fecha_legible, user_info, 
                           toggle_panel=None, on_download_pdf=None):
    """
    Unificador supremo del reporte:
    Ensambla el canvas físico (Carta o A4), ejecuta la paginación determinista
    e integra secuencialmente:
      1. Encabezado institucional
      2. Cláusula de apertura (Pág 1)
      3. Tabla CSS Grid con acomodación inteligente
      4. Cláusula de cierre y firmas (Última Pág)
      5. Pie de página sagrado al borde inferior
    """
    container.clear()
    now = datetime.now()
    lista_registros = registros if registros else []

    # Pre-cargar cachés de módulos vinculados
    cache_detalles_modulos = {}
    cache_opciones_modulos = {}
    for f in config_campos.values():
        if f.get('type') == 'linked_data' and f.get('linked_module_id'):
            mid = f['linked_module_id']
            if mid not in cache_detalles_modulos:
                cache_detalles_modulos[mid] = obtener_detalles_modulo_vinculado(mid)
                cache_opciones_modulos[mid] = {k: v['label'] for k, v in cache_detalles_modulos[mid].items()}

    # Resolución de variables dinámicas en cláusulas
    raw_apertura = (estado_reporte.get('texto_apertura') or '').strip()
    raw_cierre = (estado_reporte.get('texto_cierre') or '').strip()
    persona_fijada = estado_reporte.get('persona_fijada')
    texto_apertura = resolver_texto_con_variables(raw_apertura, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)
    texto_cierre = resolver_texto_con_variables(raw_cierre, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)
    
    f1_tit_raw = estado_reporte.get('firma_1_titulo', 'Firma de Recibido')
    f1_sub_raw = estado_reporte.get('firma_1_subtitulo', '[RESPONSABLE] / C.C.')
    f2_tit_raw = estado_reporte.get('firma_2_titulo', 'Entregado Por')
    f2_sub_raw = estado_reporte.get('firma_2_subtitulo', 'Departamento de Ingeniería')

    texto_f1_tit = resolver_texto_con_variables(f1_tit_raw, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)
    texto_f1_sub = resolver_texto_con_variables(f1_sub_raw, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)
    texto_f2_tit = resolver_texto_con_variables(f2_tit_raw, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)
    texto_f2_sub = resolver_texto_con_variables(f2_sub_raw, lista_registros, config_campos, cache_detalles_modulos, cache_opciones_modulos, persona_fijada, user_info)

    mostrar_apertura = estado_reporte.get('mostrar_clausula_apertura', True) and bool(texto_apertura)
    mostrar_cierre = estado_reporte.get('mostrar_clausula_cierre', True) and bool(texto_cierre)
    mostrar_firmas = estado_reporte.get('mostrar_firmas', False)

    altura_apertura = estimar_altura_texto(texto_apertura, caracteres_por_linea=85, altura_linea=18) if mostrar_apertura else 0
    altura_cierre = estimar_altura_texto(texto_cierre, caracteres_por_linea=85, altura_linea=16) if mostrar_cierre else 0
    altura_firmas = 135 if mostrar_firmas else 0
    altura_pie_final = altura_cierre + altura_firmas

    # Especificación física del formato de papel
    papel_cfg = obtener_especificacion_papel(estado_reporte.get('formato_papel', 'letter'))
    
    # Motor de paginación determinista
    paginas_de_registros, pie_final_en_pagina = calcular_paginacion_reporte(
        lista_registros, estado_reporte, config_campos, cache_detalles_modulos,
        altura_apertura=altura_apertura, altura_pie_final=altura_pie_final,
        espacio_disponible=papel_cfg['espacio_disponible']
    )
    total_paginas = len(paginas_de_registros)
    logo_actual = estado_reporte.get('logo_b64') or get_system_logo()

    with container:
        with ui.column().classes('w-full max-w-full h-full overflow-y-auto overflow-x-auto bg-gray-200 py-6 px-2 sm:px-4 flex-nowrap scroll-smooth'):
            with ui.column().classes('w-fit min-w-full flex flex-col items-center gap-8 mx-auto flex-nowrap'):
                
                # BARRA SUPERIOR DE HERRAMIENTAS Y CONTROL
                with ui.row().classes(f'w-full max-w-[{papel_cfg["ancho_px"]}px] justify-between items-center bg-white p-3 sm:p-4 rounded-xl shadow-md border border-gray-200 shrink-0 flex-wrap gap-2'):
                    with ui.row().classes('items-center gap-2'):
                        if toggle_panel:
                            ui.button(icon='space_dashboard', on_click=toggle_panel).props('flat round color=blue').tooltip('Ocultar/Mostrar Configuración')
                        ui.label(f'Vista Previa de Impresión ({papel_cfg["label"]})').classes('text-gray-800 font-bold text-sm sm:text-base')
                    
                    with ui.row().classes('items-center gap-4'):
                        if on_download_pdf:
                            ui.button('Exportar PDF', icon='picture_as_pdf', on_click=on_download_pdf) \
                                .classes('bg-red-600 text-white font-bold px-4 py-2 rounded-lg shadow-sm hover:bg-red-700 transition-colors text-xs')
                        ui.label(f'Total: {len(lista_registros)} ítems | {total_paginas} Hoja(s) {papel_cfg["label"]}').classes('text-gray-600 font-bold text-xs sm:text-sm')

                # ENSAMBLADO DE HOJAS FÍSICAS (CARTA / A4) - APILADAS VERTICALMENTE
                for num_pag, registros_pagina in enumerate(paginas_de_registros):
                    with ui.column().classes(papel_cfg['paper_classes']).props(f'id="report-paper-{num_pag}"'):
                        
                        # CUERPO PRINCIPAL (FLEX-GROW PROTEGIDO ANTI-DESBORDE)
                        with ui.column().classes('w-full flex-grow flex flex-col justify-start min-h-0 overflow-hidden'):
                            
                            # 1. Encabezado institucional
                            render_report_header(estado_reporte, modulo_nombre, fecha_legible, now, logo_actual)

                            # 2. Cláusula de apertura (Pág 1)
                            if num_pag == 0 and mostrar_apertura:
                                render_report_apertura(texto_apertura, estado_reporte)

                            # 3. Tabla CSS Grid con acomodación inteligente
                            render_report_table(
                                registros_pagina=registros_pagina,
                                estado_reporte=estado_reporte,
                                config_campos=config_campos,
                                opciones_campos=opciones_campos,
                                cache_detalles_modulos=cache_detalles_modulos,
                                cache_opciones_modulos=cache_opciones_modulos,
                                resolver_texto_fn=resolver_texto_con_variables,
                                persona_fijada=persona_fijada,
                                user_info=user_info,
                                num_pag=num_pag,
                                pie_final_en_pagina=pie_final_en_pagina,
                                mostrar_firmas=mostrar_firmas
                            )

                            # 4. Cláusula de cierre (Última Pág con cierre)
                            if num_pag == pie_final_en_pagina and mostrar_cierre:
                                render_report_cierre(texto_cierre, estado_reporte)

                            # Espaciador flexible para empujar firmas hacia el final
                            ui.space()

                            # 5. Firmas institucionales (Última Pág)
                            if num_pag == pie_final_en_pagina and mostrar_firmas:
                                render_report_firmas(
                                    estado_reporte,
                                    texto_f1_tit=texto_f1_tit,
                                    texto_f1_sub=texto_f1_sub,
                                    texto_f2_tit=texto_f2_tit,
                                    texto_f2_sub=texto_f2_sub,
                                    firma_1_img_b64=estado_reporte.get('firma_receptor_b64'),
                                    firma_1_fecha=estado_reporte.get('firma_receptor_fecha'),
                                    firma_2_img_b64=estado_reporte.get('firma_emisor_b64'),
                                    firma_2_fecha=estado_reporte.get('firma_emisor_fecha')
                                )

                        # 6. PIE DE PÁGINA SAGRADO (FIJADO AL BORDE INFERIOR)
                        render_report_footer(estado_reporte, user_info, num_pag, total_paginas, now)
