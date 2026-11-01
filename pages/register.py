import os
from nicegui import ui
from database import register_user

def obtener_texto_eula():
    """Lee el contenido del archivo eula.md dinámicamente."""
    try:
        # Busca el archivo eula.md en la raíz del proyecto (subiendo un nivel desde /pages)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ruta_eula = os.path.join(base_dir, 'eula.md')
        
        with open(ruta_eula, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return "**Error:** El archivo de términos y condiciones (eula.md) no se encontró en el servidor."

def register_page():
    
    # ==========================================
    # 1. EL POP-UP FLOTANTE DEL EULA (Diálogo)
    # ==========================================
    with ui.dialog() as eula_dialog, ui.card().classes('w-full max-w-2xl max-h-[85vh] overflow-y-auto p-8'):
        ui.label('CONTRATO DE LICENCIA DE USUARIO FINAL (EULA) – MEDIAHUB').classes('text-xl font-black mb-2 text-center text-gray-800')
        
        # Leemos el archivo externo y lo dibujamos
        texto_legal = obtener_texto_eula()
        ui.markdown(texto_legal).classes('text-sm text-gray-700 text-justify')
        
        ui.button('Entendido y Cerrar', on_click=eula_dialog.close).classes('w-full mt-6 bg-blue-600 text-white font-bold shadow-md')


    # ==========================================
    # 2. PANTALLA PRINCIPAL DE REGISTRO
    # ==========================================
    with ui.column().classes('w-full min-h-screen items-center justify-center bg-gray-50 p-4'):
        with ui.card().classes('w-full max-w-md p-8 shadow-xl rounded-2xl bg-white'):
            ui.label('Registro MediaHub').classes('text-2xl font-bold mb-6 text-center text-gray-800')
            
            nombres = ui.input('Nombres').classes('w-full mb-2')
            apellidos = ui.input('Apellidos').classes('w-full mb-2')
            cargo = ui.input('Cargo').classes('w-full mb-2')
            area = ui.input('Área encargada').classes('w-full mb-2')
            celular = ui.input('Celular').classes('w-full mb-2')
            correo = ui.input('Correo Electrónico').classes('w-full mb-2')
            password = ui.input('Contraseña', password=True, password_toggle_button=True).classes('w-full mb-2')
            
            # --- SECCIÓN DEL CHECKBOX Y LINK DEL EULA ---
            with ui.row().classes('w-full items-center justify-start gap-1 mb-6 mt-4 flex-nowrap'):
                acepta_eula = ui.checkbox()
                ui.label('He leído y acepto el').classes('text-sm text-gray-600')
                ui.label('Acuerdo EULA').classes('text-sm text-blue-600 font-bold cursor-pointer hover:underline').on('click', eula_dialog.open)
            
            def handle_register():
                if not all([nombres.value, apellidos.value, cargo.value, area.value, celular.value, correo.value, password.value]):
                    ui.notify('Por favor, rellena todos los campos', type='warning')
                    return
                
                if not acepta_eula.value:
                    ui.notify('Es obligatorio aceptar el Acuerdo EULA para registrarse.', type='negative', icon='gavel')
                    return
                
                success, message = register_user(
                    nombres.value, apellidos.value, cargo.value, 
                    area.value, celular.value, correo.value, password.value
                )
                
                if success:
                    ui.notify(message, type='positive')
                    ui.navigate.to('/login')
                else:
                    ui.notify(message, type='negative')

            ui.button('Registrarse', on_click=handle_register) \
                .classes('w-full mb-4 bg-green-600 text-white font-bold rounded-lg shadow-md py-2')
            
            with ui.row().classes('w-full justify-center text-sm mt-2'):
                ui.label('¿Ya tienes cuenta?').classes('text-gray-600')
                ui.link('Inicia Sesión aquí', '/login').classes('text-blue-500 font-semibold')