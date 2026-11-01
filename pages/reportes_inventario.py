from nicegui import ui, app
from components.topbar import topbar
from components.sidebar import sidebar
from database import get_user_by_usuario
from components.custom_report_builder import render_custom_report_module

def reportes_inventario_page(module_id: str, initial_record_id: str = None):
    """Renderiza el lienzo de página para el maquetador y visor A4 del reporte de inventario."""
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

    # Renderizar topbar y sidebar
    topbar(user_info)
    sidebar(user_info)
    
    # Contenedores para el lienzo central y el panel de configuración
    with ui.row().classes('w-full h-[calc(100vh-65px)] flex flex-row flex-nowrap overflow-hidden m-0 p-0 bg-gray-200'):
        
        # Centro: Vista previa del papel A4 / Carta
        report_main = ui.column().classes('flex-grow min-w-0 h-full m-0 p-0 overflow-hidden items-center justify-start flex-nowrap')
        
        # Derecha: El Maquetador
        report_right = ui.column().classes('w-[380px] shrink-0 h-full bg-white border-l border-gray-200 p-0 flex flex-col shadow-2xl z-10 overflow-hidden')
        
        # Iniciar el renderizador
        render_custom_report_module(report_main, report_right, user_info, module_id, initial_record_id=initial_record_id)
