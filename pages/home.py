from nicegui import ui, app
from components.topbar import topbar
from components.sidebar import sidebar
from components.calendar_view import CalendarView
from database import get_user_by_usuario
from components.report_builder import render_report_module

# ==============================================================
# VISTA 1: EL CALENDARIO (Ruta Principal '/')
# ==============================================================
def home_page():
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

    # Dibujamos cabecera y menú con drawer responsivo
    drawer = sidebar(user_info)
    topbar(user_info, drawer=drawer)
    
    # Al llamarlo directamente en la raíz, el RightDrawer NO lanza error
    cal_view = CalendarView(user_info)
    target_date = app.storage.user.pop('target_date', None)
    if target_date:
        cal_view.navigate_to_date(target_date)


# ==============================================================
# VISTA 2: LOS REPORTES (Nueva Ruta '/reportes')
# ==============================================================
@ui.page('/reportes')
def reportes_page():
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

    # Zona 1: Cabecera y Menú Lateral (Sidebar Nativos)
    drawer = sidebar(user_info)
    topbar(user_info, drawer=drawer)
    
    # Zonas 2 y 3: Lienzo Central y Panel Derecho (Responsivo para tablets y móviles)
    with ui.row().classes('w-full min-h-[calc(100vh-65px)] flex flex-col lg:flex-row flex-nowrap lg:overflow-hidden m-0 p-0 bg-gray-200'):
        
        # Centro: El lienzo de la hoja (Ocupa todo el espacio sobrante)
        report_main = ui.column().classes('flex-grow w-full lg:w-auto h-full m-0 p-4 sm:p-8 overflow-y-auto items-center justify-start')
        
        # Derecha: El Maquetador (Panel fijo en desktop, apilado en móvil)
        report_right = ui.column().classes('w-full lg:w-[380px] shrink-0 h-auto lg:h-full bg-white border-t lg:border-t-0 lg:border-l border-gray-200 p-0 flex flex-col shadow-2xl z-10')
        
        # Le pasamos ambos contenedores a nuestro motor
        render_report_module(report_main, report_right, user_info)