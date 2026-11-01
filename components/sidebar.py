from nicegui import ui
from database import get_pending_surveys_for_user, get_pending_delivery_acts_for_user

def sidebar(user_info):
    user_id = user_info.get('id', 0)
    pending_surveys = []
    pending_acts = []
    if user_id:
        try:
            pending_surveys = get_pending_surveys_for_user(user_id)
        except Exception:
            pending_surveys = []
        try:
            pending_acts = get_pending_delivery_acts_for_user(user_info)
        except Exception:
            pending_acts = []
            
    total_pendientes = len(pending_surveys) + len(pending_acts)
    has_pending = total_pendientes > 0

    with ui.left_drawer(value=True).props('breakpoint=1024').classes('bg-slate-50 border-r border-slate-200 p-4 shadow-sm') as drawer:
        ui.label('MEDIAHUB SUITE').classes('text-[10px] font-black text-slate-400 mb-4 tracking-wider')
        
        # Botón 1: Navega a la raíz (Calendario)
        with ui.row().classes('w-full items-center gap-3 p-2.5 rounded-xl cursor-pointer hover:bg-slate-200/60 transition-colors')\
             .on('click', lambda: ui.navigate.to('/')):
            ui.icon('calendar_month').classes('text-slate-600')
            ui.label('Calendario').classes('font-semibold text-slate-800 text-sm')
            
        # BOTÓN: Reportes
        with ui.row().classes('w-full items-center gap-3 p-2.5 rounded-xl cursor-pointer hover:bg-slate-200/60 transition-colors mt-1')\
             .on('click', lambda: ui.navigate.to('/reportes')):
            ui.icon('analytics').classes('text-slate-600')
            ui.label('Reporte Diario').classes('font-semibold text-slate-800 text-sm')
            
        # BOTÓN: Herramientas & Apps
        with ui.row().classes('w-full items-center justify-between p-2.5 rounded-xl cursor-pointer hover:bg-indigo-50 hover:text-indigo-700 text-slate-800 transition-colors mt-1 group')\
             .on('click', lambda: ui.navigate.to('/herramientas')):
            with ui.row().classes('items-center gap-3'):
                ui.icon('apps').classes('text-indigo-600')
                ui.label('Herramientas').classes('font-semibold text-sm group-hover:text-indigo-700')
            if has_pending:
                ui.badge(f"{len(pending_surveys)} PENDIENTE").props('color=rose-500 text-color=white').classes('text-[9px] font-bold px-1.5 py-0.5 animate-pulse')

        # ENLACE DIRECTO A LA ENCUESTA TELEAMIGA
        with ui.row().classes('w-full items-center justify-between p-2.5 rounded-xl cursor-pointer hover:bg-blue-50 transition-colors mt-1 group border border-dashed border-blue-200 bg-blue-50/50')\
             .on('click', lambda: ui.navigate.to('/herramientas/encuesta')):
            with ui.row().classes('items-center gap-2.5'):
                ui.icon('quiz', size='xs').classes('text-blue-600')
                ui.label('Encuesta Teleamiga').classes('font-bold text-xs text-blue-900')
            if has_pending:
                ui.element('span').classes('w-2 h-2 rounded-full bg-rose-500 animate-ping')
            else:
                ui.icon('check_circle', size='xs').classes('text-emerald-500')

        # LÓGICA DE SEGURIDAD: Mostrar botón de Administración a Administradores, Sub Admins, Ingeniería o Sistemas
        area = (user_info.get('area') or user_info.get('area_encargada') or '').lower()
        cargo = (user_info.get('cargo') or '').lower()
        rol = (user_info.get('rol') or '').lower()
        es_privilegiado = user_info.get('es_admin', False) or user_info.get('es_subadmin', False) or 'admin' in rol or 'sub admin' in rol
        if es_privilegiado or 'ingenieria' in area or 'sistemas' in area or 'admin' in area or 'sistemas' in cargo:
            ui.separator().classes('my-3')
            ui.label('ADMINISTRACIÓN').classes('text-[10px] font-black text-slate-400 mb-2 tracking-wider')
            with ui.row().classes('w-full items-center gap-3 p-2.5 rounded-xl cursor-pointer bg-blue-50 text-blue-800 hover:bg-blue-100 transition-colors shadow-xs')\
                 .on('click', lambda: ui.navigate.to('/admin')):
                ui.icon('admin_panel_settings').classes('text-blue-600')
                ui.label('Catálogos y Equipo').classes('font-bold text-sm')
            
    return drawer