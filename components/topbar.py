from nicegui import ui, app
from database import get_pending_surveys_for_user, get_pending_delivery_acts_for_user, get_active_transition_alerts

def topbar(user_info, drawer=None):
    user_id = user_info.get('id', 0)
    user_area = user_info.get('area', '')
    pending_surveys = []
    pending_acts = []
    transition_alerts = []
    if user_id:
        try:
            pending_surveys = get_pending_surveys_for_user(user_id)
        except Exception:
            pending_surveys = []
        try:
            pending_acts = get_pending_delivery_acts_for_user(user_info)
        except Exception:
            pending_acts = []
        try:
            transition_alerts = get_active_transition_alerts(user_area)
        except Exception:
            transition_alerts = []
            
    total_pendientes = len(pending_surveys) + len(pending_acts) + len(transition_alerts)
    has_pending = total_pendientes > 0

    with ui.header().classes('bg-white text-gray-800 shadow-md justify-between items-center px-3 sm:px-6 py-2.5 z-50'):
        with ui.row().classes('items-center gap-2 sm:gap-3'):
            if drawer:
                ui.button(icon='menu', on_click=lambda: drawer.toggle())\
                    .props('flat round dense')\
                    .classes('text-slate-600 lg:hidden')

            with ui.row().classes('items-center gap-2 cursor-pointer').on('click', lambda: ui.navigate.to('/')):
                with ui.element('div').classes('w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white font-black shadow-sm'):
                    ui.label('M')
                ui.label('MediaHub').classes('text-xl font-extrabold text-slate-900 tracking-tight')
            
            # Badge de versión o canal
            ui.badge('TELEAMIGA').props('outline color=blue-6 text-color=blue-8').classes('text-[10px] hidden sm:flex')

        with ui.row().classes('items-center gap-2 sm:gap-4'):
            
            # BOTÓN INSTALAR PWA DIRECTO
            btn_install = ui.button('Instalar App', icon='download_for_offline')\
                .props('flat dense size=sm')\
                .classes('bg-blue-50 text-blue-700 hover:bg-blue-100 font-bold px-2.5 py-1 rounded-lg text-xs transition-all hidden sm:flex')\
                .tooltip('Instalar MediaHub como aplicación de escritorio o móvil')
            btn_install.on('click', js_handler='''() => {
                if (window.deferredPWAInstallPrompt) {
                    window.deferredPWAInstallPrompt.prompt();
                    window.deferredPWAInstallPrompt = null;
                } else {
                    alert('Para instalar MediaHub en tu equipo:\\n\\n• En Chrome o Edge: Haz clic en el icono de instalación (pantalla con flecha) en la barra de direcciones superior, o en Menú (⋮) -> "Instalar MediaHub".\\n• En Android: Menú (⋮) -> "Instalar aplicación".\\n• En iPhone: Compartir -> "Agregar a pantalla de inicio".');
                }
            }''')
            
            # -------------------------------------------------------------
            # CAMPANA DE NOTIFICACIONES (INTERACTIVA)
            # -------------------------------------------------------------
            with ui.element('div').classes('relative'):
                btn_bell = ui.button(icon='notifications', color='slate-700')\
                    .props('flat round dense')\
                    .classes('text-slate-600 hover:text-blue-600 transition-colors')
                
                if has_pending:
                    # Badge animado de alerta
                    ui.badge(str(total_pendientes), color='rose-600')\
                        .props('floating rounded')\
                        .classes('animate-pulse font-bold text-[10px]')
                
                with ui.menu().classes('w-80 sm:w-96 p-0 rounded-2xl shadow-2xl border border-slate-200 overflow-hidden'):
                    # Encabezado del menú
                    with ui.row().classes('w-full bg-slate-900 text-white p-3.5 items-center justify-between'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('notifications_active', size='sm').classes('text-amber-400')
                            ui.label('Centro de Notificaciones').classes('font-bold text-sm')
                        if has_pending:
                            ui.badge(f"{total_pendientes} Pendiente(s)").props('color=rose-500 text-color=white').classes('text-[10px]')
                        else:
                            ui.badge('Al día').props('color=emerald-500 text-color=white').classes('text-[10px]')

                    # Lista de notificaciones
                    if has_pending:
                        with ui.column().classes('p-3 gap-2 bg-slate-50 max-h-96 overflow-y-auto'):
                            # 1. Actas de Entrega de Equipos Pendientes
                            for act in pending_acts:
                                with ui.card().classes('w-full p-3 bg-white border border-indigo-200 rounded-xl shadow-xs gap-2'):
                                    with ui.row().classes('items-start justify-between w-full'):
                                        with ui.row().classes('items-center gap-2'):
                                            with ui.element('div').classes('w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0'):
                                                ui.icon('assignment_turned_in', size='xs')
                                            ui.label('Acta de Entrega de Equipo').classes('text-xs font-black text-indigo-800')
                                        ui.badge('Firma Pendiente').props('outline color=indigo-6').classes('text-[9px]')

                                    ui.label(act.get('equipo_nombre', 'Equipo Asignado')).classes('text-xs font-bold text-slate-800 leading-snug')
                                    ui.label(f"Código: {act['code']} • Responsable: {act['receptor_nombre']}").classes('text-[11px] text-slate-500 leading-tight')

                                    with ui.row().classes('w-full justify-end pt-1'):
                                        ui.button('Revisar y Firmar Acta', icon='draw', on_click=lambda c=act['code']: ui.navigate.to(f"/acta_entrega/{c}"))\
                                            .classes('bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-3 py-1 rounded-lg shadow-xs')

                            # 2. Encuestas Internas Pendientes
                            for s in pending_surveys:
                                with ui.card().classes('w-full p-3 bg-white border border-rose-200 rounded-xl shadow-xs gap-2'):
                                    with ui.row().classes('items-start justify-between w-full'):
                                        with ui.row().classes('items-center gap-2'):
                                            with ui.element('div').classes('w-7 h-7 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center shrink-0'):
                                                ui.icon('quiz', size='xs')
                                            ui.label('Nueva Encuesta Asignada').classes('text-xs font-black text-rose-700')
                                        ui.badge('Prioritaria').props('outline color=rose-6').classes('text-[9px]')

                                    ui.label(s.get('title', 'Encuesta Interna Teleamiga')).classes('text-xs font-bold text-slate-800 leading-snug')
                                    ui.label('Participa en la revisión de programación de Teleamiga. Tu opinión y creatividad son fundamentales.').classes('text-[11px] text-slate-500 leading-tight')

                                    with ui.row().classes('w-full justify-end pt-1'):
                                        ui.button('Responder Encuesta', icon='edit_note', on_click=lambda: ui.navigate.to('/herramientas/encuesta'))\
                                            .classes('bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1 rounded-lg shadow-xs')

                            # 3. Alertas de Traslado Técnico y Ajuste en Parrilla
                            for alert in transition_alerts:
                                with ui.card().classes('w-full p-3 bg-amber-50/50 border border-amber-300 rounded-xl shadow-xs gap-2'):
                                    with ui.row().classes('items-start justify-between w-full'):
                                        with ui.row().classes('items-center gap-2'):
                                            with ui.element('div').classes('w-7 h-7 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center shrink-0'):
                                                ui.icon('transfer_within_a_station', size='xs')
                                            ui.label('Alerta de Traslado Técnico').classes('text-xs font-black text-amber-950')
                                        ui.badge(f"Ajuste Parrilla: {alert.get('ajuste_sugerido', 3)}m").props('color=amber-7 text-color=white').classes('text-[9px] font-bold')

                                    ui.label(f"{alert['persona']} ({alert.get('rol_a', 'Técnico')})").classes('text-xs font-bold text-slate-800 leading-snug')
                                    ev_a_nom = alert.get('evento_a', {}).get('nombre') or alert.get('evento_a', {}).get('nombre_programa', 'Programa 1')
                                    ev_b_nom = alert.get('evento_b', {}).get('nombre') or alert.get('evento_b', {}).get('nombre_programa', 'Programa 2')
                                    h_fin_a = alert.get('evento_a', {}).get('hora_fin', '')
                                    h_ini_b = alert.get('evento_b', {}).get('hora_inicio', '')
                                    ui.label(f"{ev_a_nom} ({alert.get('locacion_a', 'Estudio')}, fin {h_fin_a}) ➔ {ev_b_nom} ({alert.get('locacion_b', 'Estudio')}, ini {h_ini_b})").classes('text-[11px] text-slate-600 leading-tight')
                                    ui.label(f"Margen real: {alert['margen']} min • Requerido: {alert['requerido']} min").classes('text-[10px] font-mono font-bold text-amber-800')

                                    def ir_a_parrilla(fecha_target=alert['fecha']):
                                        app.storage.user['target_date'] = fecha_target
                                        ui.navigate.to('/')

                                    with ui.row().classes('w-full justify-end pt-1'):
                                        ui.button('Ver en Parrilla del Día', icon='calendar_month', on_click=ir_a_parrilla)\
                                            .classes('bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold px-3 py-1 rounded-lg shadow-xs')
                    else:
                        with ui.column().classes('p-6 items-center justify-center text-center gap-2'):
                            ui.icon('check_circle', size='md').classes('text-emerald-500')
                            ui.label('¡Estás al día!').classes('font-bold text-slate-800 text-sm')
                            ui.label('No tienes actas ni trámites pendientes por firmar en este momento.').classes('text-xs text-slate-500 max-w-[240px]')

                    # Pie de menú
                    with ui.row().classes('w-full p-2 bg-slate-100 border-t border-slate-200 justify-center'):
                        ui.button('Ver todas las herramientas', icon='apps', on_click=lambda: ui.navigate.to('/herramientas'))\
                            .props('flat dense size=sm')\
                            .classes('text-xs text-slate-600 font-semibold hover:text-blue-600')

            # Información de texto del usuario
            es_admin_top = user_info.get('es_admin', False) or user_info.get('usuario', '').lower() == 'jose'
            with ui.column().classes('items-end leading-tight'):
                with ui.row().classes('items-center gap-1.5'):
                    if es_admin_top:
                        with ui.element('span').classes('bg-amber-100 text-amber-900 border border-amber-300 text-[9px] font-black px-1.5 py-0.5 rounded-full flex items-center gap-0.5 shadow-xs'):
                            ui.icon('verified_user', size='10px').classes('text-amber-600')
                            ui.label('ADMIN')
                    ui.label(f"{user_info['nombres']} {user_info['apellidos']}").classes('font-bold text-xs sm:text-sm text-slate-800')
                ui.label(f"{user_info.get('cargo', 'Colaborador')} • {user_info.get('area', '')}").classes('text-[11px] text-slate-400')
            
            # Círculo con iniciales y Menú
            avatar_border = 'ring-2 ring-amber-400' if es_admin_top else ''
            with ui.avatar(color='blue').classes(f'cursor-pointer text-white font-bold text-xs shadow-sm {avatar_border}'):
                ui.label(user_info['iniciales'])
                with ui.menu().classes('rounded-xl shadow-lg border border-slate-100') as menu:
                    with ui.row().classes('px-4 py-2 bg-slate-50 items-center justify-between gap-3 border-b border-slate-100'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('person', size='xs').classes('text-slate-400')
                            ui.label(user_info.get('usuario', '')).classes('text-xs font-bold text-slate-700')
                        if es_admin_top:
                            ui.badge('ADMIN GENERAL', color='amber-8 text-white').classes('text-[9px] font-black')
                    ui.menu_item('Mis Herramientas', lambda: ui.navigate.to('/herramientas'))
                    ui.menu_item('Encuesta Teleamiga', lambda: ui.navigate.to('/herramientas/encuesta'))
                    ui.menu_item('📥 Instalar MediaHub (PWA)').on('click', js_handler='''() => {
                        if (window.deferredPWAInstallPrompt) {
                            window.deferredPWAInstallPrompt.prompt();
                            window.deferredPWAInstallPrompt = null;
                        } else {
                            alert('Para instalar MediaHub en tu equipo:\\n\\n• En Chrome o Edge: Clic en el icono de instalación en la barra de direcciones superior o Menú (⋮) -> Instalar MediaHub.\\n• En Android: Menú (⋮) -> Instalar aplicación.\\n• En iPhone: Compartir -> Agregar a pantalla de inicio.');
                        }
                    }''')
                    ui.separator()
                    ui.menu_item('Cerrar Sesión', lambda: ui.navigate.to('/login'))