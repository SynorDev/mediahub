from nicegui import ui, app  # <-- Añadimos 'app' aquí
from database import verify_user, extraer_primer_nombre  # <-- Importamos la función aquí arriba

def login_page():
    with ui.column().classes('w-full h-screen items-center justify-center bg-gray-50 p-4'):
        with ui.card().classes('w-full max-w-sm p-8 shadow-xl rounded-2xl bg-white'):
            ui.label('MediaHub').classes('text-3xl font-bold mb-8 text-center text-blue-600')
            
            # Etiqueta actualizada para guiar al usuario
            primer_nombre = ui.input('Tu Primer Nombre (Ej: Jose)').classes('w-full mb-4')
            password = ui.input('Contraseña', password=True, password_toggle_button=True).classes('w-full mb-6')
            
            def handle_login():
                if not primer_nombre.value or not password.value:
                    ui.notify('Por favor, ingresa tus credenciales', type='warning')
                    return
                
                # Pasamos solo el primer nombre a la validación
                if verify_user(primer_nombre.value, password.value):
                    # Guardamos el usuario en la sesión usando 'app'
                    app.storage.user['username'] = extraer_primer_nombre(primer_nombre.value)
                    
                    ui.notify('¡Inicio de sesión correcto!', type='positive')
                    ui.navigate.to('/')
                else:
                    ui.notify('Nombre o contraseña incorrectos', type='negative')

            ui.button('Iniciar Sesión', on_click=handle_login) \
                .classes('w-full mb-4 bg-blue-600 text-white rounded-lg shadow-md py-2')
            
            with ui.row().classes('w-full justify-center text-sm mt-4'):
                ui.label('¿No tienes cuenta?').classes('text-gray-600')
                ui.link('Regístrate aquí', '/register').classes('text-blue-600 font-semibold')