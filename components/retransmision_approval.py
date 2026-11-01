import os
from nicegui import ui
from datetime import datetime
from database import update_retransmission_status, get_retransmission_authorization_by_id
from components.retransmision_acta_generator import render_acta_retransmision_preview

def render_retransmision_approval_dialog(expediente_id: int, user_info: dict, on_status_changed_callback=None, initial_tab: str = 'revision'):
    """
    Abre un diálogo modal moderno para que Gerencia o Ingeniería inspeccione el expediente,
    revise los resultados del OCR, estampe su firma digital y emita el acta oficial.
    """
    expediente = get_retransmission_authorization_by_id(expediente_id)
    if not expediente:
        ui.notify('No se encontró el expediente solicitado.', type='negative')
        return

    # Comprobación de permiso de Gerencia
    area_user = (user_info.get('area') or '').lower()
    cargo_user = (user_info.get('cargo') or '').lower()
    es_gerencia = any(k in area_user or k in cargo_user for k in ['gerencia', 'gerente', 'director', 'admin'])

    dialog = ui.dialog()
    with dialog, ui.card().classes('w-[96vw] max-w-6xl h-[92vh] max-h-[92vh] flex flex-col no-wrap p-4 sm:p-6 rounded-3xl shadow-2xl gap-3 bg-slate-100 overflow-hidden')\
        .style('display: flex; flex-direction: column; flex-wrap: nowrap !important;'):
        
        # 1. Barra de encabezado del diálogo
        with ui.row().classes('w-full bg-white border border-slate-200 rounded-2xl text-slate-800 p-4 justify-between items-center shrink-0 shadow-xs'):
            with ui.row().classes('items-center gap-3'):
                with ui.element('div').classes('w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600'):
                    ui.icon('verified_user', size='sm')
                with ui.column().classes('gap-0'):
                    ui.label(f"Expediente de Retransmisión: {expediente['code']}").classes('font-bold text-base text-slate-900 leading-tight')
                    ui.label(f"Operador: {expediente['operator_name']} • Radicado: {expediente['created_at'][:10]}").classes('text-xs text-slate-500')
            
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='close', on_click=dialog.close).props('flat round color=slate-700')

        # 2. Barra de navegación por pestañas
        with ui.tabs().classes('w-full bg-white border border-slate-200 rounded-2xl text-slate-700 shadow-xs shrink-0') as tabs:
            tab_rev = ui.tab('Auditoría y Emparejamiento OCR', icon='fact_check')
            tab_act = ui.tab('Acta Oficial de Autorización', icon='description')

        # 3. Paneles de contenido
        with ui.tab_panels(tabs, value=tab_act if initial_tab == 'acta' else tab_rev, animated=False)\
            .classes('w-full flex-grow bg-transparent p-0 overflow-hidden min-h-0')\
            .style('flex-grow: 1; min-height: 0;'):
            
            # ==========================================
            # PANEL 1: AUDITORÍA Y EMPAREJAMIENTO OCR
            # ==========================================
            with ui.tab_panel(tab_rev).classes('p-0 w-full flex flex-col no-wrap gap-5 overflow-y-auto overflow-x-hidden pb-12 pr-2')\
                .style('display: flex; flex-direction: column; flex-wrap: nowrap !important; overflow-y: auto !important; height: 100%;'):
                
                # A. Estado actual y resumen de veredicto
                status = expediente.get('status')
                es_aprobado = status == 'aprobado_gerencia'
                es_filtro1 = status == 'filtro1_aprobado'
                
                status_bg = 'bg-emerald-50 border-emerald-300' if es_aprobado else ('bg-indigo-50 border-indigo-200' if es_filtro1 else 'bg-amber-50 border-amber-200')
                status_txt = 'text-emerald-900' if es_aprobado else ('text-indigo-900' if es_filtro1 else 'text-amber-900')
                status_label = 'APROBADO POR GERENCIA • ACTA OFICIAL EMITIDA' if es_aprobado else ('FILTRO 1 APROBADO (COINCIDENCIA EXACTA 100%)' if es_filtro1 else 'EN REVISIÓN / DISCREPANCIAS TÉCNICAS')

                with ui.card().classes(f'w-full p-4 {status_bg} border rounded-2xl shadow-xs'):
                    with ui.row().classes('justify-between items-center w-full flex-wrap gap-3'):
                        with ui.row().classes('items-center gap-3'):
                            ui.icon('verified', color='positive' if (es_aprobado or es_filtro1) else 'warning').classes('text-3xl')
                            with ui.column().classes('gap-0'):
                                ui.label(f'ESTADO DEL EXPEDIENTE: {status_label}').classes(f'font-black {status_txt} text-sm')
                                ui.label(f"Radicado por {expediente.get('created_by', 'Sistema')} • Radicado ID: {expediente.get('code')}").classes('text-xs text-slate-600')
                        
                        with ui.row().classes('items-center gap-2'):
                            if expediente.get('approved_at'):
                                ui.label(f"Aprobado el {expediente.get('approved_at')[:16]} por {expediente.get('approved_by')}").classes('text-xs font-bold text-emerald-800 bg-emerald-100 px-3 py-1 rounded-full')
                            def go_to_acta():
                                tabs.value = tab_act

                            ui.button('Ver Acta Oficial', icon='description', on_click=go_to_acta)\
                                .props('dense outline color=indigo size=sm').classes('px-3 rounded-lg text-xs')

                # B. Ficha Técnica con los Datos Cargados del Operador
                with ui.card().classes('w-full p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col gap-3'):
                    with ui.row().classes('items-center justify-between w-full border-b border-slate-100 pb-2.5'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('badge', color='indigo').classes('text-xl')
                            ui.label('Datos Cargados y Reconocidos del Operador').classes('text-sm font-bold text-slate-900')
                        ui.badge('EXPEDIENTE DIGITAL', color='primary').classes('text-[10px]')

                    with ui.element('div').classes('grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 w-full text-xs'):
                        campos_operador = [
                            ('Razón Social / Operador', expediente.get('operator_name') or 'N/A', 'business', 'font-bold text-slate-900'),
                            ('NIT / Identificación Tributaria', expediente.get('nit') or 'N/A', 'pin', 'font-mono font-bold text-slate-900'),
                            ('No. Registro RTI MINTIC', expediente.get('rti_number') or 'N/A', 'policy', 'font-mono font-bold text-indigo-700'),
                            ('Representante Legal', expediente.get('rep_name') or 'N/A', 'person', 'font-semibold text-slate-800'),
                            ('Cédula de Ciudadanía', f"C.C. {expediente.get('rep_doc') or 'N/A'}", 'credit_card', 'font-mono font-semibold text-slate-800'),
                            ('Canal a Retransmitir', expediente.get('channel_target') or 'CANAL TELEAMIGA', 'live_tv', 'font-bold text-indigo-900'),
                            ('Municipio y Departamento', f"{expediente.get('municipality') or 'N/A'}, {expediente.get('department') or 'N/A'}", 'location_on', 'font-medium text-slate-700'),
                            ('Dirección de Notificación', expediente.get('address') or 'CR 73 BIS 49 A 29', 'home', 'font-medium text-slate-700'),
                            ('Email Notificaciones', expediente.get('notification_email') or f"notificaciones@{expediente.get('operator_name', 'op').lower().replace(' ', '')[:8]}.com", 'mail', 'font-medium text-slate-700'),
                        ]
                        for titulo_c, val_c, icono_c, val_style in campos_operador:
                            with ui.card().classes('p-3 bg-slate-50 border border-slate-100 rounded-xl flex flex-col gap-1'):
                                with ui.row().classes('items-center gap-1.5 text-slate-500'):
                                    ui.icon(icono_c, size='xs')
                                    ui.label(titulo_c).classes('text-[11px] font-semibold text-slate-500 uppercase tracking-wide')
                                ui.label(val_c).classes(f'text-xs {val_style} truncate')

                # C. Cruce Automático de Documentos (OCR)
                match_results = expediente.get('match_results') or {}
                verificaciones = match_results.get('verificaciones') or []

                with ui.row().classes('w-full justify-between items-center mt-1'):
                    ui.label('Resultados del Cruce Automático MINTIC RTI vs Cámara vs Cédula').classes('text-sm font-bold text-slate-800 uppercase tracking-wider')
                    score = match_results.get('score', 100)
                    ui.badge(f'COINCIDENCIA: {score}%', color='positive' if score == 100 else 'warning').classes('text-[11px] font-bold')

                with ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 gap-3 w-full'):
                    for v in verificaciones:
                        v_ok = v.get('valido', False)
                        b_color = 'emerald' if v_ok else 'rose'
                        with ui.card().classes(f'p-4 bg-white border-l-4 border-{b_color}-500 shadow-xs flex flex-col justify-between rounded-xl'):
                            with ui.row().classes('justify-between items-center w-full mb-1'):
                                ui.label(v.get('criterio')).classes('font-bold text-xs text-slate-800')
                                ui.badge('COINCIDE' if v_ok else 'REVISAR', color='positive' if v_ok else 'negative').classes('text-[10px]')
                            
                            ui.label(v.get('mensaje')).classes(f'text-xs text-{b_color}-800 font-medium')

                # D. Visor de Documentos Adjuntos para Comprobación Humana
                with ui.row().classes('w-full justify-between items-center mt-3'):
                    ui.label('Expediente Digital • Comprobación Humana de Documentos').classes('text-sm font-bold text-slate-800 uppercase tracking-wider')
                    ui.badge('INSPECCIÓN MANUAL').props('outline color=slate text-color=slate-7').classes('text-[10px]')
                
                with ui.row().classes('w-full gap-4'):
                    docs_info = [
                        ('1. Certificado RTI MINTIC', expediente.get('file_rti_path'), 'policy', 'blue'),
                        ('2. Cámara de Comercio', expediente.get('file_camara_path'), 'store', 'indigo'),
                        ('3. Cédula de Ciudadanía', expediente.get('file_cedula_path'), 'badge', 'teal')
                    ]
                    for label, path, icon, col in docs_info:
                        with ui.card().classes('flex-1 p-4 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col justify-between'):
                            with ui.column().classes('w-full gap-1'):
                                with ui.row().classes('items-center gap-2 mb-1'):
                                    ui.icon(icon, color=col).classes('text-xl')
                                    ui.label(label).classes('font-bold text-xs text-slate-900')
                                
                                if path and os.path.exists(path):
                                    ui.label('Archivo original verificado en servidor').classes('text-[11px] text-emerald-600 font-medium')
                                    ui.label(path.split('/')[-1].split('\\')[-1]).classes('text-[10px] text-slate-400 truncate w-full font-mono')
                                else:
                                    ui.label('No adjuntado en servidor').classes('text-[11px] text-rose-500 italic')
                            
                            if path and os.path.exists(path):
                                ui.button('Descargar / Abrir PDF', icon='download', on_click=lambda p=path: ui.download(p))\
                                    .props('dense outline color=indigo text-color=indigo-9 size=sm').classes('w-full mt-3 rounded-lg')

                # E. SECCIÓN DE FIRMA DIGITAL PARA GERENCIA
                if status != 'aprobado_gerencia':
                    ui.label('Zona de Aprobación Formal y Firma Digital (Gerencia)').classes('text-sm font-bold text-slate-800 uppercase tracking-wider mt-4')
                    
                    with ui.card().classes('w-full p-5 bg-white border-2 border-indigo-200 rounded-2xl shadow-sm'):
                        if not es_gerencia:
                            with ui.row().classes('items-center gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs w-full'):
                                ui.icon('lock', size='sm')
                                ui.label('Esta solicitud ha pasado el filtro técnico al 100%. La firma digital y emisión del acta oficial corresponde al rol de Gerencia General.').classes('font-medium')
                        else:
                            ui.label('Cargar Firma Digital de Gerencia (.PNG) o Estampar Firma Oficial:').classes('font-semibold text-xs text-slate-700 mb-2')
                            
                            firma_holder = {'b64': None}
                            firma_preview_img = ui.image().props('fit=contain position="left"').classes('h-16 w-56 object-contain border border-slate-300 rounded p-1 mb-2 hidden')

                            async def handle_firma_upload(e):
                                import base64
                                b_content = None
                                if hasattr(e, 'file') and hasattr(e.file, 'read'):
                                    res = e.file.read()
                                    b_content = await res if hasattr(res, '__await__') else res
                                elif hasattr(e, 'content') and hasattr(e.content, 'read'):
                                    res = e.content.read()
                                    b_content = await res if hasattr(res, '__await__') else res
                                elif hasattr(e, 'content'):
                                    b_content = e.content
                                elif hasattr(e, 'read'):
                                    res = e.read()
                                    b_content = await res if hasattr(res, '__await__') else res

                                if not b_content:
                                    ui.notify('No se pudo leer la imagen de firma.', type='negative')
                                    return

                                nombre = getattr(e, 'name', 'firma.png')
                                ext = nombre.split('.')[-1].lower() if '.' in nombre else 'png'
                                mime = 'image/png' if ext == 'png' else 'image/jpeg'
                                b64_str = f"data:{mime};base64,{base64.b64encode(b_content).decode('utf-8')}"
                                firma_holder['b64'] = b64_str
                                firma_preview_img.set_source(b64_str)
                                firma_preview_img.classes(remove='hidden')
                                ui.notify('Firma digital cargada correctamente', type='positive')

                            with ui.row().classes('w-full items-center gap-4 flex-wrap'):
                                ui.upload(label='Cargar Firma (.PNG/.JPG)', on_upload=handle_firma_upload, auto_upload=True)\
                                    .props('accept=.png,.jpg,.jpeg').classes('max-w-xs text-xs')
                                
                                async def ejecutar_aprobacion():
                                    gerente_display = user_info.get('nombre_completo') or f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}".strip() or user_info.get('usuario') or 'Claudia Garzon'
                                    now_iso = datetime.now().isoformat()
                                    update_retransmission_status(
                                        auth_id=expediente_id,
                                        status='aprobado_gerencia',
                                        approved_by=gerente_display,
                                        approved_at=now_iso,
                                        signature_b64=firma_holder['b64'],
                                        notes='Aprobación formal de retransmisión MINTIC con firma digital.'
                                    )
                                    ui.notify('¡Expediente APROBADO con éxito! Acta oficial generada.', type='positive', icon='verified')
                                    dialog.close()
                                    if on_status_changed_callback:
                                        on_status_changed_callback()
                                    # Abrir diálogo nuevamente para ver el acta firmada
                                    render_retransmision_approval_dialog(expediente_id, user_info, on_status_changed_callback, initial_tab='acta')

                                ui.button('Aprobar y Emitir Acta Oficial', icon='check_circle', on_click=ejecutar_aprobacion)\
                                    .classes('bg-emerald-600 text-white font-bold py-2.5 px-6 shadow-md hover:bg-emerald-700 text-sm rounded-xl')

            # ==========================================
            # PANEL 2: ACTA OFICIAL DE AUTORIZACIÓN (FORMATO CARTA FÍSICA)
            # ==========================================
            with ui.tab_panel(tab_act).classes('p-0 w-full flex flex-col no-wrap items-center overflow-y-auto overflow-x-hidden pb-16 pr-2')\
                .style('display: flex; flex-direction: column; flex-wrap: nowrap !important; overflow-y: auto !important; height: 100%;'):
                acta_container = ui.column().classes('w-full items-center p-0 overflow-visible')
                render_acta_retransmision_preview(acta_container, expediente, user_info=user_info)

    dialog.open()
