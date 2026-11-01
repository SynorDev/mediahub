import os
import zipfile
import xml.etree.ElementTree as ET
from nicegui import ui
from database import (
    get_acta_retransmision_template,
    save_acta_retransmision_template,
    DEFAULT_ACTA_RETRANSMISION_TEMPLATE,
    get_system_logo
)
from components.retransmision_acta_generator import formatear_texto_plantilla, markdown_inline_to_html

RUTA_DOCX_DEFECTO = r"C:\Sistemas Desarrollo\Gestion\MediaHub\ejemplos\AUTORIZACION DE RETRANSMISION ACCAPP_Telehub 1.docx"


def extraer_plantilla_desde_docx(ruta_docx: str) -> dict | None:
    """Extrae los párrafos clave desde un archivo DOCX oficial."""
    if not os.path.exists(ruta_docx):
        return None
    try:
        with zipfile.ZipFile(ruta_docx) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            paras = []
            for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                t = ''.join([node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]).strip()
                if t:
                    paras.append(t)
            
            # Mapeo según estructura observada del documento
            resultado = dict(DEFAULT_ACTA_RETRANSMISION_TEMPLATE)
            if len(paras) >= 3:
                resultado['titulo'] = paras[0]
                resultado['entidad'] = paras[1]
                resultado['nit_entidad'] = paras[2]

            for p in paras:
                if 'operadora de la señal' in p.lower() or 'representada por' in p.lower() or 'entidad sin ánimo de lucro' in p.lower():
                    resultado['texto_apertura'] = (
                        'La Fundación Ictus, entidad sin ánimo de lucro, operadora de la señal del Canal Teleamiga, '
                        'NIT 830.080.615-2, representada por {gerente_nombre}, en su calidad de Representante Legal '
                        'y Gerente de la institución, se permite autorizar a:'
                    )
                elif 'cubre todas sus cabeceras' in p.lower() or 'todas sus cabeceras actuales' in p.lower():
                    resultado['clausula_cabeceras'] = p
                elif 'se expide a los' in p.lower() or 'se expide en fecha' in p.lower():
                    # Preservamos placeholder de fecha y vigencia
                    resultado['clausula_vigencia'] = (
                        'Esta autorización se expide a los {fecha_legal}, por un periodo de {periodo_vigencia}, '
                        'contando a partir de la fecha de expedición.'
                    )
                elif 'medio actual para la recepción' in p.lower():
                    resultado['clausula_tecnica'] = p
                elif 'atentamente' in p.lower():
                    resultado['despedida'] = p

            return resultado
    except Exception as e:
        print(f"Error extrayendo DOCX: {e}")
        return None


