from nicegui import ui, app
from datetime import datetime
import json
import base64
import re
import unicodedata
from components.topbar import topbar
from components.sidebar import sidebar
from database import (
    get_user_by_usuario,
    get_delivery_act_by_code,
    sign_delivery_act,
    get_all_custom_records,
    get_custom_module
)

def render_acta_entrega_virtual_page(acta_code: str):
    """Página interactiva oficial para la visualización, validación y firma virtual de actas de entrega."""
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    ui.query('body').style('background-color: #f1f5f9; margin: 0; padding: 0;')
    topbar(user_info)
    sidebar(user_info)

    acta = get_delivery_act_by_code(acta_code)
    
    with ui.column().classes('w-full max-w-5xl mx-auto p-4 sm:p-6 gap-6'):
        if not acta:
            with ui.card().classes('w-full p-8 text-center items-center justify-center bg-white border border-rose-200 rounded-2xl shadow-sm'):
                ui.icon('error_outline', size='xl').classes('text-rose-500 mb-2')
                ui.label('Acta de Entrega No Encontrada').classes('text-xl font-bold text-slate-800')
                ui.label(f'No se encontró ningún acta registrada con el código: {acta_code}').classes('text-sm text-slate-500 max-w-md')
                ui.button('Volver al Inicio', icon='home', on_click=lambda: ui.navigate.to('/')).classes('bg-blue-600 text-white mt-4 rounded-xl')
            return

        estado = acta.get('estado', 'pendiente_firma')
        f_rec = acta.get('firma_receptor_b64')
        f_emi = acta.get('firma_emisor_b64')
        
        user_correo = (user_info.get('correo') or '').strip().lower()
        user_nom_comp = (user_info.get('nombre_completo') or f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}").strip().lower()
        user_nombres = (user_info.get('nombres') or '').strip().lower()
        user_usuario = (user_info.get('usuario') or '').strip().lower()
        user_area = (user_info.get('area') or user_info.get('area_encargada') or '').strip().lower()
        user_cargo = (user_info.get('cargo') or '').strip().lower()
        
        es_ingenieria = any(k in user_area or k in user_cargo or k in user_usuario or k in user_nom_comp for k in ['ingenieria', 'ingeniería', 'sistemas', 'admin', 'jose', 'zhayrus'])
        
        # Validación de receptor
        acta_rec_correo = (acta.get('receptor_correo') or '').strip().lower()
        acta_rec_nom = (acta.get('receptor_nombre') or '').strip().lower()
        
        es_receptor = False
        if user_correo and acta_rec_correo and user_correo == acta_rec_correo:
            es_receptor = True
        elif user_nom_comp and acta_rec_nom and (user_nom_comp in acta_rec_nom or acta_rec_nom in user_nom_comp):
            es_receptor = True
        elif user_nombres and acta_rec_nom and (user_nombres in acta_rec_nom):
            es_receptor = True
        else:
            def normalizar_palabras(s):
                s = unicodedata.normalize('NFKD', str(s or '')).encode('ASCII', 'ignore').decode('utf-8').lower()
                return set(re.findall(r'[a-z0-9]+', s))
            u_tok = normalizar_palabras(user_nom_comp)
            if user_usuario: u_tok.add(user_usuario)
            r_tok = normalizar_palabras(acta_rec_nom)
            com = u_tok.intersection(r_tok)
            if len(com) >= 2 or (len(u_tok) == 1 and u_tok.issubset(r_tok)):
                es_receptor = True

        # HEADER DEL ACTA VIRTUAL
        with ui.row().classes('w-full items-center justify-between bg-white p-5 rounded-2xl shadow-sm border border-slate-200 gap-4 flex-wrap'):
            with ui.row().classes('items-center gap-3'):
                with ui.element('div').classes('w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700'):
                    ui.icon('assignment_turned_in', size='md')
                with ui.column().classes('gap-0'):
                    ui.label(f"Acta Oficial: {acta['code']}").classes('text-lg font-black text-slate-900')
                    ui.label(f"Equipo: {acta['equipo_nombre']} • {acta.get('serial', 'Sin S/N')}").classes('text-xs text-slate-500 font-medium')
            
            with ui.row().classes('items-center gap-3'):
                if estado == 'completada':
                    with ui.row().classes('items-center gap-1.5 px-3 py-1.5 bg-emerald-50 border border-emerald-300 rounded-full text-emerald-800 text-xs font-bold'):
                        ui.icon('verified', size='xs').classes('text-emerald-600')
                        ui.label('100% FIRMADA Y COMPLETADA')
                elif estado == 'firmado_receptor':
                    with ui.row().classes('items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-300 rounded-full text-blue-800 text-xs font-bold'):
                        ui.icon('pending_actions', size='xs').classes('text-blue-600')
                        ui.label('FIRMADA POR RECEPTOR • ESPERA INGENIERÍA')
                elif estado == 'firmado_ingenieria':
                    with ui.row().classes('items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-300 rounded-full text-amber-800 text-xs font-bold'):
                        ui.icon('pending_actions', size='xs').classes('text-amber-600')
                        ui.label('FIRMADA POR INGENIERÍA • ESPERA RECEPTOR')
                else:
                    with ui.row().classes('items-center gap-1.5 px-3 py-1.5 bg-rose-50 border border-rose-300 rounded-full text-rose-800 text-xs font-bold'):
                        ui.icon('edit', size='xs').classes('text-rose-600')
                        ui.label('PENDIENTE DE FIRMAS')

                ui.button('Ver Reporte Oficial', icon='print', on_click=lambda: ui.navigate.to(f"/reportes_inventario/{acta.get('module_id', 'system_inventory')}?record_id={acta['record_id']}", new_tab=True))\
                    .props('flat color=indigo dense').classes('text-xs font-bold')

        # DETALLES Y CLÁUSULAS INSTITUCIONALES DEL ACTA
        with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-sm gap-4'):
            with ui.row().classes('items-center justify-between border-b pb-3'):
                ui.label('DECLARACIÓN Y CONDICIONES DE ASIGNACIÓN').classes('font-bold text-xs uppercase tracking-wider text-slate-700')
                ui.label(f"Fecha de emisión: {acta.get('created_at', '')[:10]}").classes('text-xs text-slate-400')

            # Cláusula de Entrega
            with ui.column().classes('p-4 bg-slate-50 border border-slate-200 rounded-xl gap-2'):
                ui.label('Cláusula de Entrega:').classes('text-xs font-bold text-slate-800')
                ui.label(f"Por medio de la presente la FUNDACIÓN ICTUS hace entrega e inventario del equipo {acta['equipo_nombre']} al colaborador {acta['receptor_nombre']}, identificado con {acta.get('receptor_correo', 'correo institucional')}, para el desempeño exclusivo de sus funciones laborales.")\
                    .classes('text-xs text-slate-600 leading-relaxed text-justify')

            # Tarjetas resumen de las partes
            with ui.row().classes('w-full gap-4 flex-wrap sm:flex-nowrap'):
                # Receptor
                with ui.column().classes('w-full sm:w-1/2 p-3 bg-blue-50/70 border border-blue-200 rounded-xl gap-1'):
                    ui.label('👤 Responsable / Receptor:').classes('text-[11px] font-bold text-blue-900')
                    ui.label(acta['receptor_nombre']).classes('text-xs font-bold text-slate-800')
                    ui.label(f"Cargo: {acta.get('receptor_cargo') or 'Colaborador'}").classes('text-[11px] text-slate-600')
                    ui.label(f"Correo: {acta.get('receptor_correo') or 'Sin correo registrado'}").classes('text-[10px] text-slate-500')

                # Emisor
                with ui.column().classes('w-full sm:w-1/2 p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl gap-1'):
                    ui.label('🏢 Entregado Por (Ingeniería):').classes('text-[11px] font-bold text-indigo-900')
                    ui.label(acta.get('emisor_nombre') or 'Departamento de Ingeniería').classes('text-xs font-bold text-slate-800')
                    ui.label(f"Área: {acta.get('emisor_cargo') or 'Ingeniería y Sistemas'}").classes('text-[11px] text-slate-600')
                    ui.label("Fundación Ictus - Canal Teleamiga").classes('text-[10px] text-slate-500')

            # Cláusula de Compromiso
            with ui.column().classes('p-3 bg-amber-50/60 border border-amber-200 rounded-xl gap-1 text-[11px] text-amber-900 leading-relaxed'):
                ui.label('Compromiso del Colaborador:').classes('font-bold')
                ui.label('1. Recibe los elementos en perfecto estado de funcionamiento y conservación.\n2. Se compromete a darles un uso exclusivamente profesional y velar por su cuidado.\n3. En caso de pérdida o daño por negligencia, asumirá la reposición del bien.')

        # ESTADO ACTUAL DE LAS FIRMAS VIRTUALES
        with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-sm gap-4'):
            ui.label('ESTADO DE FIRMAS VIRTUALES').classes('font-bold text-xs uppercase tracking-wider text-slate-700 border-b pb-2')

            with ui.row().classes('w-full justify-around items-start gap-6 flex-wrap'):
                # Firma 1: Receptor
                with ui.column().classes('items-center w-64 p-4 border rounded-xl gap-2 ' + ('bg-emerald-50/60 border-emerald-300' if f_rec else 'bg-slate-50 border-dashed border-slate-300')):
                    ui.label('FIRMA DE RECIBIDO').classes('text-xs font-bold text-slate-800')
                    if f_rec:
                        ui.image(f_rec).props('fit=contain').classes('h-16 w-48 object-contain bg-white rounded p-1 border border-emerald-200')
                        ui.label(f"✓ Firmado digitalmente").classes('text-[10px] font-bold text-emerald-700')
                        if acta.get('firma_receptor_fecha'):
                            ui.label(acta['firma_receptor_fecha']).classes('text-[9px] text-slate-500 font-mono')
                    else:
                        with ui.element('div').classes('h-16 w-48 flex items-center justify-center text-slate-400 bg-white rounded border border-slate-200'):
                            ui.label('Firma Pendiente').classes('text-xs italic')
                    ui.label(acta['receptor_nombre']).classes('text-xs font-semibold text-slate-700 text-center')

                # Firma 2: Ingeniería
                with ui.column().classes('items-center w-64 p-4 border rounded-xl gap-2 ' + ('bg-indigo-50/60 border-indigo-300' if f_emi else 'bg-slate-50 border-dashed border-slate-300')):
                    ui.label('ENTREGADO POR').classes('text-xs font-bold text-slate-800')
                    if f_emi:
                        ui.image(f_emi).props('fit=contain').classes('h-16 w-48 object-contain bg-white rounded p-1 border border-indigo-200')
                        ui.label(f"✓ Firmado digitalmente").classes('text-[10px] font-bold text-indigo-700')
                        if acta.get('firma_emisor_fecha'):
                            ui.label(acta['firma_emisor_fecha']).classes('text-[9px] text-slate-500 font-mono')
                    else:
                        with ui.element('div').classes('h-16 w-48 flex items-center justify-center text-slate-400 bg-white rounded border border-slate-200'):
                            ui.label('Firma Pendiente').classes('text-xs italic')
                    ui.label(acta.get('emisor_nombre', 'Ingeniería')).classes('text-xs font-semibold text-slate-700 text-center')

        # ESTACIÓN INTERACTIVA DE FIRMA (SI FALTA ALGUNA FIRMA)
        puedo_firmar_receptor = (not f_rec) and (es_receptor or es_ingenieria)
        puedo_firmar_ingenieria = (not f_emi) and es_ingenieria

        if puedo_firmar_receptor or puedo_firmar_ingenieria:
            with ui.card().classes('w-full p-6 bg-gradient-to-br from-indigo-50/80 to-blue-50/80 border-2 border-indigo-300 rounded-2xl shadow-md gap-4'):
                with ui.row().classes('items-center justify-between w-full'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('draw', size='sm').classes('text-indigo-600')
                        ui.label('Estación de Firma Digital').classes('text-base font-black text-slate-900')
                    
                    # Selector de Rol para firmar si tiene ambos permisos
                    opciones_rol = {}
                    if puedo_firmar_receptor:
                        opciones_rol['receptor'] = f"Firmar como Receptor ({acta['receptor_nombre']})"
                    if puedo_firmar_ingenieria:
                        opciones_rol['emisor'] = "Firmar como Emisor (Ingeniería y Sistemas)"
                        
                    rol_default = 'receptor' if puedo_firmar_receptor else 'emisor'
                    rol_select = ui.select(options=opciones_rol, value=rol_default).classes('text-xs w-64 bg-white rounded-lg').props('outlined dense')

                # Contenedor para la firma (base64)
                firma_state = {'b64': None}
                
                with ui.tabs().classes('w-full text-xs font-bold') as tabs_firma:
                    tab_dibujar = ui.tab('✍️ Dibujar Firma en Pantalla')
                    tab_subir = ui.tab('📁 Cargar Imagen de Firma')

                with ui.tab_panels(tabs_firma, value=tab_dibujar).classes('w-full bg-transparent p-0'):
                    
                    # PESTAÑA 1: DIBUJAR FIRMA (CANVAS INTERACTIVO)
                    with ui.tab_panel(tab_dibujar).classes('p-0 gap-3'):
                        ui.label('Utiliza el mouse, puntero o pantalla táctil para dibujar tu firma en el recuadro blanco:').classes('text-xs text-slate-600')
                        
                        canvas_id = f"canvas-signature-{acta['id']}"
                        ui.html(f'''
                            <div style="position: relative; width: 100%; max-width: 500px; height: 180px; background: #ffffff; border: 2px dashed #94a3b8; border-radius: 12px; overflow: hidden; touch-action: none; margin: 0 auto;">
                                <canvas id="{canvas_id}" width="500" height="180" style="display: block; width: 100%; height: 100%; cursor: crosshair;"></canvas>
                                <div style="position: absolute; bottom: 8px; left: 12px; font-size: 10px; color: #94a3b8; pointer-events: none; font-weight: bold;">
                                    Línea de firma digital
                                </div>
                            </div>
                        ''')
                        
                        # Script de inicialización de dibujo en el canvas
                        ui.run_javascript(f'''
                            (function() {{
                                const canvas = document.getElementById("{canvas_id}");
                                if (!canvas) return;
                                const ctx = canvas.getContext("2d");
                                ctx.lineWidth = 2.5;
                                ctx.lineCap = "round";
                                ctx.lineJoin = "round";
                                ctx.strokeStyle = "#1e293b";
                                
                                let drawing = false;
                                
                                function getPos(e) {{
                                    const rect = canvas.getBoundingClientRect();
                                    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                                    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                                    return {{
                                        x: (clientX - rect.left) * (canvas.width / rect.width),
                                        y: (clientY - rect.top) * (canvas.height / rect.height)
                                    }};
                                }}
                                
                                function start(e) {{
                                    drawing = true;
                                    const pos = getPos(e);
                                    ctx.beginPath();
                                    ctx.moveTo(pos.x, pos.y);
                                    e.preventDefault();
                                }}
                                
                                function move(e) {{
                                    if (!drawing) return;
                                    const pos = getPos(e);
                                    ctx.lineTo(pos.x, pos.y);
                                    ctx.stroke();
                                    e.preventDefault();
                                }}
                                
                                function stop(e) {{
                                    drawing = false;
                                }}
                                
                                canvas.addEventListener("mousedown", start);
                                canvas.addEventListener("mousemove", move);
                                window.addEventListener("mouseup", stop);
                                
                                canvas.addEventListener("touchstart", start, {{passive: false}});
                                canvas.addEventListener("touchmove", move, {{passive: false}});
                                window.addEventListener("touchend", stop);
                            }})();
                        ''')
                        
                        with ui.row().classes('w-full justify-center gap-3 mt-2'):
                            async def limpiar_canvas():
                                await ui.run_javascript(f'''
                                    const c = document.getElementById("{canvas_id}");
                                    if (c) {{
                                        const ctx = c.getContext("2d");
                                        ctx.clearRect(0, 0, c.width, c.height);
                                    }}
                                ''')
                                firma_state['b64'] = None
                                ui.notify('Lienzo de firma limpiado', type='info')
                                
                            ui.button('Limpiar Trazo', icon='delete_sweep', on_click=limpiar_canvas).props('flat dense color=red size=sm')

                    # PESTAÑA 2: CARGAR IMAGEN
                    with ui.tab_panel(tab_subir).classes('p-0 gap-3'):
                        ui.label('Sube un archivo de imagen (.PNG transparente recomendado o .JPG) de tu firma:').classes('text-xs text-slate-600')
                        
                        preview_upload_container = ui.column().classes('w-full items-center')
                        
                        async def handle_upload(e):
                            bytes_f = await e.file.read()
                            b64 = f"data:image/png;base64,{base64.b64encode(bytes_f).decode('utf-8')}"
                            firma_state['b64'] = b64
                            preview_upload_container.clear()
                            with preview_upload_container:
                                ui.image(b64).props('fit=contain').classes('h-20 w-48 object-contain bg-white rounded border border-indigo-200 mt-2 p-1')
                            ui.notify('Imagen de firma cargada', type='positive')
                            
                        ui.upload(label='Seleccionar Firma (.PNG/.JPG)', on_upload=handle_upload, auto_upload=True)\
                            .props('accept=.png,.jpg,.jpeg').classes('w-full max-w-sm mx-auto')

                # Botón de confirmación final de la firma
                async def confirmar_firma():
                    selected_tab = tabs_firma.value
                    b64_final = None
                    
                    if selected_tab == tab_dibujar:
                        # Extraer imagen del canvas
                        js_extract = f'''
                            (() => {{
                                const c = document.getElementById("{canvas_id}");
                                if (!c) return "";
                                // Comprobar si está en blanco
                                const blank = document.createElement("canvas");
                                blank.width = c.width;
                                blank.height = c.height;
                                if (c.toDataURL() === blank.toDataURL()) return "EMPTY";
                                return c.toDataURL("image/png");
                            }})();
                        '''
                        res = await ui.run_javascript(js_extract)
                        if not res or res == "EMPTY":
                            ui.notify('Por favor dibuja tu firma antes de confirmar', type='warning')
                            return
                        b64_final = res
                    else:
                        if not firma_state.get('b64'):
                            ui.notify('Por favor carga una imagen de firma válida', type='warning')
                            return
                        b64_final = firma_state['b64']
                        
                    rol = rol_select.value
                    nom_firmante = user_info.get('nombres') or user_info.get('usuario') or 'Usuario'
                    if rol == 'receptor':
                        nom_firmante = acta['receptor_nombre']
                    else:
                        nom_firmante = user_info.get('nombres') or 'Ingeniería y Sistemas'
                        
                    succ, msg, updated = sign_delivery_act(acta['code'], rol, b64_final, nom_firmante)
                    if succ:
                        ui.notify('¡Firma registrada exitosamente en el acta oficial!', type='positive', icon='check_circle')
                        ui.navigate.to(f"/acta_entrega/{acta['code']}")
                    else:
                        ui.notify(msg, type='negative')

                with ui.row().classes('w-full justify-end pt-3 border-t border-indigo-200'):
                    ui.button('Confirmar y Estampar Firma Oficial', icon='verified', on_click=confirmar_firma)\
                        .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 px-6 rounded-xl shadow-md text-xs')

        elif estado == 'completada':
            with ui.card().classes('w-full p-6 bg-emerald-50 border border-emerald-200 rounded-2xl text-center items-center justify-center gap-3'):
                ui.icon('verified_user', size='xl').classes('text-emerald-600')
                ui.label('¡Acta 100% Firmada y Legalizada!').classes('text-lg font-black text-emerald-900')
                ui.label('Este documento cuenta con las firmas digitales válidas del colaborador receptor y del Departamento de Ingeniería.').classes('text-xs text-emerald-700 max-w-md')
                with ui.row().classes('gap-3'):
                    ui.button('Ver / Descargar PDF Oficial', icon='picture_as_pdf', on_click=lambda: ui.navigate.to(f"/reportes_inventario/{acta.get('module_id', 'system_inventory')}?record_id={acta['record_id']}", new_tab=True))\
                        .classes('bg-emerald-600 text-white font-bold px-4 py-2 rounded-xl text-xs shadow-sm')
