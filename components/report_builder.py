from nicegui import ui
from datetime import datetime
import base64
import uuid
from database import (
    get_events_by_date, get_template_by_area, save_report_layout, get_report_layout,
    save_system_logo, get_system_logo
)
from components.report_preview import render_a4_paper 

def render_report_module(main_container, right_panel_container, user_info):
    """El Cerebro: Maneja el panel lateral derecho (Maquetador) y orquesta la vista previa con memoria."""
    main_container.clear()
    right_panel_container.clear()

    # ==========================================
    # EL MOTOR GRÁFICO (html2canvas-pro: Soporta OKLCH y no distorsiona el DOM)
    # ==========================================
    ui.run_javascript("""
        if (!document.getElementById('html2canvas-script')) {
            let s1 = document.createElement('script');
            s1.id = 'html2canvas-script';
            s1.src = 'https://cdn.jsdelivr.net/npm/html2canvas-pro/dist/html2canvas-pro.min.js';
            document.head.appendChild(s1);
        }
        if (!document.getElementById('jspdf-script')) {
            let s2 = document.createElement('script');
            s2.id = 'jspdf-script';
            s2.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
            document.head.appendChild(s2);
        }
    """)

    now = datetime.now()
    fecha_hoy_sql = now.strftime("%Y-%m-%d")
    fecha_legible = now.strftime("%d/%m/%Y")
    
    area_usuario = user_info.get('area', '')
    eventos_hoy = get_events_by_date(fecha_hoy_sql, area_usuario)
    template_config = get_template_by_area(area_usuario)

    opciones_campos = {
        '__nombre__': 'Nombre del Programa',
        '__horario__': 'Horario (Inicio - Fin)',
        '__locacion__': 'Locación (Si aplica)'
    }
    
    if template_config:
        for seccion in template_config.get('layout', []):
            for campo in seccion.get('campos', []):
                opciones_campos[campo['name_id']] = campo['label']

    estado_guardado = get_report_layout(area_usuario)
    
    if estado_guardado:
        estado_reporte = estado_guardado
    else:
        estado_reporte = {
            'titulo': f'Planilla Diaria - {area_usuario.upper()}',
            'logo_b64': None,
            'columnas': [
                {'id': str(uuid.uuid4()), 'titulo': 'DATOS PRINCIPALES', 'campos': ['__nombre__', '__horario__', '__locacion__']},
                {'id': str(uuid.uuid4()), 'titulo': 'ASIGNACIONES', 'campos': [k for k in opciones_campos.keys() if k not in ['__nombre__', '__horario__', '__locacion__']]}
            ]
        }

    # Cargar logo persistente del sistema si no tiene uno específico asignado
    if not estado_reporte.get('logo_b64'):
        estado_reporte['logo_b64'] = get_system_logo()

    # ==========================================
    # LÓGICA DE GUARDADO AUTOMÁTICO Y EXPANSIÓN
    # ==========================================
    def disparar_actualizacion():
        
        # Esta función permite ocultar/mostrar el panel derecho desde la vista previa
        def toggle_panel():
            if 'hidden' in right_panel_container.classes:
                right_panel_container.classes(remove='hidden')
            else:
                right_panel_container.classes(add='hidden')
                
        save_report_layout(area_usuario, estado_reporte)
        
        # Le enviamos el "control remoto" (toggle_panel) a la vista previa
        render_a4_paper(main_container, estado_reporte, eventos_hoy, opciones_campos, area_usuario, fecha_legible, user_info, toggle_panel)

    # ==========================================
    # PANEL DERECHO (EL MAQUETADOR)
    # ==========================================
    with right_panel_container.classes('flex flex-col h-full bg-white'):
        with ui.column().classes('w-full flex-grow p-6 overflow-y-auto gap-4'):
            
            with ui.row().classes('items-center gap-2 mb-2 border-b pb-4 w-full'):
                ui.icon('tune', size='md').classes('text-blue-600')
                ui.label('Maquetador').classes('text-xl font-bold text-gray-800')

            ui.label('1. Ajustes Generales').classes('text-xs font-bold text-gray-500 uppercase tracking-wider')

            logo_preview_container = ui.column().classes('w-full')

            def redibujar_logo_preview():
                logo_preview_container.clear()
                curr_logo = estado_reporte.get('logo_b64') or get_system_logo()
                if curr_logo:
                    with logo_preview_container:
                        with ui.row().classes('w-full items-center justify-between p-2 bg-slate-50 border border-slate-200 rounded-lg mt-1'):
                            ui.image(curr_logo).props('fit=contain').classes('h-10 max-w-[120px] object-contain')
                            def quitar_logo():
                                estado_reporte['logo_b64'] = None
                                save_system_logo('')
                                disparar_actualizacion()
                                redibujar_logo_preview()
                                ui.notify('Logo removido del sistema', type='info')
                            ui.button('Quitar Logo', icon='delete', on_click=quitar_logo).props('flat dense color=red size=sm')

            async def procesar_archivo_local(e):
                bytes_archivo = await e.file.read()
                base64_encoded = base64.b64encode(bytes_archivo).decode('utf-8')
                ext = e.file.name.lower().split('.')[-1]
                mime = 'image/png' if ext == 'png' else ('image/svg+xml' if ext == 'svg' else 'image/jpeg')
                data_uri = f"data:{mime};base64,{base64_encoded}"
                estado_reporte['logo_b64'] = data_uri
                save_system_logo(data_uri) # Persistencia permanente para todo el sistema
                disparar_actualizacion()
                redibujar_logo_preview()
                ui.notify('Logo aplicado y guardado permanentemente en el sistema', type='positive', icon='cloud_done')

            ui.upload(label='Cargar Logo Persistente (.PNG/.JPG)', on_upload=procesar_archivo_local, auto_upload=True).classes('w-full')
            redibujar_logo_preview()


            def actualizar_titulo_general(e):
                estado_reporte['titulo'] = e.value
                disparar_actualizacion()

            ui.input('Título Principal', value=estado_reporte['titulo'], on_change=actualizar_titulo_general).classes('w-full')

            ui.label('2. Columnas y Datos').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-4 border-b w-full pb-1')

            builder_col_container = ui.column().classes('w-full gap-2')

            def redibujar_panel_columnas():
                builder_col_container.clear()
                with builder_col_container:
                    for idx, col in enumerate(estado_reporte['columnas']):
                        with ui.card().classes('w-full p-4 bg-gray-50 border border-gray-200 shadow-sm'):
                            with ui.row().classes('w-full justify-between items-center mb-2'):
                                ui.label(f'Columna {idx + 1}').classes('font-bold text-blue-800 text-sm')
                                
                                def eliminar_col(c=col):
                                    estado_reporte['columnas'].remove(c)
                                    redibujar_panel_columnas()
                                    disparar_actualizacion()
                                ui.button(icon='delete', on_click=eliminar_col).props('flat color=red round size=sm').tooltip('Eliminar Columna')

                            def actualizar_titulo_col(e, c=col):
                                c['titulo'] = e.value
                                disparar_actualizacion()
                            ui.input('Título', value=col['titulo'], on_change=actualizar_titulo_col).classes('w-full mb-2')

                            def actualizar_campos_col(e, c=col):
                                c['campos'] = e.value
                                disparar_actualizacion()
                                
                            ui.select(
                                options=opciones_campos,
                                value=col['campos'],
                                multiple=True,
                                label='Datos a mostrar',
                                on_change=actualizar_campos_col
                            ).props('use-chips outlined').classes('w-full text-xs')

            redibujar_panel_columnas()

            def agregar_columna():
                if len(estado_reporte['columnas']) >= 5:
                    ui.notify('Máximo 5 columnas para evitar desborde en A4', type='warning')
                    return
                estado_reporte['columnas'].append({'id': str(uuid.uuid4()), 'titulo': 'Nueva Columna', 'campos': []})
                redibujar_panel_columnas()
                disparar_actualizacion()

            ui.button('Añadir Columna', icon='add_box', on_click=agregar_columna).classes('w-full bg-blue-100 text-blue-800 shadow-none hover:bg-blue-200 py-2 mt-2')

        # ==========================================
        # 3. LOS BOTONES DE DESCARGA
        # ==========================================
        with ui.column().classes('w-full p-6 border-t border-gray-200 bg-gray-50 shrink-0'):
            ui.label('3. Exportación').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mb-2')
            
            async def disparar_descarga_jpg():
                ui.notify('Generando fotografía de la primera hoja...', type='info', icon='image')
                js_code = """
                    if (typeof html2canvas === 'undefined') {
                        alert('El motor gráfico se está preparando.'); return;
                    }
                    // Tomamos siempre la primera hoja (ideal para JPG rápido)
                    let pages = document.querySelectorAll(".report-page");
                    if (pages.length === 0) return;
                    
                    html2canvas(pages[0], {scale: 2, useCORS: true, backgroundColor: '#ffffff'}).then(canvas => {
                        let link = document.createElement("a");
                        link.download = "Reporte_MediaHub_Pagina1.jpg";
                        link.href = canvas.toDataURL("image/jpeg", 0.95);
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }).catch(err => alert("Error capturando imagen: " + err));
                """
                await ui.run_javascript(js_code)

            async def disparar_descarga_pdf():
                ui.notify('Compilando PDF Multipágina... aguarda un momento', type='info', icon='picture_as_pdf')
                js_code = """
                    if (typeof window.jspdf === 'undefined' || typeof html2canvas === 'undefined') {
                        alert('El motor PDF se está preparando.'); return;
                    }
                    
                    async function generarPDF() {
                        let pdf = new window.jspdf.jsPDF("p", "mm", "a4");
                        let pages = document.querySelectorAll(".report-page");
                        
                        // Recorremos las hojas visibles y las pegamos en el PDF
                        for (let i = 0; i < pages.length; i++) {
                            let element = pages[i];
                            let canvas = await html2canvas(element, {scale: 2, useCORS: true, backgroundColor: '#ffffff'});
                            let imgData = canvas.toDataURL("image/jpeg", 0.95);
                            
                            let pdfWidth = pdf.internal.pageSize.getWidth();
                            let imgProps = pdf.getImageProperties(imgData);
                            let ratio = imgProps.width / imgProps.height;
                            let renderHeight = pdfWidth / ratio;
                            
                            pdf.addImage(imgData, "JPEG", 0, 0, pdfWidth, renderHeight);
                            
                            if (i < pages.length - 1) {
                                pdf.addPage();
                            }
                        }
                        
                        pdf.save("Reporte_Diario_MediaHub.pdf");
                    }
                    
                    generarPDF().catch(err => alert("Error compilando PDF: " + err));
                """
                await ui.run_javascript(js_code)
            
            ui.button('Descargar JPG (Solo Pág 1)', icon='image', on_click=disparar_descarga_jpg).classes('w-full bg-indigo-600 text-white font-bold mb-2 shadow-md')
            ui.button('Descargar PDF Completo', icon='picture_as_pdf', on_click=disparar_descarga_pdf).classes('w-full bg-red-600 text-white font-bold shadow-md')

    # Ejecución inicial
    disparar_actualizacion()