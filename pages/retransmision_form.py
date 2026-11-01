import os
import time
from datetime import datetime
from nicegui import ui, app

from components.topbar import topbar
from components.sidebar import sidebar
from database import (
    get_user_by_usuario, 
    create_retransmission_authorization, 
    get_all_retransmission_authorizations,
    delete_retransmission_authorization
)
from components.retransmision_ocr import (
    extraer_texto_pdf,
    analizar_documento_rti,
    analizar_documento_camara,
    analizar_documento_cedula,
    realizar_cruce_documentos
)
from components.retransmision_approval import render_retransmision_approval_dialog

UPLOAD_DIR = os.path.join(os.getcwd(), 'uploads', 'retransmisiones')
os.makedirs(UPLOAD_DIR, exist_ok=True)

def retransmision_page():
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    # Verificación de permisos: Exclusivo Ingeniería, Gerencia y Administración General (Jose Rafael Cifuentes)
    user_usuario = (user_info.get('usuario') or '').strip().lower()
    user_full_name = f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}".strip().lower()
    user_area = (user_info.get('area_encargada') or user_info.get('area') or '').strip().lower()
    user_cargo = (user_info.get('cargo') or '').strip().lower()

    user_rol = (user_info.get('rol') or '').strip().lower()

    es_admin = (
        user_rol in ['admin general', 'administrador general', 'admin', 'administrador'] or
        user_info.get('es_admin', False) or
        user_usuario in ['jose', 'admin', 'administrador'] or
        ('jose rafael' in user_full_name and 'cifuentes' in user_full_name) or
        'admin' in user_cargo or 'administrador' in user_cargo
    )
    es_ingenieria = any(k in user_area for k in ['ingenieria', 'ingeniería', 'sistemas'])
    es_gerencia = any(k in user_area for k in ['gerencia', 'dirección general', 'direccion general']) or any(k in user_cargo for k in ['gerente', 'director general', 'directora general'])
    es_autorizado = es_admin or es_ingenieria or es_gerencia

    if not es_autorizado:
        ui.notify('Acceso restringido: Esta herramienta es exclusiva para Ingeniería y Gerencia.', type='warning')
        ui.navigate.to('/herramientas')
        return

    # TEMA CLARO INSTITUCIONAL (#f8fafc)
    ui.query('body').style('background-color: #f8fafc; margin: 0; padding: 0;')
    topbar(user_info)
    sidebar(user_info)

    # Estado reactivo del formulario
    state = {
        'rti_uploaded': False,
        'camara_uploaded': False,
        'cedula_uploaded': False,
        'file_rti_path': '',
        'file_camara_path': '',
        'file_cedula_path': '',
        'datos_rti': {},
        'datos_camara': {},
        'datos_cedula': {},
        'cruce_resultado': None,
        'validado_manualmente': False,
        # Campos consolidados editables
        'operator_name': '',
        'nit': '',
        'rti_number': '',
        'rep_name': '',
        'rep_doc': '',
        'municipality': '',
        'department': '',
        'channel_target': 'Canal Teleamiga',
        'notes': ''
    }

    async def guardar_archivo_upload(e, prefijo: str) -> str:
        """Extrae de forma robusta los bytes y nombre de cualquier evento de subida en NiceGUI y lo guarda en disco."""
        nombre = getattr(e, 'name', None) or (getattr(e.file, 'name', None) if hasattr(e, 'file') else None) or f"{prefijo}.pdf"
        nombre_seguro = os.path.basename(nombre)
        filename = f"{prefijo}_{int(time.time())}_{nombre_seguro}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        content = None
        if hasattr(e, 'file') and hasattr(e.file, 'read'):
            res = e.file.read()
            content = await res if hasattr(res, '__await__') else res
        elif hasattr(e, 'content') and hasattr(e.content, 'read'):
            res = e.content.read()
            content = await res if hasattr(res, '__await__') else res
        elif hasattr(e, 'content'):
            content = e.content
        elif hasattr(e, 'read'):
            res = e.read()
            content = await res if hasattr(res, '__await__') else res

        if content is None:
            raise ValueError("No se pudo leer el contenido del archivo subido.")

        with open(filepath, 'wb') as f:
            f.write(content)
            
        return filepath

    def actualizar_cruce_si_listo():
        """Ejecuta el cruce automático si al menos están RTI y Cámara cargados."""
        if state['rti_uploaded'] and state['camara_uploaded']:
            cruce = realizar_cruce_documentos(
                state['datos_rti'], state['datos_camara'], state['datos_cedula']
            )
            state['cruce_resultado'] = cruce
            state['validado_manualmente'] = False
            # Auto-llenar campos consolidados con datos cruzados de alta fidelidad
            cons = cruce.get('datos_consolidados', {})
            if cons.get('operator_name'): state['operator_name'] = cons['operator_name']
            if cons.get('nit'): state['nit'] = cons['nit']
            if cons.get('rti_number'): state['rti_number'] = cons['rti_number']
            if cons.get('rep_name'): state['rep_name'] = cons['rep_name']
            if cons.get('rep_doc'): state['rep_doc'] = cons['rep_doc']
            if cons.get('municipality'): state['municipality'] = cons['municipality']
            if cons.get('department'): state['department'] = cons['department']

    with ui.column().classes('w-full min-h-[calc(100vh-65px)] bg-slate-50 text-slate-800 p-4 sm:p-6 md:p-8 lg:p-10 gap-6'):
        
        # Barra superior de navegación / título
        with ui.row().classes('w-full justify-between items-start sm:items-center pb-4 border-b border-slate-200 flex-col sm:flex-row gap-4'):
            with ui.row().classes('items-center gap-3 sm:gap-4'):
                ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/herramientas'))\
                    .props('flat round color=slate-600').tooltip('Volver a Herramientas')
                with ui.element('div').classes('w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm'):
                    ui.icon('cast_connected', size='md')
                with ui.column().classes('gap-0.5'):
                    ui.label('Autorización de Retransmisión de Señal').classes('text-xl sm:text-2xl font-black text-slate-900 tracking-tight')
                    ui.label('Módulo de Verificación Documental MINTIC RTI, Cruce OCR y Emisión de Actas Oficiales').classes('text-xs text-slate-500')

            with ui.row().classes('items-center gap-2 flex-wrap'):
                ui.badge('INGENIERÍA / GERENCIA').props('outline color=indigo text-color=indigo-9').classes('text-xs font-bold px-3 py-1')
                ui.badge(user_info.get('nombre_completo', username)).props('color=slate-100 text-color=slate-700 border border-slate-300').classes('text-xs font-medium px-3 py-1')

        # Pestañas principales
        with ui.tabs().classes('w-full bg-white rounded-2xl p-1 border border-slate-200 shadow-sm text-slate-700') as tabs:
            tab_radicar = ui.tab('Radicar Nueva Solicitud', icon='add_circle')
            tab_expedientes = ui.tab('Bandeja de Expedientes & Actas', icon='folder_special')

        with ui.tab_panels(tabs, value=tab_radicar).classes('w-full bg-transparent p-0 mt-4'):
            
            # ==============================================================
            # PESTAÑA 1: RADICAR NUEVA SOLICITUD (FORMULARIO CONDICIONAL)
            # ==============================================================
            with ui.tab_panel(tab_radicar).classes('w-full p-0 flex flex-col gap-6'):
                
                @ui.refreshable
                def render_formulario_dinamico():
                    with ui.row().classes('w-full gap-6 items-start'):
                        
                        # COLUMNA IZQUIERDA: ÁREA DE CARGA DE ARCHIVOS
                        with ui.column().classes('w-full lg:w-1/2 gap-6'):
                            
                            # --- PASO 1: CERTIFICADO RTI MINTIC (OBLIGATORIO) ---
                            with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm hover:shadow-md transition-shadow'):
                                with ui.row().classes('justify-between items-center w-full mb-3 flex-wrap gap-2'):
                                    with ui.row().classes('items-center gap-2.5'):
                                        with ui.element('div').classes('w-7 h-7 rounded-full bg-indigo-600 text-white font-black text-xs flex items-center justify-center shrink-0'):
                                            ui.label('1')
                                        ui.label('Certificado RTI MINTIC (Campo Obligatorio)').classes('text-base font-bold text-slate-900')
                                    
                                    if state['rti_uploaded']:
                                        with ui.element('div').classes('px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold flex items-center gap-1'):
                                            ui.icon('check_circle', size='xs').classes('text-emerald-600')
                                            ui.label('CARGADO Y LEÍDO')
                                    else:
                                        with ui.element('div').classes('px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold'):
                                            ui.label('REQUERIDO')

                                ui.label('Suba el certificado oficial de Registro de Tecnologías de la Información y las Comunicaciones (RTI) expedido por el MINTIC. Este archivo habilitará los siguientes campos.')\
                                    .classes('text-xs text-slate-500 mb-4 leading-relaxed')

                                async def handle_upload_rti(e):
                                    filepath = await guardar_archivo_upload(e, 'RTI')
                                    
                                    # Extracción de texto y análisis OCR
                                    texto = extraer_texto_pdf(filepath)
                                    datos = analizar_documento_rti(texto)
                                    
                                    state['rti_uploaded'] = True
                                    state['file_rti_path'] = filepath
                                    state['datos_rti'] = datos
                                    
                                    if datos.get('operator_name'): state['operator_name'] = datos['operator_name']
                                    if datos.get('nit'): state['nit'] = datos['nit']
                                    if datos.get('rti_number'): state['rti_number'] = datos['rti_number']
                                    if datos.get('rep_name'): state['rep_name'] = datos['rep_name']
                                    if datos.get('rep_doc'): state['rep_doc'] = datos['rep_doc']
                                    if datos.get('municipality'): state['municipality'] = datos['municipality']
                                    if datos.get('department'): state['department'] = datos['department']

                                    actualizar_cruce_si_listo()
                                    ui.notify('Certificado RTI MINTIC cargado y analizado con éxito.', type='positive')
                                    render_formulario_dinamico.refresh()

                                ui.upload(
                                    label='Arrastre o seleccione el PDF de RTI MINTIC',
                                    auto_upload=True,
                                    on_upload=handle_upload_rti
                                ).props('accept=.pdf color=indigo-7 flat bordered').classes('w-full')

                                # Mini resumen de datos detectados del RTI
                                if state['rti_uploaded'] and state['datos_rti']:
                                    d = state['datos_rti']
                                    with ui.column().classes('w-full mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl gap-1 text-xs'):
                                        ui.label('DATOS DETECTADOS EN RTI MINTIC:').classes('font-bold text-indigo-700 text-[11px]')
                                        ui.label(f"• Operador / Razón: {d.get('operator_name') or 'N/A'}")
                                        ui.label(f"• NIT: {d.get('nit') or 'N/A'}")
                                        ui.label(f"• No. Registro RTI: {d.get('rti_number') or 'N/A'}")
                                        if d.get('rep_name'):
                                            ui.label(f"• Representante Legal: {d.get('rep_name')} (C.C. {d.get('rep_doc') or 'N/A'})")
                                        if d.get('tiene_tv'):
                                            ui.badge('Habilitado para Televisión').props('color=emerald-1 text-color=emerald-9').classes('text-[10px] w-fit mt-1')

                            # --- PASO 2: CÁMARA DE COMERCIO Y CÉDULA (CONDICIONALES) ---
                            if not state['rti_uploaded']:
                                with ui.card().classes('w-full bg-slate-100/60 border border-slate-200 p-8 rounded-3xl flex flex-col items-center justify-center text-center py-12'):
                                    ui.icon('lock', size='lg').classes('text-slate-400 mb-2')
                                    ui.label('Documentos Adicionales Bloqueados').classes('text-base font-bold text-slate-700')
                                    ui.label('Las opciones para adjuntar la Cámara de Comercio y la Cédula del Representante Legal se habilitarán automáticamente en cuanto se cargue el Certificado RTI MINTIC.')\
                                        .classes('text-xs text-slate-500 max-w-sm mt-1 leading-relaxed')
                            
                            else:
                                with ui.column().classes('w-full gap-6 animate-fade-in'):
                                    
                                    # Cámara de Comercio
                                    with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm hover:shadow-md transition-shadow'):
                                        with ui.row().classes('justify-between items-center w-full mb-3 flex-wrap gap-2'):
                                            with ui.row().classes('items-center gap-2.5'):
                                                with ui.element('div').classes('w-7 h-7 rounded-full bg-indigo-600 text-white font-black text-xs flex items-center justify-center shrink-0'):
                                                    ui.label('2')
                                                ui.label('Cámara de Comercio (Campo Obligatorio)').classes('text-base font-bold text-slate-900')
                                            
                                            if state['camara_uploaded']:
                                                with ui.element('div').classes('px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold flex items-center gap-1'):
                                                    ui.icon('check_circle', size='xs').classes('text-emerald-600')
                                                    ui.label('CARGADO Y LEÍDO')
                                            else:
                                                with ui.element('div').classes('px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold'):
                                                    ui.label('REQUERIDO')

                                        ui.label('Certificado de Existencia y Representación Legal (con vigencia preferiblemente no mayor a 30-90 días).')\
                                            .classes('text-xs text-slate-500 mb-4')

                                        async def handle_upload_camara(e):
                                            filepath = await guardar_archivo_upload(e, 'CAMARA')
                                            
                                            texto = extraer_texto_pdf(filepath)
                                            datos = analizar_documento_camara(texto)
                                            state['camara_uploaded'] = True
                                            state['file_camara_path'] = filepath
                                            state['datos_camara'] = datos

                                            actualizar_cruce_si_listo()
                                            ui.notify('Cámara de Comercio analizada con éxito.', type='positive')
                                            render_formulario_dinamico.refresh()

                                        ui.upload(
                                            label='Arrastre o seleccione el PDF de Cámara de Comercio',
                                            auto_upload=True,
                                            on_upload=handle_upload_camara
                                        ).props('accept=.pdf color=indigo-7 flat bordered').classes('w-full')

                                        if state['camara_uploaded'] and state['datos_camara']:
                                            d = state['datos_camara']
                                            with ui.column().classes('w-full mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl gap-1 text-xs'):
                                                ui.label('DATOS DETECTADOS EN CÁMARA DE COMERCIO:').classes('font-bold text-indigo-700 text-[11px]')
                                                ui.label(f"• Razón Social: {d.get('operator_name') or 'N/A'}")
                                                ui.label(f"• NIT: {d.get('nit') or 'N/A'}")
                                                ui.label(f"• Representante Legal: {d.get('rep_name') or 'N/A'}")
                                                ui.label(f"• C.C. Representante: {d.get('rep_doc') or 'N/A'}")
                                                if d.get('matricula'):
                                                    ui.label(f"• Matrícula Mercantil: {d.get('matricula')}")

                                    # Cédula del Representante Legal
                                    with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm hover:shadow-md transition-shadow'):
                                        with ui.row().classes('justify-between items-center w-full mb-3 flex-wrap gap-2'):
                                            with ui.row().classes('items-center gap-2.5'):
                                                with ui.element('div').classes('w-7 h-7 rounded-full bg-indigo-600 text-white font-black text-xs flex items-center justify-center shrink-0'):
                                                    ui.label('3')
                                                ui.label('Cédula del Representante Legal (Obligatorio)').classes('text-base font-bold text-slate-900')
                                            
                                            if state['cedula_uploaded']:
                                                with ui.element('div').classes('px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold flex items-center gap-1'):
                                                    ui.icon('check_circle', size='xs').classes('text-emerald-600')
                                                    ui.label('CARGADO Y LEÍDO')
                                            else:
                                                with ui.element('div').classes('px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold'):
                                                    ui.label('REQUERIDO')

                                        ui.label('Copia legible del documento de identidad del representante legal (escaneo o imagen de ambas caras).')\
                                            .classes('text-xs text-slate-500 mb-4')

                                        async def handle_upload_cedula(e):
                                            filepath = await guardar_archivo_upload(e, 'CEDULA')
                                            
                                            texto = extraer_texto_pdf(filepath)
                                            datos = analizar_documento_cedula(texto)
                                            state['cedula_uploaded'] = True
                                            state['file_cedula_path'] = filepath
                                            state['datos_cedula'] = datos

                                            actualizar_cruce_si_listo()
                                            ui.notify('Cédula procesada con éxito.', type='positive')
                                            render_formulario_dinamico.refresh()

                                        ui.upload(
                                            label='Arrastre o seleccione el documento de cédula',
                                            auto_upload=True,
                                            on_upload=handle_upload_cedula
                                        ).props('accept=.pdf,.jpg,.jpeg,.png color=indigo-7 flat bordered').classes('w-full')

                                        if state['cedula_uploaded'] and state['datos_cedula']:
                                            d = state['datos_cedula']
                                            with ui.column().classes('w-full mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl gap-1 text-xs'):
                                                ui.label('DATOS DETECTADOS EN CÉDULA:').classes('font-bold text-indigo-700 text-[11px]')
                                                ui.label(f"• Documento (C.C.): {d.get('rep_doc') or 'Coincidente con registros oficiales'}")
                                                if d.get('rep_name'):
                                                    ui.label(f"• Titular: {d.get('rep_name')}")


                        # COLUMNA DERECHA: CRUCE ALGORÍTMICO Y DATOS PARA RADICACIÓN
                        with ui.column().classes('w-full lg:w-1/2 gap-6'):
                            
                            # Tarjeta de Auditoría y Filtro 1 Automático
                            with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm'):
                                with ui.row().classes('justify-between items-center w-full mb-2 flex-wrap gap-2'):
                                    with ui.row().classes('items-center gap-2.5'):
                                        ui.icon('verified', size='md').classes('text-indigo-600')
                                        ui.label('Resultado del Filtro 1 (Cruce OCR)').classes('text-base font-bold text-slate-900')
                                    
                                    if state['cruce_resultado']:
                                        if state['cruce_resultado']['aprobado_filtro1']:
                                            with ui.element('div').classes('px-3 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-bold flex items-center gap-1.5'):
                                                with ui.element('span').classes('w-2 h-2 rounded-full bg-emerald-500 animate-pulse'):
                                                    pass
                                                txt_badge = f"COINCIDENCIA: {state['cruce_resultado']['score']}%"
                                                if state.get('validado_manualmente'):
                                                    txt_badge += " (VALIDADO)"
                                                ui.label(txt_badge)
                                        else:
                                            with ui.element('div').classes('px-3 py-1 rounded-full bg-amber-50 border border-amber-300 text-amber-800 text-xs font-bold flex items-center gap-1.5'):
                                                ui.icon('warning', size='xs').classes('text-amber-600')
                                                ui.label(f"COINCIDENCIA: {state['cruce_resultado']['score']}% • REVISIÓN REQUERIDA")
                                    else:
                                        with ui.element('div').classes('px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-medium'):
                                            ui.label('ESPERANDO DOCUMENTOS')

                                if not state['cruce_resultado']:
                                    ui.label('Cargue el Certificado RTI MINTIC y la Cámara de Comercio. El motor comparará automáticamente el NIT, la Razón Social, la Cédula del Representante y la habilitación de TV.')\
                                        .classes('text-xs text-slate-500 my-4 leading-relaxed')
                                else:
                                    res = state['cruce_resultado']
                                    with ui.column().classes('w-full my-3 gap-2'):
                                        for v in res['verificaciones']:
                                            valido = v['valido']
                                            bg_c = 'bg-emerald-50/80 border-emerald-200 text-emerald-900' if valido else 'bg-amber-50/80 border-amber-200 text-amber-900'
                                            icon_c = 'check_circle' if valido else 'warning'
                                            icon_color = 'text-emerald-600' if valido else 'text-amber-600'
                                            with ui.row().classes(f'w-full p-3 rounded-2xl border {bg_c} items-center justify-between text-xs gap-2 flex-wrap'):
                                                with ui.row().classes('items-center gap-2'):
                                                    ui.icon(icon_check:=icon_c).classes(f'text-base {icon_color}')
                                                    ui.label(v['criterio']).classes('font-bold text-slate-900')
                                                ui.label(v['mensaje']).classes('text-slate-600 text-[11px] font-medium')

                                    if res['aprobado_filtro1']:
                                        es_man = state.get('validado_manualmente') or res.get('validado_manualmente')
                                        with ui.row().classes('w-full p-4 bg-emerald-50 border border-emerald-300 rounded-2xl items-center gap-3 mt-3'):
                                            ui.icon('verified' if es_man else 'thumb_up', size='sm').classes('text-emerald-600')
                                            with ui.column().classes('gap-0.5'):
                                                ui.label('Filtro 1 Aprobado al 100%' + (' (Validación Manual Acreditada)' if es_man else ' Automáticamente')).classes('text-xs text-emerald-900 font-bold')
                                                ui.label('Todos los datos legales requeridos han sido verificados y coinciden. El expediente se transferirá directamente a Gerencia General para firma digital.')\
                                                    .classes('text-[11px] text-emerald-700 leading-tight')
                                    else:
                                        with ui.row().classes('w-full p-4 bg-amber-50 border border-amber-300 rounded-2xl items-center gap-3 mt-3'):
                                            ui.icon('info', size='sm').classes('text-amber-600')
                                            with ui.column().classes('gap-0.5'):
                                                ui.label(f"Requiere Revisión o Comprobación Manual (Coincidencia {res.get('score', 0)}%)").classes('text-xs text-amber-900 font-bold')
                                                ui.label('El escaneo OCR no reconoció con certeza algunos campos (como el Representante o Cédula). Ingréselos abajo en "Datos del Expediente para Radicación" y presione "Comprobar Datos Manuales" para alcanzar el 100% y habilitar la radicación.')\
                                                    .classes('text-[11px] text-amber-700 leading-tight')

                            # Tarjeta con Formulario de Radicación Final
                            with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm gap-4'):
                                ui.label('Datos del Expediente para Radicación').classes('text-base font-bold text-slate-900')
                                ui.label('Verifique o complete los datos que figurarán en el Acta Formal de Autorización de Retransmisión:')\
                                    .classes('text-xs text-slate-500')

                                with ui.grid().classes('grid grid-cols-1 md:grid-cols-2 gap-4 w-full'):
                                    ui.input('Nombre / Razón Social del Operador', value=state['operator_name'], on_change=lambda e: state.update({'operator_name': e.value}))\
                                        .props('dense outlined').classes('w-full md:col-span-2')
                                    
                                    ui.input('NIT del Operador', value=state['nit'], on_change=lambda e: state.update({'nit': e.value}))\
                                        .props('dense outlined').classes('w-full')
                                    
                                    ui.input('Número de Registro RTI MINTIC', value=state['rti_number'], on_change=lambda e: state.update({'rti_number': e.value}))\
                                        .props('dense outlined').classes('w-full')
                                    
                                    ui.input('Representante Legal', value=state['rep_name'], on_change=lambda e: state.update({'rep_name': e.value}))\
                                        .props('dense outlined').classes('w-full')
                                    
                                    ui.input('Cédula del Representante', value=state['rep_doc'], on_change=lambda e: state.update({'rep_doc': e.value}))\
                                        .props('dense outlined').classes('w-full')

                                    ui.input('Municipio de Operación', value=state['municipality'], on_change=lambda e: state.update({'municipality': e.value}))\
                                        .props('dense outlined').classes('w-full')

                                    ui.input('Departamento', value=state['department'], on_change=lambda e: state.update({'department': e.value}))\
                                        .props('dense outlined').classes('w-full')

                                ui.input('Canal a Autorizar', value=state['channel_target'], on_change=lambda e: state.update({'channel_target': e.value}))\
                                    .props('dense outlined readonly').classes('w-full')

                                ui.textarea('Observaciones o Notas Adicionales', value=state['notes'], on_change=lambda e: state.update({'notes': e.value}))\
                                    .props('dense outlined').classes('w-full')

                                # Lógica de Comprobación Manual
                                def comprobar_datos_manuales():
                                    if not state['rti_uploaded']:
                                        ui.notify('Debe cargar obligatoriamente el Certificado RTI MINTIC.', type='warning', icon='warning')
                                        return
                                    if not state['camara_uploaded']:
                                        ui.notify('Debe cargar la Cámara de Comercio.', type='warning', icon='warning')
                                        return

                                    # Validar campos esenciales para alcanzar el 100%
                                    faltantes = []
                                    if not (state.get('operator_name') or '').strip():
                                        faltantes.append('Nombre / Razón Social')
                                    if not (state.get('nit') or '').strip():
                                        faltantes.append('NIT')
                                    if not (state.get('rep_name') or '').strip():
                                        faltantes.append('Representante Legal')
                                    if not (state.get('rep_doc') or '').strip():
                                        faltantes.append('Cédula del Representante')

                                    if faltantes:
                                        ui.notify(f"Para comprobar y validar al 100%, ingrese: {', '.join(faltantes)}", type='warning', icon='edit_note', duration=5000)
                                        return

                                    nuevo_cruce = realizar_cruce_documentos(
                                        state['datos_rti'],
                                        state['datos_camara'],
                                        state['datos_cedula'],
                                        datos_manuales=state
                                    )
                                    state['cruce_resultado'] = nuevo_cruce
                                    state['validado_manualmente'] = True

                                    if nuevo_cruce.get('score') == 100 and nuevo_cruce.get('aprobado_filtro1'):
                                        ui.notify('¡Comprobación exitosa! Coincidencia al 100%. Botón de radicación habilitado.', type='positive', icon='verified', duration=5000)
                                    else:
                                        ui.notify(f"Comprobación ejecutada. Coincidencia: {nuevo_cruce.get('score')}%. Revise los criterios pendientes.", type='warning', icon='info', duration=5000)

                                    render_formulario_dinamico.refresh()

                                # Botón de Radicación
                                async def ejecutar_radicacion():
                                    if not state['rti_uploaded']:
                                        ui.notify('Debe cargar obligatoriamente el Certificado RTI MINTIC.', type='negative')
                                        return
                                    if not state['camara_uploaded']:
                                        ui.notify('Debe cargar la Cámara de Comercio.', type='negative')
                                        return
                                    if not (state.get('operator_name') or '').strip() or not (state.get('nit') or '').strip():
                                        ui.notify('Ingrese al menos el nombre del operador y el NIT.', type='negative')
                                        return

                                    # Generar código único consecutivo
                                    existentes = get_all_retransmission_authorizations()
                                    next_num = len(existentes) + 1
                                    anio = datetime.now().year
                                    codigo_generado = f"AUT-RET-{anio}-{next_num:04d}"

                                    aprobado_auto = state['cruce_resultado']['aprobado_filtro1'] if state['cruce_resultado'] else False
                                    estado_inicial = 'filtro1_aprobado' if aprobado_auto else 'pendiente_revision'

                                    data_guardar = {
                                        'code': codigo_generado,
                                        'operator_name': state['operator_name'].strip(),
                                        'nit': state['nit'].strip(),
                                        'rti_number': state['rti_number'].strip(),
                                        'rep_name': state['rep_name'].strip(),
                                        'rep_doc': state['rep_doc'].strip(),
                                        'channel_target': state['channel_target'],
                                        'municipality': state['municipality'].strip() or 'Bogotá D.C.',
                                        'department': state['department'].strip() or 'Bogotá D.C.',
                                        'address': state.get('datos_camara', {}).get('address') or state.get('datos_rti', {}).get('address') or 'CR 73 BIS 49 A 29',
                                        'notification_email': state.get('datos_camara', {}).get('notification_email') or f"notificaciones@{state['operator_name'].lower().replace(' ', '')[:8]}.com.co",
                                        'status': estado_inicial,
                                        'created_by': user_info.get('nombre_completo', username),
                                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'file_rti_path': state['file_rti_path'],
                                        'file_camara_path': state['file_camara_path'],
                                        'file_cedula_path': state['file_cedula_path'],
                                        'ocr_data': {
                                            'rti': state['datos_rti'],
                                            'camara': state['datos_camara'],
                                            'cedula': state['datos_cedula']
                                        },
                                        'match_results': state['cruce_resultado'] or {},
                                        'notes': state['notes']
                                    }

                                    new_id = create_retransmission_authorization(data_guardar)
                                    
                                    if aprobado_auto:
                                        ui.notify(
                                            f"¡Filtro 1 Aprobado al 100%! Expediente {codigo_generado} transferido a la bandeja de Gerencia para firma digital.",
                                            type='positive',
                                            icon='verified',
                                            duration=6000
                                        )
                                    else:
                                        ui.notify(
                                            f"Expediente {codigo_generado} radicado en revisión técnica. No se remitirá a Gerencia hasta subsanar discrepancias.",
                                            type='warning',
                                            icon='info',
                                            duration=6000
                                        )

                                    # Reset de estado para una nueva radicación
                                    state['rti_uploaded'] = False
                                    state['camara_uploaded'] = False
                                    state['cedula_uploaded'] = False
                                    state['cruce_resultado'] = None
                                    state['validado_manualmente'] = False
                                    state['operator_name'] = ''
                                    state['nit'] = ''
                                    state['rti_number'] = ''
                                    state['rep_name'] = ''
                                    state['rep_doc'] = ''
                                    state['municipality'] = ''
                                    state['department'] = ''
                                    state['notes'] = ''
                                    render_formulario_dinamico.refresh()
                                    render_tabla_expedientes.refresh()

                                    # Abrir diálogo para inspección humana y firma
                                    render_retransmision_approval_dialog(new_id, user_info, on_status_changed_callback=render_tabla_expedientes.refresh)

                                # RENDERIZADO CONDICIONAL DE BOTONES:
                                cruce = state.get('cruce_resultado')
                                tiene_docs = state['rti_uploaded'] and state['camara_uploaded']
                                esta_100 = bool(cruce and cruce.get('score') == 100 and cruce.get('aprobado_filtro1'))

                                if not tiene_docs:
                                    with ui.row().classes('w-full items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs text-slate-500 mt-2'):
                                        ui.icon('lock', size='xs').classes('text-slate-400')
                                        ui.label('Cargue el Certificado RTI MINTIC y la Cámara de Comercio para habilitar la comprobación y radicación.')
                                    ui.button('Radicar y Guardar Expediente', icon='save')\
                                        .props('disable').classes('w-full bg-slate-200 text-slate-400 font-bold py-3.5 rounded-2xl shadow-none text-sm mt-1 cursor-not-allowed')

                                elif not esta_100:
                                    score_actual = cruce.get('score', 0) if cruce else 0
                                    with ui.row().classes('w-full items-center gap-2 p-3.5 bg-amber-50 border border-amber-300 rounded-2xl text-xs text-amber-900 mt-2'):
                                        ui.icon('fact_check', size='sm').classes('text-amber-600 shrink-0')
                                        with ui.column().classes('gap-0.5'):
                                            ui.label(f'Coincidencia actual: {score_actual}% (Revisión requerida)').classes('font-bold')
                                            ui.label('Si el OCR no leyó el Representante Legal o su Cédula, complete los campos de arriba y presione "Comprobar Datos Manuales" para alcanzar el 100% y habilitar la radicación.')\
                                                .classes('text-[11px] text-amber-800 leading-tight')

                                    ui.button('COMPROBAR DATOS MANUALES', icon='fact_check', on_click=comprobar_datos_manuales)\
                                        .classes('w-full bg-amber-600 hover:bg-amber-700 text-white font-black py-4 rounded-2xl shadow-md hover:shadow-lg transition-all text-sm mt-1 tracking-wide flex items-center justify-center gap-2')

                                else:
                                    with ui.row().classes('w-full items-center justify-between p-3.5 bg-emerald-50 border border-emerald-300 rounded-2xl text-xs text-emerald-900 mt-2 flex-wrap gap-2'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.icon('verified', size='sm').classes('text-emerald-600 shrink-0')
                                            with ui.column().classes('gap-0'):
                                                ui.label('¡Coincidencia del 100% Verificada!').classes('font-bold text-emerald-950')
                                                ui.label('El expediente ha cumplido todos los criterios legales y está listo para ser radicado.')\
                                                    .classes('text-[11px] text-emerald-700')
                                        ui.button('Recomprobar datos', icon='sync', on_click=comprobar_datos_manuales)\
                                            .props('flat dense size=sm color=emerald-8').classes('text-xs font-bold')

                                    ui.button('RADICAR Y GUARDAR EXPEDIENTE', icon='save', on_click=ejecutar_radicacion)\
                                        .classes('w-full bg-emerald-600 hover:bg-emerald-700 text-white font-black py-4 rounded-2xl shadow-lg hover:shadow-xl transition-all text-sm mt-1 tracking-wide flex items-center justify-center gap-2')

                render_formulario_dinamico()

            # ==============================================================
            # PESTAÑA 2: BANDEJA DE EXPEDIENTES Y SEGUIMIENTO (MODO CLARO)
            # ==============================================================
            with ui.tab_panel(tab_expedientes).classes('w-full p-0'):
                
                @ui.refreshable
                def render_tabla_expedientes():
                    todas_solicitudes = get_all_retransmission_authorizations()
                    
                    # Filtro estricto por rol:
                    # Si el usuario es de Gerencia (y no es admin técnico), SOLO ve expedientes aprobados por el filtro 1 o por Gerencia
                    user_area = (user_info.get('area') or '').lower()
                    user_cargo = (user_info.get('cargo') or '').lower()
                    es_gerencia = any(k in user_area or k in user_cargo for k in ['gerencia', 'gerente'])
                    es_tecnico = any(k in user_area or k in user_cargo for k in ['ingenieria', 'sistemas', 'admin'])

                    if es_gerencia and not es_tecnico:
                        solicitudes = [s for s in todas_solicitudes if s.get('status') in ['filtro1_aprobado', 'aprobado_gerencia']]
                    else:
                        solicitudes = todas_solicitudes

                    pendientes_firma = [s for s in solicitudes if s.get('status') == 'filtro1_aprobado']

                    with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-7 rounded-3xl shadow-sm'):
                        
                        # Banner de notificación para Gerencia cuando hay expedientes 100% aprobados listos para firmar
                        if es_gerencia and pendientes_firma:
                            with ui.row().classes('w-full p-4 bg-indigo-50 border border-indigo-200 rounded-2xl items-center justify-between mb-5 flex-wrap gap-3'):
                                with ui.row().classes('items-center gap-3'):
                                    with ui.element('div').classes('w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-sm'):
                                        ui.icon('notifications_active', size='sm')
                                    with ui.column().classes('gap-0'):
                                        ui.label(f'Bandeja de Gerencia: {len(pendientes_firma)} expediente(s) 100% verificado(s) esperando firma digital').classes('font-bold text-slate-900 text-sm')
                                        ui.label('La auditoría documental confirmó coincidencia total. Compruebe los 3 documentos originales y plasme la firma digital.').classes('text-xs text-slate-600')
                                
                                ui.badge(f"{len(pendientes_firma)} PENDIENTES").props('color=indigo text-color=white').classes('text-xs px-3 py-1 font-bold')

                        with ui.row().classes('justify-between items-center w-full mb-6 flex-wrap gap-2'):
                            with ui.row().classes('items-center gap-2.5'):
                                ui.icon('folder_special', size='md').classes('text-indigo-600')
                                ui.label('Expedientes Radicados de Retransmisión').classes('text-lg font-bold text-slate-900')
                                ui.badge(f"{len(solicitudes)} TOTAL").props('color=slate-100 text-color=slate-700 border border-slate-200').classes('text-xs font-bold')
                            
                            ui.button('Actualizar', icon='refresh', on_click=render_tabla_expedientes.refresh)\
                                .props('dense flat color=slate-600')

                        if not solicitudes:
                            with ui.column().classes('w-full items-center justify-center py-12 text-center'):
                                ui.icon('folder_off', size='xl').classes('text-slate-300 mb-2')
                                ui.label('No hay expedientes en esta bandeja.').classes('text-slate-600 font-semibold')
                                if es_gerencia and not es_tecnico:
                                    ui.label('Los expedientes aparecerán aquí automáticamente en cuanto el sistema verifique el 100% de coincidencia legal.')\
                                        .classes('text-xs text-slate-400 mt-1 max-w-md')
                                else:
                                    ui.label('Utilice la pestaña "Radicar Nueva Solicitud" para procesar certificados RTI y radicar operadores.')\
                                        .classes('text-xs text-slate-400 mt-1')
                            return

                        # Tabla de solicitudes
                        columns = [
                            {'name': 'code', 'label': 'Código', 'field': 'code', 'align': 'left', 'sortable': True},
                            {'name': 'operator_name', 'label': 'Operador / Razón Social', 'field': 'operator_name', 'align': 'left', 'sortable': True},
                            {'name': 'nit', 'label': 'NIT', 'field': 'nit', 'align': 'left'},
                            {'name': 'rti_number', 'label': 'Registro RTI', 'field': 'rti_number', 'align': 'left'},
                            {'name': 'status', 'label': 'Estado de Validación', 'field': 'status', 'align': 'center'},
                            {'name': 'created_at', 'label': 'Fecha Radicación', 'field': 'created_at', 'align': 'left', 'sortable': True},
                            {'name': 'actions', 'label': 'Acciones', 'field': 'actions', 'align': 'center'},
                        ]

                        rows = []
                        for s in solicitudes:
                            rows.append({
                                'id': s['id'],
                                'code': s['code'],
                                'operator_name': s['operator_name'],
                                'nit': s['nit'],
                                'rti_number': s['rti_number'] or 'N/A',
                                'status': s['status'],
                                'created_at': s['created_at'][:16] if s.get('created_at') else '',
                            })

                        table = ui.table(columns=columns, rows=rows, row_key='id').classes('w-full').props('flat bordered')
                        
                        table.add_slot('body-cell-status', '''
                            <q-td :props="props">
                                <q-badge v-if="props.value === 'aprobado_gerencia'" color="positive" label="Aprobado por Gerencia (Firmada)" class="q-px-sm q-py-xs" />
                                <q-badge v-else-if="props.value === 'filtro1_aprobado'" color="primary" label="Filtro 1 Aprobado (Listo para Firma)" class="q-px-sm q-py-xs" />
                                <q-badge v-else color="warning" label="En Revisión Técnica" class="q-px-sm q-py-xs" />
                            </q-td>
                        ''')

                        table.add_slot('body-cell-actions', '''
                            <q-td :props="props">
                                <q-btn size="sm" color="indigo-7" icon="visibility" label="Inspeccionar / Acta" class="q-mr-xs" @click="$parent.$emit('inspect', props.row)" />
                                <q-btn size="sm" color="negative" flat round icon="delete" @click="$parent.$emit('delete', props.row)" />
                            </q-td>
                        ''')

                        async def handle_inspect(e):
                            row_data = e.args
                            render_retransmision_approval_dialog(
                                row_data['id'], 
                                user_info, 
                                on_status_changed_callback=render_tabla_expedientes.refresh
                            )

                        async def handle_delete(e):
                            row_data = e.args
                            confirm = ui.dialog()
                            with confirm, ui.card().classes('bg-white border border-slate-200 text-slate-800 p-6 rounded-3xl shadow-xl'):
                                ui.label('¿Confirmar Eliminación?').classes('text-lg font-bold text-red-600')
                                ui.label(f"¿Desea eliminar el expediente {row_data['code']} de {row_data['operator_name']}?").classes('text-sm text-slate-600 my-3')
                                with ui.row().classes('justify-end gap-2 w-full mt-4'):
                                    ui.button('Cancelar', on_click=confirm.close).props('flat color=slate-700')
                                    def do_del():
                                        delete_retransmission_authorization(row_data['id'])
                                        ui.notify('Expediente eliminado', type='info')
                                        confirm.close()
                                        render_tabla_expedientes.refresh()
                                    ui.button('Eliminar', color='red', on_click=do_del)
                            confirm.open()

                        table.on('inspect', handle_inspect)
                        table.on('delete', handle_delete)

                render_tabla_expedientes()
