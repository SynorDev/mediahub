from nicegui import ui, app
import io
import csv
import asyncio
import base64
import json
from PIL import Image

from components.topbar import topbar
from components.sidebar import sidebar
from components.custom_management import render_custom_management_builder
from components.acta_template_admin import render_acta_template_admin
from components.transition_rules_admin import render_transition_rules_admin
from database import (
    get_user_by_usuario,
    get_all_users, reset_user_password, delete_user, update_user_profile, register_user,
    get_all_custom_modules, get_custom_module,
    get_admin_quick_access_modules, toggle_admin_quick_access, is_module_quick_access
)

def render_usuarios_panel():
    """Dibuja el panel completo de administración y creación de usuarios del sistema."""
    with ui.row().classes('w-full gap-8 items-start flex-col lg:flex-row flex-nowrap'):
        
        # --- FORMULARIO DE CREACIÓN DE USUARIOS ---
        with ui.column().classes('w-full lg:w-1/3 gap-4'):
            with ui.card().classes('w-full p-6 shadow-sm border border-gray-200 bg-white rounded-xl'):
                with ui.row().classes('items-center gap-2 mb-4'):
                    ui.icon('person_add', size='md').classes('text-blue-600')
                    ui.label('Crear Nuevo Usuario').classes('text-lg font-bold text-gray-800')
                
                u_nombres = ui.input('Nombres (Ej: Carlos)').classes('w-full mb-3')
                u_apellidos = ui.input('Apellidos (Ej: Gomez Perez)').classes('w-full mb-3')
                u_cargo = ui.input('Cargo (Ej: Operador de Master)').classes('w-full mb-3')
                u_area = ui.select(
                    options=['Ingenieria', 'Produccion', 'Programacion', 'Master', 'Sistemas', 'Direccion', 'Administracion', 'Realizador', 'Operaciones'],
                    value='Ingenieria',
                    label='Área de trabajo'
                ).classes('w-full mb-3')
                u_rol = ui.select(
                    options=['Colaborador', 'Sub Admin', 'Admin General'],
                    value='Colaborador',
                    label='Rol del Sistema'
                ).classes('w-full mb-3')
                u_celular = ui.input('Celular / Teléfono').classes('w-full mb-3')
                u_correo = ui.input('Correo Electrónico').classes('w-full mb-3')
                u_password = ui.input('Contraseña Inicial', password=True, password_toggle_button=True).classes('w-full mb-6')

                def guardar_usuario():
                    if not all([u_nombres.value, u_apellidos.value, u_cargo.value, u_area.value, u_celular.value, u_correo.value, u_password.value]):
                        ui.notify('Todos los campos son obligatorios', type='warning')
                        return
                    
                    success, msg = register_user(
                        u_nombres.value.strip(),
                        u_apellidos.value.strip(),
                        u_cargo.value.strip(),
                        u_area.value.strip(),
                        u_celular.value.strip(),
                        u_correo.value.strip(),
                        u_password.value.strip(),
                        rol=u_rol.value
                    )
                    
                    if success:
                        ui.notify(msg, type='positive')
                        u_nombres.value = ''
                        u_apellidos.value = ''
                        u_cargo.value = ''
                        u_rol.value = 'Colaborador'
                        u_celular.value = ''
                        u_correo.value = ''
                        u_password.value = ''
                        refrescar_listado_usuarios()
                    else:
                        ui.notify(msg, type='negative')

                ui.button('Registrar Usuario', icon='how_to_reg', on_click=guardar_usuario) \
                    .classes('w-full bg-blue-600 text-white font-bold rounded-lg shadow-md py-2')

        # --- LISTADO Y GESTIÓN DE USUARIOS ---
        with ui.column().classes('w-full lg:w-2/3 gap-4'):
            with ui.row().classes('w-full justify-between items-center bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex-wrap gap-2'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('badge', size='md').classes('text-blue-600')
                    ui.label('Usuarios Registrados en MediaHub').classes('text-lg font-bold text-gray-800')
                
                u_search = ui.input(placeholder='Buscar por nombre, usuario, área...').props('dense clearable icon=search debounce="300"').classes('w-64 text-xs')

            usuarios_container = ui.column().classes('w-full gap-3')

            def refrescar_listado_usuarios():
                usuarios_container.clear()
                todos_u = get_all_users()
                filtro = (u_search.value or '').strip().lower()

                if filtro:
                    filtrados = []
                    for u in todos_u:
                        if (filtro in u['nombre_completo'].lower() or
                            filtro in u['usuario'].lower() or
                            filtro in u['area_encargada'].lower() or
                            filtro in u['cargo'].lower() or
                            filtro in u['correo'].lower()):
                            filtrados.append(u)
                    todos_u = filtrados

                with usuarios_container:
                    if not todos_u:
                        with ui.card().classes('w-full p-8 items-center justify-center text-center bg-white border border-dashed border-gray-300'):
                            ui.icon('group_off', size='lg').classes('text-gray-400 mb-2')
                            ui.label('No se encontraron usuarios').classes('text-gray-500 font-medium')
                        return

                    for u in todos_u:
                        es_usuario_admin = u.get('es_admin', False)
                        es_usuario_subadmin = u.get('es_subadmin', False)
                        es_principal = (u.get('usuario', '').lower() == 'jose') or ('jose rafael' in u.get('nombre_completo', '').lower() and 'cifuentes' in u.get('nombre_completo', '').lower())
                        
                        area_color = {
                            'ingenieria': 'bg-blue-100 text-blue-800 border-blue-200',
                            'sistemas': 'bg-sky-100 text-sky-800 border-sky-200',
                            'produccion': 'bg-purple-100 text-purple-800 border-purple-200',
                            'programacion': 'bg-amber-100 text-amber-800 border-amber-200',
                            'master': 'bg-emerald-100 text-emerald-800 border-emerald-200'
                        }.get(u['area_encargada'].lower(), 'bg-slate-100 text-slate-800 border-slate-200')

                        with ui.card().classes('w-full p-4 bg-white shadow-sm border border-gray-200 rounded-xl hover:shadow-md transition-shadow flex flex-row items-center justify-between gap-4'):
                            with ui.row().classes('items-center gap-3 flex-grow min-w-0'):
                                # Avatar con iniciales
                                inits = (u['nombres'][:1] + u['apellidos'][:1]).upper() if u['nombres'] and u['apellidos'] else 'U'
                                if es_usuario_admin:
                                    avatar_classes = 'w-12 h-12 rounded-full bg-gradient-to-tr from-amber-600 via-indigo-900 to-slate-900 ring-2 ring-amber-400 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm'
                                elif es_usuario_subadmin:
                                    avatar_classes = 'w-12 h-12 rounded-full bg-gradient-to-tr from-purple-600 via-indigo-900 to-slate-900 ring-2 ring-purple-400 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm'
                                else:
                                    avatar_classes = 'w-12 h-12 rounded-full bg-gradient-to-tr from-slate-800 to-indigo-950 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm'
                                
                                with ui.element('div').classes(avatar_classes):
                                    ui.label(inits)

                                with ui.column().classes('gap-0.5 min-w-0 flex-grow'):
                                    with ui.row().classes('items-center gap-2 flex-wrap'):
                                        ui.label(u['nombre_completo']).classes('text-sm font-bold text-gray-900 leading-tight')
                                        ui.label(f"@{u['usuario']}").classes('text-[11px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded')
                                        ui.label(u['area_encargada'].upper()).classes(f'text-[9.5px] font-bold px-2 py-0.5 rounded border {area_color}')
                                        if es_usuario_admin:
                                            with ui.element('span').classes('text-[9.5px] font-black px-2 py-0.5 rounded-full border bg-amber-50 text-amber-900 border-amber-400 flex items-center gap-1 shadow-xs'):
                                                ui.icon('verified_user', size='xs').classes('text-amber-600')
                                                ui.label('ADMIN GENERAL')
                                        elif es_usuario_subadmin:
                                            with ui.element('span').classes('text-[9.5px] font-black px-2 py-0.5 rounded-full border bg-purple-50 text-purple-900 border-purple-400 flex items-center gap-1 shadow-xs'):
                                                ui.icon('stars', size='xs').classes('text-purple-600')
                                                ui.label('SUB ADMIN')
                                    
                                    ui.label(f"{u['cargo']} • {u['correo']} • Tel: {u['celular']}").classes('text-xs text-gray-500 truncate')

                            # Acciones de administración de usuario
                            with ui.row().classes('gap-1 shrink-0 items-center'):
                                # 1. Restablecer Contraseña
                                def abrir_modal_pass(uid=u['id'], nom=u['nombre_completo'], uname=u['usuario']):
                                    with ui.dialog() as dlg_pass, ui.card().classes('w-96 p-6 bg-white rounded-2xl shadow-xl'):
                                        with ui.row().classes('items-center gap-2 mb-2'):
                                            ui.icon('lock_reset', size='md').classes('text-amber-500')
                                            ui.label('Restablecer Contraseña').classes('text-lg font-bold text-gray-800')
                                        
                                        ui.label(f"Usuario: {nom} (@{uname})").classes('text-xs text-gray-500 mb-4')
                                        
                                        nueva_pwd = ui.input('Nueva Contraseña', password=True, password_toggle_button=True).classes('w-full mb-2')
                                        conf_pwd = ui.input('Confirmar Contraseña', password=True, password_toggle_button=True).classes('w-full mb-6')

                                        def guardar_pwd():
                                            if not nueva_pwd.value or len(nueva_pwd.value.strip()) < 3:
                                                ui.notify('La contraseña debe tener mínimo 3 caracteres', type='warning')
                                                return
                                            if nueva_pwd.value != conf_pwd.value:
                                                ui.notify('Las contraseñas no coinciden', type='negative')
                                                return
                                            
                                            ok, msg = reset_user_password(uid, nueva_pwd.value)
                                            if ok:
                                                ui.notify(msg, type='positive')
                                                dlg_pass.close()
                                            else:
                                                ui.notify(msg, type='negative')

                                        with ui.row().classes('w-full justify-end gap-2'):
                                            ui.button('Cancelar', on_click=dlg_pass.close).props('flat')
                                            ui.button('Guardar Contraseña', icon='save', on_click=guardar_pwd).classes('bg-amber-600 text-white font-bold')
                                    dlg_pass.open()

                                ui.button(icon='key', on_click=abrir_modal_pass).props('flat round size=sm color=amber').tooltip('Restablecer Contraseña')

                                # 2. Editar Datos y Rol
                                def abrir_modal_edit(user_data=u):
                                    with ui.dialog() as dlg_edit, ui.card().classes('w-full max-w-lg p-6 bg-white rounded-2xl shadow-xl'):
                                        es_u_principal = (user_data.get('usuario', '').lower() == 'jose') or ('jose rafael' in user_data.get('nombre_completo', '').lower() and 'cifuentes' in user_data.get('nombre_completo', '').lower())
                                        rol_actual = user_data.get('rol') or ('Admin General' if es_u_principal else 'Colaborador')

                                        with ui.row().classes('items-center justify-between w-full mb-4'):
                                            with ui.row().classes('items-center gap-2'):
                                                ui.icon('manage_accounts', size='md').classes('text-blue-600')
                                                ui.label('Editar Perfil de Usuario').classes('text-lg font-bold text-gray-800')
                                            if es_u_principal:
                                                with ui.element('span').classes('text-[10px] font-black px-2.5 py-0.5 rounded-full border bg-amber-50 text-amber-900 border-amber-400 flex items-center gap-1'):
                                                    ui.icon('verified_user', size='xs').classes('text-amber-600')
                                                    ui.label('ADMIN PRINCIPAL')
                                            elif user_data.get('es_admin'):
                                                with ui.element('span').classes('text-[10px] font-black px-2.5 py-0.5 rounded-full border bg-amber-50 text-amber-900 border-amber-400 flex items-center gap-1'):
                                                    ui.icon('verified_user', size='xs').classes('text-amber-600')
                                                    ui.label('ADMIN GENERAL')
                                            elif user_data.get('es_subadmin'):
                                                with ui.element('span').classes('text-[10px] font-black px-2.5 py-0.5 rounded-full border bg-purple-50 text-purple-900 border-purple-400 flex items-center gap-1'):
                                                    ui.icon('stars', size='xs').classes('text-purple-600')
                                                    ui.label('SUB ADMIN')
                                        
                                        ed_nom = ui.input('Nombres', value=user_data['nombres']).classes('w-full mb-2')
                                        ed_ape = ui.input('Apellidos', value=user_data['apellidos']).classes('w-full mb-2')
                                        ed_car = ui.input('Cargo', value=user_data.get('cargo') or '').classes('w-full mb-2')
                                        
                                        area_actual = user_data.get('area_encargada') or 'Produccion'
                                        areas_disponibles = ['Ingenieria', 'Produccion', 'Programacion', 'Master', 'Sistemas', 'Direccion', 'Administracion', 'Realizador', 'Operaciones']
                                        if area_actual not in areas_disponibles:
                                            areas_disponibles.append(area_actual)

                                        ed_are = ui.select(
                                            options=areas_disponibles,
                                            value=area_actual,
                                            label='Área'
                                        ).classes('w-full mb-2')

                                        # Selector de Rol del Sistema
                                        ed_rol = ui.select(
                                            options=['Colaborador', 'Sub Admin', 'Admin General'],
                                            value=rol_actual,
                                            label='Rol del Sistema'
                                        ).classes('w-full mb-2')
                                        
                                        if es_u_principal:
                                            ed_rol.props('readonly disable')
                                            ed_rol.tooltip('La cuenta maestra de Administrador Principal es inamovible.')

                                        ed_cel = ui.input('Celular', value=user_data['celular']).classes('w-full mb-2')
                                        ed_cor = ui.input('Correo', value=user_data['correo']).classes('w-full mb-6')

                                        def guardar_cambios_usuario():
                                            ok, msg = update_user_profile(
                                                user_data['id'],
                                                ed_nom.value,
                                                ed_ape.value,
                                                ed_car.value,
                                                ed_are.value,
                                                ed_cel.value,
                                                ed_cor.value,
                                                rol=ed_rol.value
                                            )
                                            if ok:
                                                ui.notify(msg, type='positive')
                                                dlg_edit.close()
                                                refrescar_listado_usuarios()
                                            else:
                                                ui.notify(msg, type='negative')

                                        with ui.row().classes('w-full justify-end gap-2'):
                                            ui.button('Cancelar', on_click=dlg_edit.close).props('flat')
                                            ui.button('Guardar Cambios', on_click=guardar_cambios_usuario).classes('bg-blue-600 text-white font-bold')
                                    dlg_edit.open()

                                ui.button(icon='edit', on_click=abrir_modal_edit).props('flat round size=sm color=blue').tooltip('Editar Datos y Rol')

                                # 3. Eliminar Usuario (Protegiendo al Administrador Principal)
                                if es_principal:
                                    ui.button(icon='verified_user').props('flat round size=sm color=amber').tooltip('Administrador Principal (Cuenta maestra inamovible, no eliminable)')
                                else:
                                    def confirmar_borrado(uid=u['id'], nom=u['nombre_completo']):
                                        with ui.dialog() as dlg_del, ui.card().classes('w-96 p-6 bg-white rounded-2xl'):
                                            with ui.row().classes('items-center gap-2 text-red-600 mb-2'):
                                                ui.icon('warning', size='md')
                                                ui.label('¿Eliminar Usuario?').classes('text-lg font-bold')
                                            
                                            ui.label(f'Esta acción eliminará el acceso de "{nom}". No se puede deshacer.').classes('text-xs text-gray-600 mb-6')
                                            
                                            def ejecutar_borrado():
                                                ok, msg = delete_user(uid)
                                                if ok:
                                                    ui.notify(msg, type='positive')
                                                    dlg_del.close()
                                                    refrescar_listado_usuarios()
                                                else:
                                                    ui.notify(msg, type='negative')

                                            with ui.row().classes('w-full justify-end gap-2'):
                                                ui.button('Cancelar', on_click=dlg_del.close).props('flat')
                                                ui.button('Eliminar', on_click=ejecutar_borrado).classes('bg-red-600 text-white font-bold')
                                        dlg_del.open()

                                    ui.button(icon='delete', on_click=confirmar_borrado).props('flat round size=sm color=red').tooltip('Eliminar Usuario')

            u_search.on('update:model-value', lambda _: refrescar_listado_usuarios())
            refrescar_listado_usuarios()

def admin_page():
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    area_usuario = user_info.get('area', '').lower()

    ui.query('body').style('background-color: #f8fafc')
    topbar(user_info)
    sidebar(user_info)

    es_admin_panel = user_info.get('es_admin', False) or user_info.get('es_subadmin', False) or 'ingenieria' in area_usuario or 'sistemas' in area_usuario or 'admin' in area_usuario
    if not es_admin_panel:
        with ui.column().classes('w-full h-[80vh] items-center justify-center text-center'):
            ui.icon('security', size='100px').classes('text-red-500 mb-4')
            ui.label('Acceso Denegado').classes('text-3xl font-bold text-gray-800')
            ui.label('Esta área es exclusiva para la gestión administrativa de Ingeniería y Administradores.').classes('text-gray-600')
        return

    with ui.column().classes('w-full p-6 sm:p-8 max-w-7xl mx-auto gap-4'):
        with ui.row().classes('items-center justify-between w-full mb-2 flex-wrap gap-2'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('admin_panel_settings', size='lg').classes('text-blue-600')
                with ui.column().classes('gap-0'):
                    ui.label('Panel de Control - Ingeniería').classes('text-2xl sm:text-3xl font-bold text-gray-800')
                    ui.label('Administración de usuarios del sistema y acceso directo a gestiones personalizadas').classes('text-xs text-gray-500')

        # Contenedor dinámico de la sub-barra de selección y paneles
        tabs_wrapper = ui.column().classes('w-full gap-0')

        def refrescar_interfaz(tab_activa='usuarios'):
            tabs_wrapper.clear()
            with tabs_wrapper:
                # 1. Obtener módulos fijados como acceso rápido en la sub-barra
                quick_access_ids = get_admin_quick_access_modules()
                todos_modulos = {m['id']: m for m in get_all_custom_modules()}
                modulos_fijados = [todos_modulos[mid] for mid in quick_access_ids if mid in todos_modulos]

                # Validar la pestaña activa
                tabs_validas = ['usuarios', 'reglas_traslado', 'gestiones', 'plantilla_acta'] + [f"mod_{m['id']}" for m in modulos_fijados]
                val_actual = tab_activa if tab_activa in tabs_validas else 'usuarios'

                # 2. Sub-barra de selección de pestañas
                with ui.tabs().classes('w-full border-b border-gray-200 text-gray-600') as tabs:
                    tab_u = ui.tab('usuarios', label='Usuarios del Sistema', icon='manage_accounts').classes('font-bold text-blue-600')
                    tab_t = ui.tab('reglas_traslado', label='Reglas de Traslado y Operación', icon='transfer_within_a_station').classes('font-bold text-amber-600')
                    tab_g = ui.tab('gestiones', label='Creador de Gestiones', icon='dashboard_customize').classes('font-bold text-indigo-600')
                    tab_p = ui.tab('plantilla_acta', label='Plantilla Acta Retransmisión', icon='description').classes('font-bold text-emerald-600')
                    
                    # Pestañas dinámicas añadidas como acceso rápido
                    for m in modulos_fijados:
                        ui.tab(f"mod_{m['id']}", label=m['nombre'], icon=m.get('icono') or 'inventory').classes('font-bold text-slate-800')

                # 3. Paneles de contenido según la pestaña seleccionada
                with ui.tab_panels(tabs, value=val_actual).classes('w-full bg-transparent p-0 mt-4'):
                    # Pestaña fija 1: Usuarios del Sistema
                    with ui.tab_panel('usuarios').classes('p-0'):
                        render_usuarios_panel()

                    # Pestaña fija 2: Reglas de Traslado y Desplazamiento Técnico
                    with ui.tab_panel('reglas_traslado').classes('p-0'):
                        render_transition_rules_admin(user_info)

                    # Pestaña fija 3: Creador de Gestiones (Vista general donde se pueden ver todas y fijarlas)
                    with ui.tab_panel('gestiones').classes('p-0'):
                        render_custom_management_builder(
                            show_list=True,
                            on_quick_access_toggle=lambda: refrescar_interfaz(tab_activa=tabs.value)
                        )

                    # Pestaña fija 4: Plantilla del Acta de Retransmisión
                    with ui.tab_panel('plantilla_acta').classes('p-0'):
                        render_acta_template_admin()

                    # Pestañas dinámicas añadidas como Acceso Rápido (Vista a pantalla completa de la gestión)
                    for m in modulos_fijados:
                        with ui.tab_panel(f"mod_{m['id']}").classes('p-0'):
                            render_custom_management_builder(
                                initial_module_id=m['id'],
                                show_list=False,
                                on_quick_access_toggle=lambda: refrescar_interfaz(tab_activa='gestiones')
                            )

        refrescar_interfaz(tab_activa='usuarios')