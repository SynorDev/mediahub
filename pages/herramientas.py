from nicegui import ui, app
from components.topbar import topbar
from components.sidebar import sidebar
from database import (
    get_user_by_usuario, 
    get_all_retransmission_authorizations,
    get_active_survey,
    get_user_survey_response
)

def herramientas_page():
    username = app.storage.user.get('username')
    
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return
        
    ui.query('body').style('background-color: #f8fafc; margin: 0; padding: 0;')

    # Cabecera y Navegación
    topbar(user_info)
    sidebar(user_info)

    # Detección de roles y permisos estrictos por área encargada
    user_usuario = (user_info.get('usuario') or '').strip().lower()
    user_full_name = f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}".strip().lower()
    user_area = (user_info.get('area_encargada') or user_info.get('area') or '').strip().lower()
    user_cargo = (user_info.get('cargo') or '').strip().lower()

    user_rol = (user_info.get('rol') or '').strip().lower()

    # Administrador General (acceso a todas las herramientas)
    es_admin = (
        user_rol in ['admin general', 'administrador general', 'admin', 'administrador'] or
        user_info.get('es_admin', False) or
        user_usuario in ['jose', 'admin', 'administrador'] or
        ('jose rafael' in user_full_name and 'cifuentes' in user_full_name) or
        'admin' in user_cargo or 'administrador' in user_cargo
    )
    es_subadmin = user_rol in ['sub admin', 'sub-admin', 'subadmin'] or user_info.get('es_subadmin', False)

    # Identificación estricta por área encargada
    es_ingenieria = any(k in user_area for k in ['ingenieria', 'ingeniería', 'sistemas'])
    es_gerencia = any(k in user_area for k in ['gerencia', 'dirección general', 'direccion general']) or any(k in user_cargo for k in ['gerente', 'director general', 'directora general'])
    es_edicion = any(k in user_area for k in ['edicion', 'edición', 'postproduccion', 'postproducción']) or any(k in user_cargo for k in ['editor', 'postproductor'])

    # Permisos por herramienta:
    # 1. Encuesta Interna: Abierta para TODOS los colaboradores
    puede_ver_encuesta = True

    # 2. Autorización de Retransmisión: Exclusivo Ingeniería y Gerencia (o Admin)
    puede_ver_retransmision = es_admin or es_ingenieria or es_gerencia

    # 3. Motor de Renderizado GPU: Exclusivo Edición / Postproducción (o Admin).
    # Ingeniería (no admin) NO puede ver las herramientas de otras áreas como Edición.
    puede_ver_render = es_admin or es_edicion

    conteo_visibles = sum([puede_ver_encuesta, puede_ver_retransmision, puede_ver_render])
    
    # Conteo de solicitudes listas para firma de Gerencia
    solicitudes_pendientes_firma = 0
    if es_gerencia or es_admin:
        try:
            solicitudes_pendientes_firma = sum(1 for s in get_all_retransmission_authorizations() if s.get('status') == 'filtro1_aprobado')
        except Exception:
            solicitudes_pendientes_firma = 0

    # Estado de la encuesta para el usuario actual
    survey = get_active_survey('teleamiga_interna_2026')
    user_response = get_user_survey_response(survey['id'], user_info['id']) if survey else None
    
    if user_response and user_response.get('is_draft') == 0:
        survey_status = 'COMPLETADA'
        survey_date = user_response.get('submitted_at', '')
    elif user_response and user_response.get('is_draft') == 1:
        survey_status = 'BORRADOR'
        survey_date = user_response.get('submitted_at', '')
    else:
        survey_status = 'PENDIENTE'
        survey_date = ''

    with ui.column().classes('w-full min-h-[calc(100vh-65px)] bg-slate-50 text-slate-800 p-4 sm:p-6 md:p-8 lg:p-10'):
        with ui.column().classes('w-full max-w-6xl mx-auto gap-6 sm:gap-8'):
            
            # --- BANNER DE NOTIFICACIÓN PRIORITARIA (SI LA ENCUESTA ESTÁ PENDIENTE) ---
            if survey_status == 'PENDIENTE':
                with ui.card().classes('w-full bg-gradient-to-r from-rose-500 to-indigo-600 text-white p-4 sm:p-5 rounded-3xl shadow-lg flex flex-row items-center justify-between gap-4 flex-wrap'):
                    with ui.row().classes('items-center gap-3.5'):
                        with ui.element('div').classes('w-10 h-10 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white shrink-0'):
                            ui.icon('campaign', size='sm')
                        with ui.column().classes('gap-0'):
                            ui.label('¡Acción requerida para todos los colaboradores!').classes('text-xs font-black tracking-wide uppercase text-rose-100')
                            ui.label('Encuesta Interna: Construyamos la nueva Teleamiga').classes('text-base sm:text-lg font-black')
                            ui.label('Tu opinión y creatividad son claves en la revisión de la programación del canal.').classes('text-xs text-white/80')
                    
                    ui.button('Responder Encuesta Ahora', icon='edit_note', on_click=lambda: ui.navigate.to('/herramientas/encuesta'))\
                        .classes('bg-white text-slate-900 hover:bg-slate-100 font-extrabold text-xs sm:text-sm px-5 py-2.5 rounded-xl shadow-md transition-all')

            # --- ENCABEZADO HERO ---
            with ui.column().classes('w-full gap-3 border-b border-slate-200 pb-5 sm:pb-6'):
                with ui.row().classes('items-start sm:items-center justify-between w-full flex-col sm:flex-row gap-4'):
                    with ui.row().classes('items-center gap-3 sm:gap-4'):
                        with ui.element('div').classes('w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-200 shrink-0'):
                            ui.icon('apps', size='md').classes('text-white')
                        with ui.column().classes('gap-0.5'):
                            ui.label('Tienda de Herramientas & Apps').classes('text-2xl sm:text-3xl font-black tracking-tight text-slate-900')
                            ui.label('Ecosistema de módulos institucionales, encuestas e inteligencia documental de MediaHub').classes('text-slate-500 text-xs sm:text-sm')
                    
                    with ui.row().classes('items-center gap-2 flex-wrap'):
                        if es_admin:
                            ui.badge('SUPERADMINISTRADOR').props('color=purple-1 text-color=purple-9').classes('text-xs font-bold px-3 py-1.5 border border-purple-300')
                        else:
                            ui.badge(user_info.get('area', 'COLABORADOR').upper()).props('color=blue-1 text-color=blue-9').classes('text-xs font-bold px-3 py-1.5 border border-blue-200')
                        if es_admin:
                            ui.badge('ACCESO TOTAL').props('color=indigo-1 text-color=indigo-9').classes('text-xs font-bold px-3 py-1.5 border border-indigo-200')

            # Sección de herramientas disponibles
            with ui.row().classes('items-center justify-between w-full'):
                ui.label('HERRAMIENTAS OPERATIVAS DISPONIBLES').classes('text-xs font-black tracking-widest text-indigo-600 uppercase')
                ui.badge(f'{conteo_visibles} MÓDULO{"S" if conteo_visibles != 1 else ""} DISPONIBLE{"S" if conteo_visibles != 1 else ""}').props('outline color=slate-400 text-color=slate-600').classes('text-[11px]')
            
            # Grid Responsivo
            with ui.grid().classes('grid grid-cols-1 lg:grid-cols-3 gap-6 w-full items-start'):
                
                # ==============================================================================
                # HERRAMIENTA 1: ENCUESTA INTERNA TELEAMIGA (PARA TODOS LOS USUARIOS)
                # ==============================================================================
                if puede_ver_encuesta:
                    with ui.card().classes('col-span-1 lg:col-span-2 bg-white border-2 border-indigo-200 hover:border-indigo-500 p-6 sm:p-8 rounded-3xl flex flex-col justify-between transition-all duration-300 shadow-sm hover:shadow-xl hover:shadow-indigo-100 group cursor-pointer')\
                         .on('click', lambda: ui.navigate.to('/herramientas/encuesta')):
                        
                        with ui.column().classes('w-full gap-5'):
                            with ui.row().classes('w-full items-start justify-between gap-3 flex-wrap'):
                                with ui.row().classes('items-center gap-3'):
                                    with ui.element('div').classes('w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center group-hover:scale-105 group-hover:bg-blue-600 transition-all duration-300 shrink-0'):
                                        ui.icon('quiz', size='md').classes('text-blue-600 group-hover:text-white transition-colors')
                                    with ui.column().classes('gap-0.5'):
                                        ui.label('Encuesta Interna: Nueva Teleamiga').classes('text-xl sm:text-2xl font-black text-slate-900 group-hover:text-blue-600 transition-colors')
                                        ui.label('Construyamos la nueva Teleamiga • 28 Preguntas').classes('text-xs font-semibold text-slate-400')
                                
                                # Badge de estado de la encuesta
                                with ui.row().classes('items-center gap-2'):
                                    if survey_status == 'COMPLETADA':
                                        with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-700 text-xs font-bold'):
                                            ui.icon('check_circle', size='xs').classes('text-emerald-600')
                                            ui.label('COMPLETADA')
                                    elif survey_status == 'BORRADOR':
                                        with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 border border-amber-300 text-amber-800 text-xs font-bold'):
                                            ui.icon('edit', size='xs').classes('text-amber-600')
                                            ui.label('BORRADOR EN CURSO')
                                    else:
                                        with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 border border-rose-300 text-rose-700 text-xs font-bold animate-pulse'):
                                            ui.icon('pending_actions', size='xs').classes('text-rose-600')
                                            ui.label('PENDIENTE POR RESPONDER')

                            ui.label('Herramienta de consulta y participación abierta para todos los colaboradores de Teleamiga. Evalúa fortalezas, audiencias, temáticas prioritarias, formatos por franja y propón ideas innovadoras para la nueva parrilla de programación.')\
                                .classes('text-slate-600 text-sm leading-relaxed')

                            # Etiquetas de características
                            with ui.row().classes('gap-2 flex-wrap pt-1'):
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('groups', size='xs').classes('text-blue-500')
                                    ui.label('Para Todos los Roles')
                                Carpeta_preg = ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1')
                                with Carpeta_preg:
                                    ui.icon('format_list_numbered', size='xs').classes('text-indigo-500')
                                    ui.label('28 Preguntas Clave')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('save', size='xs').classes('text-emerald-500')
                                    ui.label('Guardado de Borrador')

                        # Botones de acción
                        with ui.row().classes('w-full pt-5 border-t border-slate-100 justify-between items-center mt-5 flex-wrap gap-3'):
                            with ui.row().classes('items-center gap-2 text-slate-500 text-xs'):
                                ui.icon('public', size='xs')
                                ui.label('Acceso habilitado para todo el personal').classes('font-medium')
                            
                            with ui.row().classes('items-center gap-2'):
                                if es_admin or es_ingenieria or es_gerencia:
                                    ui.button('Métricas & Resultados', icon='insights', on_click=lambda: ui.navigate.to('/herramientas/encuesta/resultados'))\
                                        .classes('bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-4 py-2 rounded-xl text-xs transition-all')

                                btn_text = 'Ver mis Respuestas' if survey_status == 'COMPLETADA' else ('Continuar Encuesta' if survey_status == 'BORRADOR' else 'Comenzar Encuesta')
                                btn_icon = 'visibility' if survey_status == 'COMPLETADA' else 'edit_note'
                                ui.button(btn_text, icon=btn_icon, on_click=lambda: ui.navigate.to('/herramientas/encuesta'))\
                                    .classes('bg-blue-600 hover:bg-blue-700 text-white font-bold px-5 py-2 rounded-xl shadow-sm text-xs sm:text-sm transition-all')

                # ==============================================================================
                # PANEL LATERAL COMPLEMENTARIO (INFORMACIÓN DE LA SUITE)
                # ==============================================================================
                with ui.card().classes('col-span-1 bg-gradient-to-br from-slate-50 to-indigo-50/40 border border-slate-200/80 p-6 sm:p-7 rounded-3xl flex flex-col justify-between gap-6 shadow-sm'):
                    with ui.column().classes('gap-4'):
                        with ui.row().classes('items-center gap-3'):
                            with ui.element('div').classes('w-10 h-10 rounded-xl bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 shrink-0'):
                                ui.icon('tips_and_updates', size='sm')
                            ui.label('Ecosistema MediaHub').classes('font-bold text-slate-900 text-base')
                        
                        ui.label('La suite de herramientas permite digitalizar trámites técnicos, encuestas corporativas y flujos documentales del canal.')\
                            .classes('text-slate-600 text-xs leading-relaxed')

                        with ui.column().classes('gap-2 p-3 bg-white/70 rounded-2xl border border-indigo-100/60'):
                            ui.label('💡 ¿Por qué es importante tu aporte?').classes('text-xs font-bold text-indigo-900')
                            ui.label('Cada departamento aporta una perspectiva única: la cercanía de Producción, la visión de Programación, el soporte de Ingeniería y la estrategia de Gerencia.').classes('text-[11px] text-slate-500 leading-tight')

                    with ui.row().classes('w-full pt-4 border-t border-slate-200/60 items-center justify-between'):
                        ui.label('MediaHub Suite v2.6').classes('text-[11px] font-semibold text-slate-400')
                        ui.badge('TELEAMIGA').props('outline color=indigo-4 text-color=indigo-7').classes('text-[10px]')

                # ==============================================================================
                # HERRAMIENTA 2: AUTORIZACIÓN DE RETRANSMISIÓN (INGENIERÍA & GERENCIA O ADMIN)
                # ==============================================================================
                if puede_ver_retransmision:
                    with ui.card().classes('col-span-1 lg:col-span-2 bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-xl hover:shadow-indigo-100 group cursor-pointer p-6 sm:p-8 rounded-3xl flex flex-col justify-between transition-all duration-300 shadow-sm'):
                        with ui.column().classes('w-full gap-5'):
                            with ui.row().classes('w-full items-start justify-between gap-3 flex-wrap'):
                                with ui.row().classes('items-center gap-3'):
                                    with ui.element('div').classes('w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0'):
                                        ui.icon('cast_connected', size='md').classes('text-indigo-600')
                                    with ui.column().classes('gap-0.5'):
                                        ui.label('Autorización de Retransmisión').classes('text-xl sm:text-2xl font-black text-slate-900')
                                        ui.label('MINTIC RTI & Operadores Cable/Comunitarios').classes('text-xs font-semibold text-slate-400')
                                
                                with ui.row().classes('items-center gap-2'):
                                    if solicitudes_pendientes_firma > 0:
                                        with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-100 border border-amber-300 text-amber-900 text-xs font-black shadow-xs animate-pulse'):
                                            ui.icon('notifications_active', size='xs').classes('text-amber-700')
                                            ui.label(f'{solicitudes_pendientes_firma} PENDIENTE{"S" if solicitudes_pendientes_firma > 1 else ""} DE FIRMA')
                                    
                                    with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold'):
                                        with ui.element('span').classes('w-2 h-2 rounded-full bg-emerald-500 animate-pulse'):
                                            pass
                                        ui.label('V1.0 • ACTIVA')

                            ui.label('Automatización integral de radicación de operadores. Extracción inteligente OCR de certificados RTI MINTIC, Cámara de Comercio y Cédula, validación de coincidencias legales y generación de actas con firma digital de Gerencia.')\
                                .classes('text-slate-600 text-sm leading-relaxed')

                            # Etiquetas de características
                            with ui.row().classes('gap-2 flex-wrap pt-1'):
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('document_scanner', size='xs').classes('text-indigo-500')
                                    ui.label('OCR Automático')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('compare_arrows', size='xs').classes('text-purple-500')
                                    ui.label('Cruce RTI-Cámara')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('draw', size='xs').classes('text-emerald-500')
                                    ui.label('Firma Digital')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('picture_as_pdf', size='xs').classes('text-rose-500')
                                    ui.label('Acta Oficial Carta')

                        with ui.row().classes('w-full pt-5 border-t border-slate-100 justify-between items-center mt-5 flex-wrap gap-3'):
                            with ui.row().classes('items-center gap-2 text-slate-400 text-xs'):
                                ui.icon('shield', size='xs').classes('text-slate-400')
                                ui.label('Exclusivo: Ingeniería & Gerencia').classes('font-medium')
                            
                            ui.button('Abrir Módulo', icon='arrow_forward', on_click=lambda: ui.navigate.to('/herramientas/retransmision'))\
                                .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-5 py-2.5 rounded-xl shadow-sm text-sm transition-all')

                # ==============================================================================
                # HERRAMIENTA 3: MOTOR DE RENDERIZADO GPU (EDICIÓN / POSTPRODUCCIÓN O ADMIN)
                # ==============================================================================
                if puede_ver_render:
                    with ui.card().classes('col-span-1 lg:col-span-2 bg-white border border-slate-200 hover:border-violet-400 hover:shadow-xl hover:shadow-violet-100 group cursor-pointer p-6 sm:p-8 rounded-3xl flex flex-col justify-between transition-all duration-300 shadow-sm'):
                        with ui.column().classes('w-full gap-5'):
                            with ui.row().classes('w-full items-start justify-between gap-3 flex-wrap'):
                                with ui.row().classes('items-center gap-3'):
                                    with ui.element('div').classes('w-14 h-14 rounded-2xl bg-violet-50 border border-violet-100 flex items-center justify-center shrink-0'):
                                        ui.icon('speed', size='md').classes('text-violet-600')
                                    with ui.column().classes('gap-0.5'):
                                        ui.label('Motor de Renderizado GPU').classes('text-xl sm:text-2xl font-black text-slate-900')
                                        ui.label('NVIDIA NVENC • Sincronización de Mosca y Cierre').classes('text-xs font-semibold text-slate-400')
                                
                                with ui.row().classes('items-center gap-2'):
                                    with ui.element('div').classes('flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-50 border border-violet-200 text-violet-700 text-xs font-bold'):
                                        with ui.element('span').classes('w-2 h-2 rounded-full bg-violet-500 animate-pulse'):
                                            pass
                                        ui.label('V1.0 • ACTIVA')

                            ui.label('Renderizado asíncrono automatizado de videos acelerado por hardware en estaciones de edición con NVIDIA Quadro P2000. Incorpora alineación matemática exacta de mosca en bucle con remate al último frame y concatenación de cortinilla de cierre.')\
                                .classes('text-slate-600 text-sm leading-relaxed')

                            # Etiquetas de características
                            with ui.row().classes('gap-2 flex-wrap pt-1'):
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('bolt', size='xs').classes('text-violet-500')
                                    ui.label('NVIDIA NVENC')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('auto_awesome', size='xs').classes('text-amber-500')
                                    ui.label('Alineación de Cola')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('video_settings', size='xs').classes('text-indigo-500')
                                    ui.label('Concat Normalizado')
                                with ui.element('span').classes('bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium px-3 py-1 rounded-lg flex items-center gap-1'):
                                    ui.icon('desktop_windows', size='xs').classes('text-emerald-500')
                                    ui.label('Cliente Local')

                        with ui.row().classes('w-full pt-5 border-t border-slate-100 justify-between items-center mt-5 flex-wrap gap-3'):
                            with ui.row().classes('items-center gap-2 text-slate-400 text-xs'):
                                ui.icon('lock', size='xs').classes('text-slate-400')
                                ui.label('Exclusivo: Edición & Sistemas').classes('font-medium')
                            
                            with ui.row().classes('items-center gap-2'):
                                ui.button('Descargar Cliente (.zip)', icon='download', on_click=lambda: ui.download('/descargar-cliente-edicion'))\
                                    .classes('bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-4 py-2.5 rounded-xl text-xs transition-all')
                                ui.button('Abrir Módulo', icon='arrow_forward', on_click=lambda: ui.navigate.to('/herramientas/render-edicion'))\
                                    .classes('bg-violet-600 hover:bg-violet-700 text-white font-semibold px-5 py-2.5 rounded-xl shadow-sm text-sm transition-all')

                # ==============================================================================
                # PANEL 3: PRÓXIMAS HERRAMIENTAS EN PREPARACIÓN
                # ==============================================================================
                with ui.card().classes('col-span-1 bg-white border border-slate-200/80 p-6 rounded-3xl flex flex-col justify-between gap-4 shadow-sm'):
                    with ui.column().classes('gap-3'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('hourglass_top', size='sm').classes('text-amber-500')
                            ui.label('Próximas Herramientas').classes('font-bold text-slate-900 text-sm uppercase tracking-wide')
                        
                        ui.label('Módulos en diseño para las demás áreas operativas del canal:').classes('text-slate-500 text-xs')

                        with ui.column().classes('gap-2 w-full pt-1'):
                            with ui.row().classes('items-center gap-2.5 p-2 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-700'):
                                ui.icon('campaign', size='xs').classes('text-amber-600')
                                with ui.column().classes('gap-0'):
                                    ui.label('Gestión de Pauta y Clientes').classes('font-bold')
                                    ui.label('Seguimiento comercial y emisión').classes('text-[10px] text-slate-400')

                            with ui.row().classes('items-center gap-2.5 p-2 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-700'):
                                ui.icon('movie', size='xs').classes('text-purple-600')
                                with ui.column().classes('gap-0'):
                                    ui.label('Control de Rodajes y Locaciones').classes('font-bold')
                                    ui.label('Producción de campo y recursos').classes('text-[10px] text-slate-400')

                    ui.label('Desarrollado por Sistemas Teleamiga').classes('text-[10px] text-slate-400 text-center font-medium pt-2 border-t border-slate-100')