def render_acta_template_admin():
    """
    Renderiza el panel de administración para editar, personalizar y previsualizar
    en tiempo real la plantilla oficial de Autorización de Retransmisión.
    """
    current_tpl = get_acta_retransmision_template()
    logo_sistema = get_system_logo()

    with ui.column().classes('w-full gap-6 pb-12'):
        
        # --- ENCABEZADO DE LA SECCIÓN ---
        with ui.row().classes('w-full justify-between items-center bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex-wrap gap-4'):
            with ui.row().classes('items-center gap-3.5'):
                with ui.element('div').classes('w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-xs'):
                    ui.icon('assignment', size='md')
                with ui.column().classes('gap-0.5'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label('Plantilla Oficial: Autorización de Retransmisión').classes('text-xl font-black text-slate-800 tracking-tight')
                        ui.badge('Canal Teleamiga', color='indigo').classes('text-[10px] font-bold uppercase tracking-wider px-2 py-0.5')
                    ui.label('Edita los textos, personerías legales, cláusulas y fórmulas del documento sin tocar código fuente.').classes('text-xs text-slate-500')

            with ui.row().classes('items-center gap-2.5'):
                btn_recargar_docx = ui.button('Cargar desde DOCX', icon='description')\
                    .props('outline color=indigo-8 size=sm').classes('px-3 rounded-xl font-bold text-xs')
                btn_reset = ui.button('Restablecer Defecto', icon='restart_alt')\
                    .props('outline color=slate-7 size=sm').classes('px-3 rounded-xl font-bold text-xs')
                btn_guardar = ui.button('Guardar Cambios', icon='save')\
                    .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-4 py-2 rounded-xl text-xs shadow-md transition-all')

        # --- GUÍA DE VARIABLES DINÁMICAS DISPONIBLES ---
        with ui.card().classes('w-full p-4 bg-gradient-to-r from-indigo-50/70 to-slate-50 border border-indigo-100/80 rounded-2xl shadow-xs'):
            with ui.row().classes('items-center gap-2 mb-2'):
                ui.icon('info', size='xs').classes('text-indigo-600')
                ui.label('Variables y Etiquetas Dinámicas Disponibles').classes('text-xs font-bold text-indigo-950')
                ui.label('(puedes incluirlas en los campos de texto y se reemplazarán automáticamente en cada acta emitida)').classes('text-[11px] text-slate-500')
            
            with ui.row().classes('gap-2 flex-wrap items-center'):
                tags = [
                    ('{gerente_nombre}', 'Usuario autorizado categoría Gerencia (ej: Claudia Garzon)'),
                    ('{usuario_autorizado}', 'Alias para usuario autorizado categoría Gerencia'),
                    ('{gerente_cargo}', 'Cargo del usuario de Gerencia'),
                    ('{fecha_legal}', 'Fecha legal extensa (ej: veintinueve (29) días del mes de septiembre...)'),
                    ('{periodo_vigencia}', 'Vigencia (ej: un (1) año)'),
                    ('{gerente_cel}', 'Celular de contacto'),
                    ('{op_name}', 'Nombre o Razón Social del operador'),
                    ('{op_nit}', 'NIT del operador'),
                    ('{codigo_acta}', 'Número oficial de radicado'),
                ]
                for tag, desc in tags:
                    with ui.row().classes('items-center gap-1 bg-white border border-indigo-200/60 px-2.5 py-1 rounded-lg shadow-2xs'):
                        ui.label(tag).classes('font-mono font-bold text-indigo-700 text-[11px]')
                        ui.label(f": {desc}").classes('text-[11px] text-slate-600')

        # --- DISTRIBUCIÓN PRINCIPAL EN 2 COLUMNAS (FORMULARIO + VISTA PREVIA EN VIVO) ---
        with ui.row().classes('w-full items-start gap-6 flex-col xl:flex-row flex-nowrap'):
            
            # ==========================================
            # COLUMNA 1: FORMULARIO DE EDICIÓN (60%)
            # ==========================================
            with ui.column().classes('w-full xl:w-7/12 gap-5'):
                
                # SECCIÓN 1: ENCABEZADO
                with ui.card().classes('w-full p-5 bg-white border border-slate-200 rounded-2xl shadow-xs'):
                    with ui.row().classes('items-center gap-2 mb-3 pb-2 border-b border-slate-100'):
                        ui.icon('title', size='sm').classes('text-indigo-600')
                        ui.label('1. Encabezado y Título Institucional').classes('font-black text-slate-800 text-sm tracking-tight')

                    f_titulo = ui.input('Título Principal del Documento', value=current_tpl.get('titulo', ''))\
                        .classes('w-full mb-3 text-sm font-semibold').props('outlined dense')
                    
                    with ui.row().classes('w-full gap-3 flex-col sm:flex-row'):
                        f_entidad = ui.input('Entidad Titular / Propietaria', value=current_tpl.get('entidad', ''))\
                            .classes('flex-1 text-sm').props('outlined dense')
                        f_nit = ui.input('NIT de la Entidad', value=current_tpl.get('nit_entidad', ''))\
                            .classes('flex-1 text-sm font-mono').props('outlined dense')

                # SECCIÓN 2: PÁRRAFO DE APERTURA Y PERSONERÍA
                with ui.card().classes('w-full p-5 bg-white border border-slate-200 rounded-2xl shadow-xs'):
                    with ui.row().classes('items-center justify-between gap-2 mb-3 pb-2 border-b border-slate-100'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('gavel', size='sm').classes('text-indigo-600')
                            ui.label('2. Párrafo de Apertura Legal y Personería').classes('font-black text-slate-800 text-sm tracking-tight')
                        ui.badge('Dinámico Gerencia', color='emerald').classes('text-[10px] font-bold')

                    ui.label('Usa {gerente_nombre} o {usuario_autorizado} para insertar al usuario autorizado en categoría Gerencia.')\
                        .classes('text-xs text-slate-500 mb-2')

                    f_apertura = ui.textarea(
                        'Texto de Personería y Autorización Legal',
                        value=current_tpl.get('texto_apertura', '')
                    ).classes('w-full text-xs font-normal').props('outlined autogrow rows=4')

                # SECCIÓN 3: CLÁUSULAS Y TÉRMINOS
                with ui.card().classes('w-full p-5 bg-white border border-slate-200 rounded-2xl shadow-xs'):
                    with ui.row().classes('items-center gap-2 mb-3 pb-2 border-b border-slate-100'):
                        ui.icon('rule', size='sm').classes('text-indigo-600')
                        ui.label('3. Cláusulas de Cobertura, Vigencia y Recepción Técnica').classes('font-black text-slate-800 text-sm tracking-tight')

                    f_cabeceras = ui.input('Cláusula de Cabeceras Autorizadas', value=current_tpl.get('clausula_cabeceras', ''))\
                        .classes('w-full mb-3 text-xs').props('outlined dense')
                    
                    with ui.row().classes('w-full gap-3 flex-col sm:flex-row mb-3'):
                        f_vigencia_periodo = ui.input('Periodo de Vigencia Predeterminado', value=current_tpl.get('periodo_vigencia', 'un (1) año'))\
                            .classes('w-full sm:w-1/3 text-xs').props('outlined dense')
                        f_vigencia = ui.textarea('Cláusula de Fecha de Expedición y Periodo', value=current_tpl.get('clausula_vigencia', ''))\
                            .classes('flex-1 text-xs').props('outlined autogrow rows=2')

                    f_tecnica = ui.input('Cláusula de Medios de Recepción (Satélite / IP)', value=current_tpl.get('clausula_tecnica', ''))\
                        .classes('w-full mb-3 text-xs').props('outlined dense')

                    f_despedida = ui.input('Fórmula de Despedida', value=current_tpl.get('despedida', 'Atentamente,'))\
                        .classes('w-full text-xs').props('outlined dense')

                # SECCIÓN 4: FIRMANTE PREDETERMINADO Y PIE DE PÁGINA
                with ui.card().classes('w-full p-5 bg-white border border-slate-200 rounded-2xl shadow-xs'):
                    with ui.row().classes('items-center gap-2 mb-3 pb-2 border-b border-slate-100'):
                        ui.icon('badge', size='sm').classes('text-indigo-600')
                        ui.label('4. Firmante Predeterminado y Pie de Página').classes('font-black text-slate-800 text-sm tracking-tight')

                    with ui.row().classes('w-full gap-3 flex-col sm:flex-row mb-3'):
                        f_firmante = ui.input('Nombre Firmante', value=current_tpl.get('nombre_firmante', 'CLAUDIA GARZON'))\
                            .classes('flex-1 text-xs uppercase font-bold').props('outlined dense')
                        f_cargo = ui.input('Cargo Firmante', value=current_tpl.get('cargo_firmante', 'Gerente del Canal'))\
                            .classes('flex-1 text-xs').props('outlined dense')
                        f_cel = ui.input('Celular Contacto', value=current_tpl.get('celular_firmante', '3138932021'))\
                            .classes('flex-1 text-xs font-mono').props('outlined dense')

                    f_pie = ui.input('Texto de Pie de Página / Seguridad', value=current_tpl.get('pie_pagina', ''))\
                        .classes('w-full text-xs font-mono').props('outlined dense')

            # ==========================================
            # COLUMNA 2: VISTA PREVIA EN TIEMPO REAL (40%)
            # ==========================================
            with ui.column().classes('w-full xl:w-5/12 gap-3 sticky top-4'):
                
                with ui.row().classes('w-full justify-between items-center bg-white px-4 py-3 rounded-2xl border border-slate-200 shadow-xs'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('preview', size='xs').classes('text-indigo-600')
                        ui.label('Vista Previa en Tiempo Real').classes('font-black text-slate-800 text-xs tracking-tight')
                    ui.badge('Hoja Carta Física', color='slate').classes('text-[10px] font-bold')

                # Tarjeta que simula la Hoja Carta con proporciones exactas
                pv_container = ui.column().classes(
                    'w-full bg-white shadow-xl rounded-2xl p-6 sm:p-8 border border-slate-300 '
                    'text-slate-900 min-h-[750px] flex flex-col justify-between overflow-x-hidden'
                )

                def actualizar_vista_previa():
                    pv_container.clear()
                    
                    # Variables simuladas para la vista previa
                    mock_vars = {
                        'fecha_legal': 'veintinueve (29) días del mes de septiembre del año dos mil veintiséis (2026)',
                        'periodo_vigencia': f_vigencia_periodo.value or 'un (1) año',
                        'gerente_nombre': f_firmante.value or 'Claudia Garzon',
                        'usuario_autorizado': f_firmante.value or 'Claudia Garzon',
                        'usuario_gerencia': f_firmante.value or 'Claudia Garzon',
                        'gerente_cargo': f_cargo.value or 'Gerente del Canal',
                        'cargo_gerencia': f_cargo.value or 'Gerente del Canal',
                        'gerente_cel': f_cel.value or '3138932021',
                        'op_name': 'ASOCIACION COMUNITARIA DE COOPROPIETARIOS ANTENA PARABOLICA DE PLANADAS',
                        'op_nit': '809008794',
                        'op_address': 'CR 6 NO 5 - 64 BRR CENTRO',
                        'municipio': 'PLANADAS, TOLIMA',
                        'departamento': 'TOLIMA',
                        'rep_name': 'JOSE TOMAS RODRIGUEZ FAGUA',
                        'rep_doc': '17192886',
                        'notif_email': 'notificaciones@asociaci.com.co',
                        'codigo_acta': 'AUT-RET-2026-0003',
                    }

                    txt_titulo = formatear_texto_plantilla(f_titulo.value, mock_vars)
                    txt_entidad = formatear_texto_plantilla(f_entidad.value, mock_vars)
                    txt_nit = formatear_texto_plantilla(f_nit.value, mock_vars)
                    txt_apertura = formatear_texto_plantilla(f_apertura.value, mock_vars)
                    txt_cabeceras = formatear_texto_plantilla(f_cabeceras.value, mock_vars)
                    txt_vigencia = formatear_texto_plantilla(f_vigencia.value, mock_vars)
                    txt_tecnica = formatear_texto_plantilla(f_tecnica.value, mock_vars)
                    txt_despedida = formatear_texto_plantilla(f_despedida.value, mock_vars)
                    txt_pie = formatear_texto_plantilla(f_pie.value, mock_vars)

                    with pv_container:
                        with ui.column().classes('w-full flex-grow flex flex-col justify-start'):
                            # Logo
                            if logo_sistema:
                                ui.image(logo_sistema).props('fit=contain').classes('w-32 h-12 object-contain mb-3')
                            else:
                                ui.label('CANAL TELEAMIGA').classes('font-black text-sm text-slate-800 tracking-wider mb-2')

                            # Títulos
                            with ui.column().classes('w-full items-center text-center gap-0 mb-4'):
                                ui.label(txt_titulo).classes('text-xs font-black tracking-wide text-slate-900 uppercase')
                                ui.label(txt_entidad).classes('text-[11px] font-black tracking-wide text-slate-900 uppercase')
                                ui.label(txt_nit).classes('text-[10px] font-bold text-slate-700')

                            # Apertura legal
                            ui.markdown(txt_apertura).classes('text-[10px] text-justify leading-relaxed text-slate-800 mb-3')

                            # Tabla Operador
                            with ui.column().classes('w-full pl-3 gap-0.5 mb-3 text-[10px] text-slate-900 leading-tight'):
                                for label, val in [
                                    ('Nombre o Razón Social:', mock_vars['op_name']),
                                    ('NIT-Número Identificación Tributaria:', mock_vars['op_nit']),
                                    ('Dirección:', mock_vars['op_address']),
                                    ('Municipio:', mock_vars['municipio']),
                                    ('Departamento:', mock_vars['departamento']),
                                    ('País:', 'COLOMBIA'),
                                    ('Representante Legal:', mock_vars['rep_name']),
                                    ('Documento de Identidad No:', mock_vars['rep_doc']),
                                    ('Datos de Notificación:', mock_vars['notif_email']),
                                ]:
                                    with ui.row().classes('gap-1'):
                                        ui.label(label).classes('font-bold text-slate-800')
                                        ui.label(val).classes('font-semibold')

                            # Cláusulas
                            ui.markdown(txt_cabeceras).classes('text-[10px] text-justify leading-relaxed text-slate-800 mb-2')
                            ui.markdown(txt_vigencia).classes('text-[10px] text-justify leading-relaxed text-slate-800 mb-2')
                            ui.markdown(txt_tecnica).classes('text-[10px] text-justify leading-relaxed text-slate-800 mb-3')
                            ui.label(txt_despedida).classes('text-[10px] text-slate-800 mb-3')

                            # Firma
                            with ui.column().classes('w-48 items-start mb-2'):
                                with ui.element('div').classes('h-10 w-44 border-b border-slate-700 flex items-end justify-center mb-1'):
                                    ui.label('Claudia Garzón M.').classes('italic text-slate-600 font-serif text-[11px]')
                                ui.label(mock_vars['gerente_nombre']).classes('text-[10px] font-black text-slate-900 uppercase')
                                ui.label(mock_vars['gerente_cargo']).classes('text-[9px] text-slate-600')
                                ui.label(f"CEL: {mock_vars['gerente_cel']}").classes('text-[8px] text-slate-500 font-mono')

                        # Pie de página
                        with ui.row().classes('w-full justify-between items-center border-t border-slate-200 pt-2 text-[8px] text-slate-400 font-mono'):
                            ui.label(txt_pie)
                            ui.label('Página 1 de 1')

                # Vinculación de eventos de cambio de texto para actualizar la vista previa en vivo
                for inp in [f_titulo, f_entidad, f_nit, f_apertura, f_cabeceras, f_vigencia_periodo, f_vigencia, f_tecnica, f_despedida, f_firmante, f_cargo, f_cel, f_pie]:
                    inp.on('update:model-value', lambda _: actualizar_vista_previa())

                # Cargar vista previa inicial
                actualizar_vista_previa()

        # --- LÓGICA DE LOS BOTONES DE ACCIÓN ---
        def ejecutar_guardado():
            nuevo_dict = {
                'titulo': f_titulo.value.strip(),
                'entidad': f_entidad.value.strip(),
                'nit_entidad': f_nit.value.strip(),
                'texto_apertura': f_apertura.value.strip(),
                'clausula_cabeceras': f_cabeceras.value.strip(),
                'periodo_vigencia': f_vigencia_periodo.value.strip() or 'un (1) año',
                'clausula_vigencia': f_vigencia.value.strip(),
                'clausula_tecnica': f_tecnica.value.strip(),
                'despedida': f_despedida.value.strip(),
                'nombre_firmante': f_firmante.value.strip().upper(),
                'cargo_firmante': f_cargo.value.strip(),
                'celular_firmante': f_cel.value.strip(),
                'pie_pagina': f_pie.value.strip(),
            }
            if save_acta_retransmision_template(nuevo_dict):
                ui.notify('¡Plantilla del Acta de Retransmisión guardada exitosamente!', type='positive', icon='check_circle')
                actualizar_vista_previa()
            else:
                ui.notify('No se pudo guardar la plantilla en la base de datos.', type='negative')

        def aplicar_valores(valores: dict):
            f_titulo.value = valores.get('titulo', '')
            f_entidad.value = valores.get('entidad', '')
            f_nit.value = valores.get('nit_entidad', '')
            f_apertura.value = valores.get('texto_apertura', '')
            f_cabeceras.value = valores.get('clausula_cabeceras', '')
            f_vigencia_periodo.value = valores.get('periodo_vigencia', 'un (1) año')
            f_vigencia.value = valores.get('clausula_vigencia', '')
            f_tecnica.value = valores.get('clausula_tecnica', '')
            f_despedida.value = valores.get('despedida', 'Atentamente,')
            f_firmante.value = valores.get('nombre_firmante', 'CLAUDIA GARZON')
            f_cargo.value = valores.get('cargo_firmante', 'Gerente del Canal')
            f_cel.value = valores.get('celular_firmante', '3138932021')
            f_pie.value = valores.get('pie_pagina', '')
            actualizar_vista_previa()

        def confirmar_restablecer():
            with ui.dialog() as dlg, ui.card().classes('w-96 p-6 bg-white rounded-2xl'):
                with ui.row().classes('items-center gap-2 text-amber-600 mb-2'):
                    ui.icon('warning', size='md')
                    ui.label('¿Restablecer Plantilla por Defecto?').classes('text-base font-bold text-slate-800')
                ui.label('Se cargarán los textos predeterminados basados en el documento oficial DOCX de Teleamiga.').classes('text-xs text-slate-600 mb-4')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Cancelar', on_click=dlg.close).props('flat')
                    def do_reset():
                        aplicar_valores(DEFAULT_ACTA_RETRANSMISION_TEMPLATE)
                        dlg.close()
                        ui.notify('Valores por defecto cargados en el formulario. Recuerda pulsar Guardar para aplicarlos.', type='info')
                    ui.button('Restablecer', on_click=do_reset).classes('bg-amber-600 text-white font-bold')
            dlg.open()

        def cargar_docx_disco():
            if os.path.exists(RUTA_DOCX_DEFECTO):
                datos = extraer_plantilla_desde_docx(RUTA_DOCX_DEFECTO)
                if datos:
                    aplicar_valores(datos)
                    ui.notify('Textos extraídos exitosamente desde el archivo DOCX de Telehub.', type='positive')
                else:
                    ui.notify('No se pudo procesar el archivo DOCX.', type='negative')
            else:
                ui.notify(f'No se encontró el archivo DOCX en: {RUTA_DOCX_DEFECTO}', type='warning')

        btn_guardar.on('click', ejecutar_guardado)
        btn_reset.on('click', confirmar_restablecer)
        btn_recargar_docx.on('click', cargar_docx_disco)
