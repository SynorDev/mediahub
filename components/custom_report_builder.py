from nicegui import app, ui
from datetime import datetime
import base64
import uuid
from database import (
    get_custom_module, 
    get_all_custom_records, 
    update_custom_record,
    save_report_layout, 
    get_report_layout,
    obtener_detalles_modulo_vinculado,
    save_system_logo,
    get_system_logo,
    create_or_update_delivery_act,
    get_delivery_act_by_record,
    get_delivery_act_by_code,
    sign_delivery_act
)
from components.custom_report_preview import render_custom_a4_paper

def desglosar_registros_para_reporte(registros, config_campos, desglosar_kits=True):
    """
    Si desglosar_kits es True, convierte cada accesorio o sub-equipo contenido en un Kit 
    en una fila independiente (registro unitario) en el PDF, conservando el tag del Kit al que pertenece.
    """
    if not desglosar_kits or not registros:
        return registros
        
    key_nombre = None
    key_cat = None
    key_serial = None
    key_cantidad = None
    key_estado = None
    key_fotos = None
    key_accs = None
    
    for f_id, field in config_campos.items():
        lbl_lower = field['label'].lower()
        f_type = field['type']
        
        if f_type == 'accessories':
            key_accs = f_id
        elif f_type == 'images':
            key_fotos = f_id
        elif any(k in lbl_lower for k in ['nombre', 'modelo', 'equipo']):
            if not key_nombre: key_nombre = f_id
        elif 'cat' in lbl_lower:
            if not key_cat: key_cat = f_id
        elif 'ser' in lbl_lower:
            if not key_serial: key_serial = f_id
        elif 'cant' in lbl_lower:
            if not key_cantidad: key_cantidad = f_id
        elif 'est' in lbl_lower or 'condic' in lbl_lower:
            if not key_estado: key_estado = f_id
            
    keys_list = list(config_campos.keys())
    if not key_nombre and len(keys_list) > 0: key_nombre = keys_list[0]
    if not key_cat and len(keys_list) > 1: key_cat = keys_list[1]
    if not key_serial and len(keys_list) > 2: key_serial = keys_list[2]
    if not key_cantidad and len(keys_list) > 3: key_cantidad = keys_list[3]
    
    nuevos_registros = []
    
    for reg in registros:
        if not reg or not isinstance(reg, dict):
            continue
        data = reg.get('data')
        if not isinstance(data, dict):
            continue
        accs = data.get(key_accs) if key_accs else None
        
        if accs and isinstance(accs, list) and len(accs) > 0:
            nombre_kit = str(data.get(key_nombre) or f"Kit #{reg['id']}")
            
            for idx_acc, acc in enumerate(accs):
                acc_data = dict(data)
                
                # Asignar atributos individuales del elemento del kit
                if key_nombre:
                    acc_data[key_nombre] = acc.get('nombre') or acc_data.get(key_nombre)
                if key_cat:
                    acc_data[key_cat] = acc.get('categoria') or acc_data.get(key_cat)
                if key_serial:
                    acc_data[key_serial] = acc.get('serial') or ""
                if key_cantidad:
                    acc_data[key_cantidad] = acc.get('cantidad') if acc.get('cantidad') is not None else 1
                if key_estado and acc.get('estado'):
                    acc_data[key_estado] = acc.get('estado')
                if key_fotos:
                    if acc.get('foto'):
                        acc_data[key_fotos] = [acc['foto']]
                    else:
                        acc_data[key_fotos] = None
                if key_accs:
                    acc_data[key_accs] = None
                    
                acc_data['_kit_pertenece'] = nombre_kit
                
                nuevos_registros.append({
                    'id': f"{reg['id']}_acc_{idx_acc}",
                    'data': acc_data,
                    'es_subitem_kit': True,
                    'nombre_kit_padre': nombre_kit
                })
        else:
            nuevos_registros.append(reg)
            
    return nuevos_registros

def render_custom_report_module(main_container, right_panel_container, user_info, module_id, initial_record_id=None):
    """Maneja el panel lateral de configuración del reporte y orquesta la vista previa para inventarios."""
    main_container.clear()
    right_panel_container.clear()

    # Inyección de las librerías jsPDF y html2canvas-pro si no están cargadas
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
    fecha_legible = now.strftime("%d/%m/%Y")
    
    # Cargar información del módulo y registros
    modulo = get_custom_module(module_id)
    if not modulo:
        with main_container:
            ui.label('Error: No se encontró el módulo de gestión de inventario solicitado.').classes('text-red-500 font-bold')
        return

    registros = get_all_custom_records(module_id)
    
    # Mapeo de campos disponibles en el módulo
    config_campos = {}
    opciones_campos = {}
    for idx, field in enumerate(modulo['config']):
        f_id = field.get('key', f"field_{idx}")
        config_campos[f_id] = field
        opciones_campos[f_id] = field['label']

    # Pre-cargar caché de módulos vinculados para detección de colaboradores y equipos
    cache_detalles_modulos = {}
    for f in config_campos.values():
        if f.get('type') == 'linked_data' and f.get('linked_module_id'):
            mid = f['linked_module_id']
            if mid not in cache_detalles_modulos:
                cache_detalles_modulos[mid] = obtener_detalles_modulo_vinculado(mid)

    # Asegurar la precarga del módulo oficial de personal de la plataforma (system_staff)
    if 'system_staff' not in cache_detalles_modulos:
        cache_detalles_modulos['system_staff'] = obtener_detalles_modulo_vinculado('system_staff')

    # Identificar colaboradores y opciones de selección puntual
    colaboradores_dict = {}
    
    # 1. Precargar TODO el personal registrado en la plataforma
    for pid, pdet in cache_detalles_modulos['system_staff'].items():
        colaboradores_dict[pid] = {
            'id': pid,
            'detalles': pdet,
            'nombre': pdet.get('nombre', 'Colaborador'),
            'rol': pdet.get('rol', ''),
            'correo': pdet.get('correo', ''),
            'celular': pdet.get('celular') or pdet.get('telefono', ''),
            'cedula': pdet.get('cedula', ''),
            'records': []
        }

    opciones_registros_puntuales = {}
    
    for reg in registros:
        d = reg.get('data', {})
        equipos_nom = []
        personas_nom = []
        
        for f_id, f_val in d.items():
            if f_val is None:
                continue
            f_cfg = config_campos.get(f_id, {})
            if f_cfg.get('type') == 'linked_data':
                mid = f_cfg.get('linked_module_id')
                detalles = cache_detalles_modulos.get(mid, {})
                keys = f_val if isinstance(f_val, list) else [f_val]
                for k in keys:
                    det = detalles.get(k)
                    if det:
                        if det.get('es_persona'):
                            pid = det['id']
                            if pid not in colaboradores_dict:
                                colaboradores_dict[pid] = {
                                    'id': pid,
                                    'detalles': det,
                                    'nombre': det['nombre'],
                                    'rol': det.get('rol', ''),
                                    'correo': det.get('correo', ''),
                                    'celular': det.get('celular') or det.get('telefono', ''),
                                    'cedula': det.get('cedula', ''),
                                    'records': []
                                }
                            if reg not in colaboradores_dict[pid]['records']:
                                colaboradores_dict[pid]['records'].append(reg)
                            personas_nom.append(det['nombre'])
                        else:
                            equipos_nom.append(det.get('nombre', 'Equipo'))
            elif f_cfg.get('type') == 'text' and f_val:
                lbl_lower = f_cfg.get('label', '').lower()
                if any(k in lbl_lower for k in ['responsable', 'colaborador', 'persona', 'entrega', 'recibe']):
                    personas_nom.append(str(f_val).strip())
                elif any(k in lbl_lower for k in ['equipo', 'modelo', 'nombre', 'articulo']):
                    equipos_nom.append(str(f_val).strip())
                    
        # Construir resumen para selector de registros puntuales
        eq_str = ", ".join(equipos_nom) if equipos_nom else "Ítems"
        per_str = f" • Asignado: {', '.join(personas_nom)}" if personas_nom else ""
        opciones_registros_puntuales[str(reg['id'])] = f"Entrega #{reg['id']}: {eq_str}{per_str}"

    opciones_colaboradores = {}
    for pid, cdata in sorted(colaboradores_dict.items(), key=lambda x: x[1]['nombre']):
        rol_txt = f" ({cdata['rol']})" if cdata.get('rol') else ""
        cant_items = len(cdata['records'])
        items_txt = f" — {cant_items} asignación(es)" if cant_items > 0 else ""
        opciones_colaboradores[pid] = f"{cdata['nombre']}{rol_txt}{items_txt}"

    # Opciones para el selector de personal general del acta
    opciones_personal_select = {
        '': '— Sin responsable específico asignado —'
    }
    for pid, cdata in sorted(colaboradores_dict.items(), key=lambda x: x[1]['nombre']):
        rol_txt = f" [{cdata['rol']}]" if cdata.get('rol') else ""
        mail_txt = f" • {cdata['correo']}" if cdata.get('correo') else ""
        opciones_personal_select[pid] = f"{cdata['nombre']}{rol_txt}{mail_txt}"

    # Detectar campo de Contenedor / Grupo para actas por locación o grupo de equipos
    key_contenedor = None
    for f_id, f_cfg in config_campos.items():
        lbl_lower = f_cfg.get('label', '').lower()
        if any(k in lbl_lower for k in ['contenedor', 'grupo', 'ubicacion', 'locacion']):
            key_contenedor = f_id
            break

    contenedores_dict = {}
    if key_contenedor:
        for reg in registros:
            cval = reg.get('data', {}).get(key_contenedor)
            if cval and str(cval).strip():
                cval_str = str(cval).strip()
                if cval_str not in contenedores_dict:
                    contenedores_dict[cval_str] = []
                contenedores_dict[cval_str].append(reg)

    # Cargar o inicializar el estado del reporte
    layout_db_id = f"inventory_{module_id}"
    estado_guardado = get_report_layout(layout_db_id)
    
    # Texto de apertura por defecto solicitado por el usuario
    DEFAULT_APERTURA = "Por medio de la presente la FUNDACION ICTUS hace entrega e inventario de los siguientes equipos a [RESPONSABLE], identificado con [CORREO], para el desempeno exclusivo de sus funciones laborales."
    DEFAULT_CIERRE = "Al firmar este documento, el colaborador declara que:\n1. Recibe los elementos en perfecto estado de funcionamiento y conservacion.\n2. Se compromete a darles un uso exclusivamente profesional y velar por su cuidado.\n3. En caso de perdida o dano por negligencia, asumira la reposicion del bien."

    doc_id_default = f"ACT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    if estado_guardado:
        estado_reporte = estado_guardado
        estado_reporte.setdefault('doc_id', doc_id_default)
        estado_reporte.setdefault('formato_papel', 'letter')
        estado_reporte.setdefault('foto_size_pct', 120)
        estado_reporte.setdefault('texto_apertura', DEFAULT_APERTURA)
        estado_reporte.setdefault('texto_cierre', DEFAULT_CIERRE)
        estado_reporte.setdefault('mostrar_clausula_apertura', True)
        estado_reporte.setdefault('mostrar_clausula_cierre', True)
        estado_reporte.setdefault('mostrar_firmas', True)
        estado_reporte.setdefault('firma_1_titulo', 'Firma de Recibido')
        estado_reporte.setdefault('firma_1_subtitulo', '[RESPONSABLE] / C.C.')
        estado_reporte.setdefault('mostrar_firma_2', True)
        estado_reporte.setdefault('firma_2_titulo', 'Entregado Por')
        estado_reporte.setdefault('firma_2_subtitulo', 'Departamento de Ingeniería')
        estado_reporte.setdefault('modo_alcance', 'todos')
        estado_reporte.setdefault('persona_fijada_id', None)
        estado_reporte.setdefault('registros_seleccionados_ids', [])
        estado_reporte.setdefault('contenedor_seleccionado', None)
        estado_reporte.setdefault('acomodacion', 'auto')
    else:
        # Inicializar por defecto (cada campo como una columna independiente, limitado a 5)
        columnas_iniciales = []
        for idx, field in enumerate(modulo['config'][:5]):
            f_id = field.get('key', f"field_{idx}")
            columnas_iniciales.append({
                'id': str(uuid.uuid4()),
                'titulo': field['label'].upper(),
                'campos': [f_id]
            })
            
        estado_reporte = {
            'doc_id': doc_id_default,
            'formato_papel': 'letter',
            'acomodacion': 'auto',
            'titulo': "ACTA DE ENTREGA DE EQUIPOS",
            'header_title': 'MEDIAHUB V4',
            'header_subtitle': 'Documento Operativo Oficial',
            'footer_text': 'Generado por MediaHub V4',
            'logo_b64': get_system_logo(),
            'columnas': columnas_iniciales,
            'foto_size_pct': 120,
            'desglosar_kits': True,
            'texto_apertura': DEFAULT_APERTURA,
            'texto_cierre': DEFAULT_CIERRE,
            'mostrar_clausula_apertura': True,
            'mostrar_clausula_cierre': True,
            'mostrar_firmas': True,
            'firma_1_titulo': 'Firma de Recibido',
            'firma_1_subtitulo': '[RESPONSABLE] / C.C.',
            'mostrar_firma_2': True,
            'firma_2_titulo': 'Entregado Por',
            'firma_2_subtitulo': 'Departamento de Ingeniería',
            'modo_alcance': 'todos',
            'persona_fijada_id': None,
            'registros_seleccionados_ids': [],
            'contenedor_seleccionado': None
        }

    # Si viene con un record_id inicial desde la vista de gestión
    if initial_record_id:
        reg_id_str = str(initial_record_id).replace('rec_', '')
        matching = [r for r in registros if str(r['id']) == reg_id_str or str(r['id']) == str(initial_record_id)]
        if matching:
            reg_obj = matching[0]
            estado_reporte['modo_alcance'] = 'puntual'
            estado_reporte['registros_seleccionados_ids'] = [str(reg_obj['id'])]
            
            # Auto-detectar responsable asignado al equipo si existe
            d = reg_obj.get('data', {})
            resp_detectado = None
            for f_id, f_val in d.items():
                if f_val and f_id in config_campos:
                    f_cfg = config_campos[f_id]
                    if f_cfg.get('type') == 'linked_data':
                        val_k = f_val[0] if isinstance(f_val, list) and f_val else f_val
                        if str(val_k) in colaboradores_dict:
                            resp_detectado = str(val_k)
                            break
            if resp_detectado:
                estado_reporte['persona_fijada_id'] = resp_detectado
                estado_reporte['persona_fijada'] = colaboradores_dict[resp_detectado]['detalles']

            # Cargar acta virtual emitida previamente si existe
            acta_db = get_delivery_act_by_record(reg_obj['id'], module_id)
            if acta_db:
                estado_reporte['doc_id'] = acta_db['code']
                estado_reporte['acta_db'] = acta_db
                estado_reporte['firma_receptor_b64'] = acta_db.get('firma_receptor_b64')
                estado_reporte['firma_receptor_fecha'] = acta_db.get('firma_receptor_fecha')
                estado_reporte['firma_emisor_b64'] = acta_db.get('firma_emisor_b64')
                estado_reporte['firma_emisor_fecha'] = acta_db.get('firma_emisor_fecha')
                if acta_db.get('receptor_id') and str(acta_db['receptor_id']) in colaboradores_dict:
                    estado_reporte['persona_fijada_id'] = str(acta_db['receptor_id'])
                    estado_reporte['persona_fijada'] = colaboradores_dict[str(acta_db['receptor_id'])]['detalles']

    # Función para obtener los registros activos según el filtro de alcance
    def obtener_registros_activos():
        # Resolver y sincronizar persona_fijada en el estado
        pid = estado_reporte.get('persona_fijada_id')
        if pid and pid in colaboradores_dict:
            estado_reporte['persona_fijada'] = colaboradores_dict[pid]['detalles']
        else:
            # Si no hay persona seleccionada manualmente, verificar si los registros actuales tienen una
            p_detectada = None
            registros_revisar = []
            modo_check = estado_reporte.get('modo_alcance', 'todos')
            if modo_check == 'puntual':
                sel_ids_set = {str(x) for x in estado_reporte.get('registros_seleccionados_ids', [])}
                registros_revisar = [r for r in registros if str(r['id']) in sel_ids_set]
            else:
                registros_revisar = registros[:1]
                
            for reg in registros_revisar:
                d = reg.get('data', {})
                for f_id, f_val in d.items():
                    f_cfg = config_campos.get(f_id, {})
                    if f_cfg.get('type') == 'linked_data':
                        keys = f_val if isinstance(f_val, list) else [f_val]
                        for k in keys:
                            if str(k) in colaboradores_dict:
                                p_detectada = colaboradores_dict[str(k)]['detalles']
                                estado_reporte['persona_fijada_id'] = str(k)
                                break
                    if p_detectada: break
                if p_detectada: break
            estado_reporte['persona_fijada'] = p_detectada

        modo = estado_reporte.get('modo_alcance', 'todos')
        if modo == 'persona':
            if pid and pid in colaboradores_dict:
                recs = colaboradores_dict[pid]['records']
                return recs if recs else registros
            return registros
        elif modo == 'contenedor':
            c_sel = estado_reporte.get('contenedor_seleccionado')
            if c_sel and c_sel in contenedores_dict:
                return contenedores_dict[c_sel]
            elif contenedores_dict:
                primer_cont = sorted(contenedores_dict.keys())[0]
                estado_reporte['contenedor_seleccionado'] = primer_cont
                return contenedores_dict[primer_cont]
            return registros
        elif modo == 'puntual':
            sel_ids = estado_reporte.get('registros_seleccionados_ids', [])
            if sel_ids:
                sel_ids_set = {str(x) for x in sel_ids}
                filtrados = [r for r in registros if str(r['id']) in sel_ids_set]
                return filtrados if filtrados else registros
            return registros
        else:
            return registros

    async def disparar_descarga_jpg():
        ui.notify('Generando fotografía de la primera hoja...', type='info', icon='image')
        fmt = estado_reporte.get('formato_papel', 'letter')
        js_code = f"""
            if (typeof html2canvas === 'undefined') {{
                alert('El motor gráfico se está preparando.'); return;
            }}
            let pages = document.querySelectorAll(".report-page");
            if (pages.length === 0) return;
            
            html2canvas(pages[0], {{scale: 2, useCORS: true, backgroundColor: '#ffffff'}}).then(canvas => {{
                let link = document.createElement("a");
                link.download = "Acta_Entrega_Pagina1_{fmt.upper()}.jpg";
                link.href = canvas.toDataURL("image/jpeg", 0.95);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}).catch(err => alert("Error capturando imagen: " + err));
        """
        await ui.run_javascript(js_code)

    async def disparar_descarga_pdf():
        ui.notify('Compilando PDF Multipágina... aguarda un momento', type='info', icon='picture_as_pdf')
        formato_js = 'a4' if estado_reporte.get('formato_papel') == 'a4' else 'letter'
        
        js_code = f"""
            if (typeof window.jspdf === 'undefined' || typeof html2canvas === 'undefined') {{
                alert('El motor PDF se está preparando.'); return;
            }}
            
            async function generarPDF() {{
                let formatoPapel = '{formato_js}';
                let pdf = new window.jspdf.jsPDF("p", "mm", formatoPapel);
                let pages = document.querySelectorAll(".report-page");
                
                let pdfWidth = pdf.internal.pageSize.getWidth();
                let pdfHeight = pdf.internal.pageSize.getHeight();
                
                for (let i = 0; i < pages.length; i++) {{
                    let element = pages[i];
                    let canvas = await html2canvas(element, {{scale: 2, useCORS: true, backgroundColor: '#ffffff'}});
                    let imgData = canvas.toDataURL("image/jpeg", 0.95);
                    
                    let imgProps = pdf.getImageProperties(imgData);
                    let ratio = imgProps.width / imgProps.height;
                    let renderHeight = pdfWidth / ratio;
                    
                    // Asegurar que no sobrepase el alto físico de la hoja
                    if (renderHeight > pdfHeight) {{
                        renderHeight = pdfHeight;
                    }}
                    
                    pdf.addImage(imgData, "JPEG", 0, 0, pdfWidth, renderHeight);
                    
                    if (i < pages.length - 1) {{
                        pdf.addPage(formatoPapel, "p");
                    }}
                }}
                
                let nomFmt = (formatoPapel === 'letter' ? 'Carta' : 'A4');
                pdf.save("Acta_Entrega_{modulo['nombre']}_" + nomFmt + ".pdf");
            }}
            
            generarPDF().catch(err => alert("Error al compilar PDF: " + err));
        """
        await ui.run_javascript(js_code)

    # Función reactiva para guardar la configuración y actualizar la vista previa
    # Cargar logo persistente del sistema si no tiene uno específico asignado
    if not estado_reporte.get('logo_b64'):
        estado_reporte['logo_b64'] = get_system_logo()

    def disparar_actualizacion():
        def toggle_panel():
            if 'hidden' in right_panel_container.classes:
                right_panel_container.classes(remove='hidden')
            else:
                right_panel_container.classes(add='hidden')
                
        save_report_layout(layout_db_id, estado_reporte)
        registros_activos = obtener_registros_activos()
        registros_desglosados = desglosar_registros_para_reporte(
            registros_activos, config_campos, estado_reporte.get('desglosar_kits', True)
        )
        render_custom_a4_paper(
            main_container, estado_reporte, registros_desglosados, opciones_campos, config_campos,
            modulo['nombre'], modulo['icono'], fecha_legible, user_info, toggle_panel,
            on_download_pdf=disparar_descarga_pdf
        )

    # Panel lateral derecho (Maquetador)
    with right_panel_container.classes('flex flex-col h-full bg-white'):
        with ui.column().classes('w-full flex-grow p-5 overflow-y-auto gap-4'):
            
            with ui.row().classes('items-center gap-2 mb-1 border-b pb-3 w-full'):
                ui.icon('assignment', size='md').classes('text-indigo-600')
                ui.label('Configuración de Acta / Reporte').classes('text-lg font-bold text-gray-800')

            # SECCIÓN 1: ALCANCE Y TIPO DE ACTA (GENERAL VS CONSOLIDADA VS PUNTUAL)
            ui.label('1. Alcance y Tipo de Acta').classes('text-xs font-bold text-indigo-900 uppercase tracking-wider bg-indigo-50 px-2 py-1 rounded w-full')
            
            alcance_options = {
                'todos': '📜 Todas las Entregas (Acta Global)',
                'contenedor': '🏢 Por Contenedor / Grupo',
                'persona': '👤 Acta Consolidada por Responsable',
                'puntual': '🎯 Entrega Puntual / Selección Específica'
            }
            
            subpanel_alcance = ui.column().classes('w-full gap-2 pl-1')
            
            def refrescar_subpanel_alcance():
                subpanel_alcance.clear()
                with subpanel_alcance:
                    modo = estado_reporte.get('modo_alcance', 'todos')
                    
                    if modo == 'contenedor':
                        if not contenedores_dict:
                            ui.label('No se detectó un campo de Contenedor o Grupo en este inventario.').classes('text-xs text-amber-700 italic')
                        else:
                            ui.label('Selecciona el Contenedor o Grupo para generar el acta:').classes('text-xs font-semibold text-slate-700')
                            opciones_cont = {k: f"{k} — {len(v)} ítem(s)" for k, v in sorted(contenedores_dict.items())}
                            
                            if not estado_reporte.get('contenedor_seleccionado') or estado_reporte['contenedor_seleccionado'] not in contenedores_dict:
                                estado_reporte['contenedor_seleccionado'] = list(contenedores_dict.keys())[0]
                                
                            def on_change_cont(e):
                                estado_reporte['contenedor_seleccionado'] = e.value
                                disparar_actualizacion()
                                
                            ui.select(
                                options=opciones_cont,
                                value=estado_reporte.get('contenedor_seleccionado'),
                                on_change=on_change_cont
                            ).props('outlined dense options-dense').classes('w-full text-xs')
                            
                            c_sel = estado_reporte.get('contenedor_seleccionado')
                            if c_sel and c_sel in contenedores_dict:
                                with ui.row().classes('items-center gap-1.5 p-2 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-900 w-full'):
                                    ui.icon('inventory_2', size='xs').classes('text-emerald-600 shrink-0')
                                    with ui.column().classes('gap-0'):
                                        ui.label(f"Contenedor: {c_sel}").classes('font-bold leading-tight')
                                        ui.label(f"Total equipos en esta acta: {len(contenedores_dict[c_sel])}").classes('text-[10px] text-emerald-700 font-semibold')
                    
                    if modo == 'persona':
                        if not opciones_colaboradores:
                            ui.label('No se detectaron colaboradores vinculados en los registros.').classes('text-xs text-amber-700 italic')
                        else:
                            ui.label('Selecciona el colaborador para consolidar todo su inventario asignado:').classes('text-xs font-semibold text-slate-700')
                            
                            # Si no hay persona seleccionada pero hay opciones, preseleccionar la primera
                            if not estado_reporte.get('persona_fijada_id') or estado_reporte['persona_fijada_id'] not in opciones_colaboradores:
                                estado_reporte['persona_fijada_id'] = list(opciones_colaboradores.keys())[0]
                                
                            def on_change_colaborador(e):
                                estado_reporte['persona_fijada_id'] = e.value
                                refrescar_subpanel_alcance()
                                disparar_actualizacion()
                                
                            ui.select(
                                options=opciones_colaboradores,
                                value=estado_reporte.get('persona_fijada_id'),
                                on_change=on_change_colaborador
                            ).props('outlined dense options-dense').classes('w-full text-xs')
                            
                            pid = estado_reporte.get('persona_fijada_id')
                            if pid and pid in colaboradores_dict:
                                pdata = colaboradores_dict[pid]
                                with ui.row().classes('items-center gap-1.5 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-900 w-full'):
                                    ui.icon('verified', size='xs').classes('text-blue-600 shrink-0')
                                    with ui.column().classes('gap-0'):
                                        ui.label(f"{pdata['nombre']} ({pdata['rol'] or 'Colaborador'})").classes('font-bold leading-tight')
                                        ui.label(f"✉️ {pdata['correo'] or 'Sin correo'} • 📞 {pdata['celular'] or 'Sin teléfono'}").classes('text-[10px] text-slate-600')
                                        ui.label(f"Total ítems consolidados: {len(pdata['records'])}").classes('text-[10px] font-semibold text-indigo-700')
                                        
                    elif modo == 'puntual':
                        if not opciones_registros_puntuales:
                            ui.label('No hay entregas disponibles.').classes('text-xs text-gray-500')
                        else:
                            ui.label('Selecciona las entregas o elementos a incluir en esta acta:').classes('text-xs font-semibold text-slate-700')
                            
                            # Si está vacío, seleccionar el primer registro
                            if not estado_reporte.get('registros_seleccionados_ids'):
                                estado_reporte['registros_seleccionados_ids'] = [list(opciones_registros_puntuales.keys())[0]]
                                
                            def on_change_puntual(e):
                                estado_reporte['registros_seleccionados_ids'] = e.value
                                disparar_actualizacion()
                                
                            ui.select(
                                options=opciones_registros_puntuales,
                                value=estado_reporte.get('registros_seleccionados_ids', []),
                                multiple=True,
                                on_change=on_change_puntual
                            ).props('use-chips outlined dense options-dense').classes('w-full text-xs')
                            
                    elif modo == 'todos':
                        with ui.row().classes('items-center gap-1 p-2 bg-slate-50 border border-slate-200 rounded text-xs text-slate-700 w-full'):
                            ui.icon('info', size='xs').classes('text-slate-500 shrink-0')
                            ui.label(f"Incluye la totalidad de {len(registros)} registros de este módulo.").classes('text-[11px]')

            def on_change_alcance(e):
                estado_reporte['modo_alcance'] = e.value
                refrescar_subpanel_alcance()
                disparar_actualizacion()

            ui.radio(
                options=alcance_options,
                value=estado_reporte.get('modo_alcance', 'todos'),
                on_change=on_change_alcance
            ).props('dense').classes('text-xs text-slate-800')

            refrescar_subpanel_alcance()

            # SECCIÓN 2: ASIGNACIÓN DE RESPONSABLE / DESTINATARIO DEL ACTA
            ui.label('2. Responsable / Destinatario del Acta').classes('text-xs font-bold text-indigo-900 uppercase tracking-wider bg-indigo-50 px-2 py-1 rounded w-full mt-2')

            subpanel_responsable = ui.column().classes('w-full gap-2 pl-1')

            # Diálogo para que Ingeniería estampe su firma digital directamente
            dialogo_firma_ing = ui.dialog()
            firma_ing_state = {'b64': None, 'canvas_id': None}

            def abrir_modal_firma_ingenieria(acta_actual):
                dialogo_firma_ing.clear()
                c_id = f"canvas-ing-{acta_actual.get('code', 'act').replace('-', '_')}"
                firma_ing_state['canvas_id'] = c_id
                firma_ing_state['b64'] = None

                with dialogo_firma_ing, ui.card().classes('w-full max-w-lg p-5 rounded-2xl gap-3 bg-white shadow-2xl'):
                    with ui.row().classes('items-center justify-between w-full border-b pb-2'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('draw', size='sm').classes('text-indigo-600')
                            ui.label('Estampar Firma de Ingeniería').classes('text-sm font-bold text-slate-800')
                        ui.button(icon='close', on_click=dialogo_firma_ing.close).props('flat round dense')

                    with ui.row().classes('items-center gap-2'):
                        ui.label('Acta Oficial:').classes('text-xs text-slate-500')
                        ui.label(acta_actual.get('code')).classes('text-xs font-mono font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded')

                    with ui.tabs().classes('w-full text-xs font-bold') as tabs_ing:
                        tab_dibujo = ui.tab('✍️ Dibujar en Pantalla')
                        tab_archivo = ui.tab('📁 Cargar Imagen (.PNG/.JPG)')

                    with ui.tab_panels(tabs_ing, value=tab_dibujo).classes('w-full p-0 bg-transparent'):
                        with ui.tab_panel(tab_dibujo).classes('p-0 gap-2 items-center'):
                            ui.label('Dibuja la firma de Ingeniería usando el mouse o pantalla táctil:').classes('text-[11px] text-slate-600')
                            ui.html(f'''
                                <div style="position: relative; width: 100%; max-width: 440px; height: 160px; background: #ffffff; border: 2px dashed #94a3b8; border-radius: 10px; overflow: hidden; touch-action: none; margin: 0 auto;">
                                    <canvas id="{c_id}" width="440" height="160" style="display: block; width: 100%; height: 100%; cursor: crosshair;"></canvas>
                                    <div style="position: absolute; bottom: 6px; left: 10px; font-size: 9px; color: #94a3b8; pointer-events: none; font-weight: bold;">
                                        Firma Ingeniería y Sistemas
                                    </div>
                                </div>
                            ''')
                            ui.run_javascript(f'''
                                (function() {{
                                    const canvas = document.getElementById("{c_id}");
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
                            async def limpiar_c():
                                await ui.run_javascript(f'''
                                    const c = document.getElementById("{c_id}");
                                    if (c) {{
                                        const ctx = c.getContext("2d");
                                        ctx.clearRect(0, 0, c.width, c.height);
                                    }}
                                ''')
                                firma_ing_state['b64'] = None
                                ui.notify('Lienzo limpiado', type='info')
                            ui.button('Limpiar Trazo', icon='delete_sweep', on_click=limpiar_c).props('flat dense color=red size=xs')

                        with ui.tab_panel(tab_archivo).classes('p-0 gap-2 items-center'):
                            ui.label('Sube un archivo de firma (.PNG transparente recomendado o .JPG):').classes('text-[11px] text-slate-600')
                            preview_box = ui.column().classes('w-full items-center')
                            async def on_upload_firm(e):
                                b_bytes = await e.file.read()
                                b64_str = f"data:image/png;base64,{base64.b64encode(b_bytes).decode('utf-8')}"
                                firma_ing_state['b64'] = b64_str
                                preview_box.clear()
                                with preview_box:
                                    ui.image(b64_str).props('fit=contain').classes('h-16 w-40 object-contain bg-white rounded border border-indigo-200 mt-1')
                                ui.notify('Imagen de firma cargada', type='positive')
                            ui.upload(label='Seleccionar Firma', on_upload=on_upload_firm, auto_upload=True)\
                                .props('accept=.png,.jpg,.jpeg').classes('w-full max-w-xs')

                    async def guardar_firma_ing():
                        b64_final = None
                        if tabs_ing.value == tab_dibujo:
                            js_extract = f'''
                                (() => {{
                                    const c = document.getElementById("{c_id}");
                                    if (!c) return "";
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
                            if not firma_ing_state.get('b64'):
                                ui.notify('Por favor sube una imagen de firma válida', type='warning')
                                return
                            b64_final = firma_ing_state['b64']

                        nom_ing = user_info.get('nombres') or user_info.get('usuario') or 'Ingeniería y Sistemas'
                        succ, msg, updated = sign_delivery_act(acta_actual['code'], 'emisor', b64_final, nom_ing)
                        if succ:
                            estado_reporte['acta_db'] = updated
                            estado_reporte['firma_emisor_b64'] = updated.get('firma_emisor_b64')
                            estado_reporte['firma_emisor_fecha'] = updated.get('firma_emisor_fecha')
                            dialogo_firma_ing.close()
                            ui.notify('✓ ¡Firma de Ingeniería estampada con éxito en el acta!', type='positive', icon='verified')
                            refrescar_subpanel_responsable()
                            disparar_actualizacion()
                        else:
                            ui.notify(msg, type='negative')

                    with ui.row().classes('w-full justify-end gap-2 pt-2 border-t'):
                        ui.button('Cancelar', on_click=dialogo_firma_ing.close).props('flat text-color=grey')
                        ui.button('Estampar Firma Oficial', icon='verified', on_click=guardar_firma_ing)\
                            .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs py-1.5 px-4 rounded-lg shadow-sm')

                dialogo_firma_ing.open()

            def guardar_responsable_en_inventario():
                pid = estado_reporte.get('persona_fijada_id')
                if not pid or pid not in colaboradores_dict:
                    ui.notify('Selecciona primero un colaborador válido de la lista', type='warning')
                    return
                    
                pdata = colaboradores_dict[pid]
                pnom = pdata.get('nombre', 'Responsable')
                
                # Identificar los registros puntuales seleccionados
                sel_ids = estado_reporte.get('registros_seleccionados_ids', [])
                if not sel_ids and initial_record_id:
                    sel_ids = [str(initial_record_id).replace('rec_', '')]
                    
                if not sel_ids:
                    ui.notify('Selecciona al menos una entrega o equipo en Alcance Puntual para vincular el responsable', type='warning')
                    return
                    
                # Buscar campo de responsable en config_campos
                key_resp = 'field_responsable'
                for f_id, f_cfg in config_campos.items():
                    if f_cfg.get('type') == 'linked_data' and f_cfg.get('linked_module_id') == 'system_staff':
                        key_resp = f_id
                        break
                        
                actualizados = 0
                for r_id_str in sel_ids:
                    try:
                        r_id_int = int(str(r_id_str).replace('rec_', ''))
                    except ValueError:
                        continue
                    reg_obj = next((r for r in registros if r['id'] == r_id_int), None)
                    if reg_obj:
                        data_actual = dict(reg_obj.get('data', {}))
                        data_actual[key_resp] = pid
                        succ, msg = update_custom_record(r_id_int, data_actual)
                        if succ:
                            reg_obj['data'] = data_actual
                            if reg_obj not in pdata['records']:
                                pdata['records'].append(reg_obj)
                            actualizados += 1
                            
                if actualizados > 0:
                    ui.notify(f'✓ Responsable {pnom} vinculado correctamente a {actualizados} equipo(s) en el inventario', type='positive', icon='check_circle')
                    refrescar_subpanel_responsable()
                    disparar_actualizacion()
                else:
                    ui.notify('No se pudo guardar la vinculación en el inventario', type='negative')

            def emitir_acta_virtual(force_new: bool = False):
                pid = estado_reporte.get('persona_fijada_id')
                if not pid or pid not in colaboradores_dict:
                    ui.notify('Selecciona primero un colaborador responsable de la lista', type='warning')
                    return
                pdata = colaboradores_dict[pid]

                sel_ids = estado_reporte.get('registros_seleccionados_ids', [])
                if not sel_ids and initial_record_id:
                    sel_ids = [str(initial_record_id).replace('rec_', '')]

                if not sel_ids:
                    ui.notify('Selecciona al menos una entrega o equipo en Alcance Puntual para emitir el acta', type='warning')
                    return

                target_rec_id = int(str(sel_ids[0]).replace('rec_', ''))
                
                # Sincronizar en inventario si aún no está vinculado
                key_resp = 'field_responsable'
                for f_id, f_cfg in config_campos.items():
                    if f_cfg.get('type') == 'linked_data' and f_cfg.get('linked_module_id') == 'system_staff':
                        key_resp = f_id
                        break
                reg_obj = next((r for r in registros if r['id'] == target_rec_id), None)
                if reg_obj:
                    data_act = dict(reg_obj.get('data', {}))
                    data_act[key_resp] = pid
                    update_custom_record(target_rec_id, data_act)
                    reg_obj['data'] = data_act

                # Construir resumen de equipos incluidos
                equipos_info = []
                for s_id in sel_ids:
                    try:
                        rid = int(str(s_id).replace('rec_', ''))
                    except ValueError:
                        continue
                    robj = next((r for r in registros if r['id'] == rid), None)
                    if robj:
                        d_r = robj.get('data', {})
                        eq_nom = None
                        eq_ser = None
                        for fid, fv in d_r.items():
                            flbl = config_campos.get(fid, {}).get('label', '').lower()
                            if any(k in flbl for k in ['nombre', 'modelo', 'equipo']) and not eq_nom:
                                eq_nom = str(fv)
                            elif 'ser' in flbl and not eq_ser:
                                eq_ser = str(fv)
                        equipos_info.append({
                            'id': rid,
                            'nombre': eq_nom or f"Equipo #{rid}",
                            'serial': eq_ser or 'S/N'
                        })

                emisor_nom = user_info.get('nombres') or user_info.get('usuario') or 'Ingeniería y Sistemas'
                succ, msg, acta = create_or_update_delivery_act(
                    record_id=target_rec_id,
                    module_id=module_id,
                    receptor_id=pid,
                    receptor_nombre=pdata.get('nombre', 'Colaborador'),
                    receptor_correo=pdata.get('correo', ''),
                    detalles_equipos=equipos_info,
                    emitido_por=emisor_nom,
                    force_new=force_new
                )
                if not succ or not acta:
                    ui.notify(msg or 'Error al emitir acta', type='negative')
                    return
                
                estado_reporte['acta_db'] = acta
                estado_reporte['doc_id'] = acta['code']
                estado_reporte['firma_receptor_b64'] = acta.get('firma_receptor_b64')
                estado_reporte['firma_receptor_fecha'] = acta.get('firma_receptor_fecha')
                estado_reporte['firma_emisor_b64'] = acta.get('firma_emisor_b64')
                estado_reporte['firma_emisor_fecha'] = acta.get('firma_emisor_fecha')

                if force_new:
                    ui.notify(f"✓ Nueva acta {acta['code']} re-emitida y archivada en 'Entrega de equipos'. Lista para ser firmada.", type='positive', icon='send')
                else:
                    ui.notify(f"✓ Acta virtual {acta['code']} emitida y archivada en 'Entrega de equipos'. Notificación enviada a {pdata['nombre']}.", type='positive', icon='send')
                refrescar_subpanel_responsable()
                disparar_actualizacion()

            def refrescar_subpanel_responsable():
                subpanel_responsable.clear()
                with subpanel_responsable:
                    ui.label('Selecciona el personal creado en la plataforma al que se le entrega el equipo:').classes('text-xs font-semibold text-slate-700')
                    
                    val_actual_pid = estado_reporte.get('persona_fijada_id')
                    if val_actual_pid not in opciones_personal_select:
                        val_actual_pid = ''
                        
                    def on_change_resp(e):
                        sel_val = e.value
                        if sel_val and sel_val in colaboradores_dict:
                            estado_reporte['persona_fijada_id'] = sel_val
                            estado_reporte['persona_fijada'] = colaboradores_dict[sel_val]['detalles']
                        else:
                            estado_reporte['persona_fijada_id'] = None
                            estado_reporte['persona_fijada'] = None
                        refrescar_subpanel_responsable()
                        refrescar_subpanel_alcance()
                        disparar_actualizacion()
                        
                    ui.select(
                        options=opciones_personal_select,
                        value=val_actual_pid,
                        on_change=on_change_resp,
                        with_input=True
                    ).props('outlined dense options-dense clearable').classes('w-full text-xs')
                    
                    pid = estado_reporte.get('persona_fijada_id')
                    if pid and pid in colaboradores_dict:
                        pdata = colaboradores_dict[pid]
                        iniciales = "".join([part[0] for part in pdata['nombre'].split()[:2]]).upper() if pdata.get('nombre') else "U"
                        with ui.column().classes('w-full p-2.5 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg gap-1.5 shadow-xs'):
                            with ui.row().classes('items-center gap-2 w-full'):
                                with ui.element('div').classes('w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0'):
                                    ui.label(iniciales)
                                with ui.column().classes('gap-0 flex-grow min-w-0'):
                                    ui.label(pdata['nombre']).classes('font-bold text-slate-900 text-xs truncate')
                                    ui.label(pdata.get('rol') or 'Personal MediaHub').classes('text-[10.5px] text-indigo-700 font-semibold truncate')
                            
                            with ui.column().classes('gap-0.5 text-[10.5px] text-slate-600 w-full pl-0.5 border-t border-blue-100 pt-1'):
                                if pdata.get('correo'):
                                    ui.label(f"✉️ {pdata['correo']}").classes('truncate')
                                if pdata.get('celular'):
                                    ui.label(f"📞 {pdata['celular']}").classes('truncate')
                                    
                            # Botón para persistir en inventario si estamos en entrega puntual
                            modo = estado_reporte.get('modo_alcance', 'todos')
                            if modo == 'puntual' or initial_record_id:
                                ui.button('💾 Vincular este Responsable al Equipo en Inventario', icon='link', on_click=guardar_responsable_en_inventario) \
                                    .classes('w-full bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold py-1.5 rounded shadow-xs mt-1')
                    else:
                        with ui.row().classes('items-center gap-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 w-full'):
                            ui.icon('info', size='xs').classes('text-amber-600 shrink-0')
                            ui.label('No hay responsable asignado. Puedes seleccionarlo de la lista para sustituir [RESPONSABLE] y [CORREO].').classes('text-[10.5px] leading-tight')

                    # SECCIÓN DE ACTA DE ENTREGA VIRTUAL Y FIRMAS DIGITALES
                    target_rec_id = None
                    sel_ids = estado_reporte.get('registros_seleccionados_ids', [])
                    if sel_ids:
                        try:
                            target_rec_id = int(str(sel_ids[0]).replace('rec_', ''))
                        except ValueError:
                            pass
                    elif initial_record_id:
                        try:
                            target_rec_id = int(str(initial_record_id).replace('rec_', ''))
                        except ValueError:
                            pass

                    # Buscar acta existente si aún no está en memoria
                    acta_db = estado_reporte.get('acta_db')
                    if not acta_db and target_rec_id:
                        acta_db = get_delivery_act_by_record(target_rec_id, module_id)
                        if acta_db:
                            estado_reporte['acta_db'] = acta_db
                            estado_reporte['doc_id'] = acta_db['code']
                            estado_reporte['firma_receptor_b64'] = acta_db.get('firma_receptor_b64')
                            estado_reporte['firma_receptor_fecha'] = acta_db.get('firma_receptor_fecha')
                            estado_reporte['firma_emisor_b64'] = acta_db.get('firma_emisor_b64')
                            estado_reporte['firma_emisor_fecha'] = acta_db.get('firma_emisor_fecha')

                    if acta_db:
                        with ui.card().classes('w-full p-2.5 bg-gradient-to-br from-indigo-50/70 to-slate-50 border border-indigo-200 rounded-xl gap-2 mt-2 shadow-xs'):
                            with ui.row().classes('items-center justify-between w-full'):
                                with ui.row().classes('items-center gap-1.5'):
                                    ui.icon('assignment_turned_in', size='xs').classes('text-indigo-600')
                                    ui.label(f"Acta: {acta_db['code']}").classes('font-bold text-xs text-indigo-950 font-mono')
                                
                                st = acta_db.get('estado', 'pendiente')
                                if st == 'completada':
                                    ui.badge('✓ TOTALMENTE FIRMADA', color='emerald').props('dense text-color=white').classes('text-[9px] font-bold')
                                elif st == 'firmada_receptor':
                                    ui.badge('✍️ FALTA INGENIERÍA', color='amber').props('dense text-color=white').classes('text-[9px] font-bold')
                                elif st == 'firmada_emisor':
                                    ui.badge('✍️ FALTA RECEPTOR', color='amber').props('dense text-color=white').classes('text-[9px] font-bold')
                                else:
                                    ui.badge('⏳ PENDIENTE FIRMAS', color='grey-7').props('dense text-color=white').classes('text-[9px] font-bold')

                            with ui.column().classes('w-full gap-1 text-[11px] bg-white p-2 rounded-lg border border-indigo-100'):
                                # Receptor
                                f_rec = acta_db.get('firma_receptor_b64')
                                with ui.row().classes('items-center justify-between w-full'):
                                    with ui.row().classes('items-center gap-1'):
                                        ui.icon('person', size='xs').classes('text-slate-500')
                                        ui.label(f"Receptor: {acta_db.get('receptor_nombre', 'Colaborador')}").classes('text-[11px] font-semibold text-slate-800 truncate max-w-[150px]')
                                    if f_rec:
                                        ui.label(f"✓ Firmado ({acta_db.get('firma_receptor_fecha', '')})").classes('text-[9.5px] font-bold text-emerald-600')
                                    else:
                                        ui.label("⏳ Pendiente de firma").classes('text-[9.5px] text-amber-700 italic')
                                
                                # Emisor / Ingeniería
                                f_emi = acta_db.get('firma_emisor_b64')
                                with ui.row().classes('items-center justify-between w-full'):
                                    with ui.row().classes('items-center gap-1'):
                                        ui.icon('engineering', size='xs').classes('text-slate-500')
                                        ui.label(f"Entrega: {acta_db.get('emisor_nombre', 'Ingeniería')}").classes('text-[11px] font-semibold text-slate-800 truncate max-w-[150px]')
                                    if f_emi:
                                        ui.label(f"✓ Firmado ({acta_db.get('firma_emisor_fecha', '')})").classes('text-[9.5px] font-bold text-indigo-600')
                                    else:
                                        ui.label("⏳ Pendiente de firma").classes('text-[9.5px] text-amber-700 italic')

                            # Botones de acción del acta
                            with ui.column().classes('w-full gap-1.5 mt-1'):
                                with ui.row().classes('w-full gap-1'):
                                    ui.button('✍️ Firmar como Ingeniería', icon='draw', on_click=lambda a=acta_db: abrir_modal_firma_ingenieria(a))\
                                        .classes('flex-grow bg-indigo-600 hover:bg-indigo-700 text-white text-[10.5px] font-bold py-1.5 rounded shadow-xs')
                                    
                                    ui.button('🔗 Abrir Acta Virtual', icon='open_in_new', on_click=lambda c=acta_db['code']: ui.navigate.to(f"/acta_entrega/{c}", new_tab=True))\
                                        .props('outline color=indigo').classes('text-[10.5px] font-bold py-1.5 rounded')
                                
                                with ui.row().classes('w-full justify-between items-center px-0.5'):
                                    def sincronizar_acta():
                                        rec_acta = get_delivery_act_by_code(acta_db['code'])
                                        if rec_acta:
                                            estado_reporte['acta_db'] = rec_acta
                                            estado_reporte['firma_receptor_b64'] = rec_acta.get('firma_receptor_b64')
                                            estado_reporte['firma_receptor_fecha'] = rec_acta.get('firma_receptor_fecha')
                                            estado_reporte['firma_emisor_b64'] = rec_acta.get('firma_emisor_b64')
                                            estado_reporte['firma_emisor_fecha'] = rec_acta.get('firma_emisor_fecha')
                                            ui.notify('✓ Estado de firmas sincronizado con éxito', type='positive')
                                            refrescar_subpanel_responsable()
                                            disparar_actualizacion()
                                    ui.button('🔄 Sincronizar Firmas', icon='sync', on_click=sincronizar_acta).props('flat dense size=xs color=grey-8')
                                    
                                    def abrir_modal_reemision():
                                        with ui.dialog() as dlg_reemitir, ui.card().classes('w-[440px] p-5 gap-3 bg-white rounded-xl shadow-xl border border-slate-200'):
                                            with ui.row().classes('items-center gap-2 text-indigo-900 border-b pb-2 w-full'):
                                                ui.icon('restart_alt', size='sm').classes('text-indigo-600')
                                                ui.label('Re-emitir Acta Oficial').classes('text-sm font-bold')
                                                
                                            rec_nom = acta_db.get('receptor_nombre') or 'el colaborador'
                                            ui.label(
                                                f"¿Deseas re-emitir una NUEVA acta oficial limpia para este equipo?\n\n"
                                                f"• Se emitirá un NUEVO folio oficial en blanco para que sea firmada de nuevo por {rec_nom} y por Ingeniería.\n"
                                                f"• Esta nueva acta quedará automáticamente archivada en la gestión de 'Entrega de equipos'.\n"
                                                f"• El colaborador recibirá la notificación en su cuenta para estampar su firma digital."
                                            ).classes('text-xs text-slate-600 whitespace-pre-line leading-relaxed')
                                            
                                            with ui.row().classes('w-full justify-end gap-2 pt-2 border-t border-slate-100'):
                                                ui.button('Cancelar', on_click=dlg_reemitir.close).props('flat dense color=grey-7').classes('text-xs')
                                                def confirmar_reemision():
                                                    dlg_reemitir.close()
                                                    emitir_acta_virtual(force_new=True)
                                                ui.button('✓ Sí, Re-emitir Acta Limpia', icon='send', on_click=confirmar_reemision)\
                                                    .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs py-1.5 px-3 rounded shadow-xs')
                                        dlg_reemitir.open()

                                    ui.button('📤 Re-emitir Acta', icon='send', on_click=abrir_modal_reemision).props('flat dense size=xs color=indigo')
                    else:
                        ui.button('📤 Emitir Acta Virtual y Notificar al Colaborador', icon='send', on_click=lambda: emitir_acta_virtual(force_new=False))\
                            .classes('w-full bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold py-2 rounded-lg shadow-sm mt-2')

            refrescar_subpanel_responsable()

            # SECCIÓN 3: AJUSTES GENERALES Y FORMATO DE PAPEL
            ui.label('3. Formato de Papel y Ajustes Generales').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-2 border-b w-full pb-1')

            # Selector de Formato de Papel (Carta vs A4)
            with ui.column().classes('w-full gap-1 p-2.5 bg-slate-50 border border-slate-200 rounded'):
                ui.label('Formato de Hoja para Impresión:').classes('text-xs font-bold text-slate-800')
                
                def actualizar_formato_papel(e):
                    estado_reporte['formato_papel'] = e.value
                    disparar_actualizacion()
                    ui.notify(f"Formato ajustado a {'Carta (Letter)' if e.value == 'letter' else 'A4'}", type='info')
                    
                ui.radio(
                    options={
                        'letter': '📄 Carta / Letter (21.59 × 27.94 cm) [Predeterminado]',
                        'a4': '📄 A4 (21.0 × 29.7 cm)'
                    },
                    value=estado_reporte.get('formato_papel', 'letter'),
                    on_change=actualizar_formato_papel
                ).props('dense').classes('text-xs text-slate-800')

            # Acomodación Inteligente del Contenedor o Tarjetas
            with ui.column().classes('w-full gap-1 p-2.5 bg-slate-50 border border-slate-200 rounded mt-1'):
                with ui.row().classes('items-center gap-1.5'):
                    ui.icon('tune', size='xs').classes('text-indigo-600')
                    ui.label('Acomodación de Tarjeta / Contenedor:').classes('text-xs font-bold text-slate-800')
                
                def actualizar_acomodacion(e):
                    estado_reporte['acomodacion'] = e.value
                    disparar_actualizacion()
                    
                ui.radio(
                    options={
                        'auto': '⚡ Inteligente (Ajusta espaciado y fotos para evitar espacio muerto)',
                        'compacto': '📦 Compacto (Máxima capacidad de ítems por hoja)',
                        'comodo': '🛋️ Espaciado (Tarjetas amplias y fotos destacadas)'
                    },
                    value=estado_reporte.get('acomodacion', 'auto'),
                    on_change=actualizar_acomodacion
                ).props('dense').classes('text-xs text-slate-800')

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
                save_system_logo(data_uri)
                disparar_actualizacion()
                redibujar_logo_preview()
                ui.notify('Logo aplicado y guardado permanentemente en el sistema', type='positive', icon='cloud_done')

            ui.upload(label='Cargar Logo Persistente (.PNG/.JPG)', on_upload=procesar_archivo_local, auto_upload=True).classes('w-full')
            redibujar_logo_preview()

            def actualizar_titulo_general(e):
                estado_reporte['titulo'] = e.value
                disparar_actualizacion()

            ui.input('Título Principal del Acta', value=estado_reporte.get('titulo', 'ACTA DE ENTREGA DE EQUIPOS'), on_change=actualizar_titulo_general).classes('w-full text-xs').props('outlined dense')

            # ID Único de Generación / Trazabilidad
            with ui.row().classes('w-full gap-2 items-center'):
                def actualizar_doc_id(e):
                    estado_reporte['doc_id'] = e.value
                    disparar_actualizacion()
                    
                input_doc_id = ui.input('ID Único de Generación / Acta', value=estado_reporte.get('doc_id', doc_id_default), on_change=actualizar_doc_id).classes('flex-grow text-xs').props('outlined dense')
                
                def regenerar_id():
                    nuevo_id = f"ACT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                    estado_reporte['doc_id'] = nuevo_id
                    input_doc_id.set_value(nuevo_id)
                    disparar_actualizacion()
                    ui.notify(f'Nuevo código generado: {nuevo_id}', type='info', icon='fingerprint')
                    
                ui.button(icon='refresh', on_click=regenerar_id).props('flat round color=indigo dense').tooltip('Regenerar ID único de generación')

            def actualizar_header_title(e):
                estado_reporte['header_title'] = e.value
                disparar_actualizacion()
                
            def actualizar_header_subtitle(e):
                estado_reporte['header_subtitle'] = e.value
                disparar_actualizacion()
                
            def actualizar_footer_text(e):
                estado_reporte['footer_text'] = e.value
                disparar_actualizacion()

            with ui.row().classes('w-full gap-2'):
                ui.input('Nombre Entidad / Header', value=estado_reporte.get('header_title', 'MEDIAHUB V4'), on_change=actualizar_header_title).classes('flex-grow text-xs').props('outlined dense')
                ui.input('Subtítulo Encabezado', value=estado_reporte.get('header_subtitle', 'Documento Operativo Oficial'), on_change=actualizar_header_subtitle).classes('flex-grow text-xs').props('outlined dense')
                
            ui.input('Pie de Página', value=estado_reporte.get('footer_text', 'Generado por MediaHub V4'), on_change=actualizar_footer_text).classes('w-full text-xs').props('outlined dense')

            # Ajuste dinámico de tamaño de fotos por porcentaje
            with ui.column().classes('w-full gap-1 mt-1'):
                ui.label('Tamaño de Fotos en Acta / Vista Previa:').classes('text-xs font-bold text-gray-700')
                with ui.row().classes('w-full items-center gap-3'):
                    slider_lbl = ui.label(f"{estado_reporte.get('foto_size_pct', 120)}%").classes('text-xs font-bold text-indigo-700 w-12 shrink-0')
                    def actualizar_foto_size(e):
                        estado_reporte['foto_size_pct'] = int(e.value)
                        slider_lbl.set_text(f"{int(e.value)}%")
                        disparar_actualizacion()
                    
                    ui.slider(
                        min=50, max=250, step=10, 
                        value=estado_reporte.get('foto_size_pct', 120), 
                        on_change=actualizar_foto_size
                    ).classes('flex-grow')
                    
            def actualizar_desglosar_kits(e):
                estado_reporte['desglosar_kits'] = e.value
                disparar_actualizacion()

            ui.checkbox('Desglosar Kits / Accesorios en filas independientes', value=estado_reporte.get('desglosar_kits', True), on_change=actualizar_desglosar_kits).classes('text-xs text-slate-700')

            # SECCIÓN 4: TEXTOS DESCRIPTIVOS Y CLÁUSULAS CON AUTOLLENADO
            ui.label('4. Cláusulas y Autollenado').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-2 border-b w-full pb-1')
            
            with ui.column().classes('w-full p-2 bg-indigo-50/70 border border-indigo-200 rounded gap-1'):
                ui.label('💡 Variables automáticas entre [ ] soportadas:').classes('text-[10px] font-bold text-indigo-900')
                ui.label('[RESPONSABLE] • [CORREO] • [CELULAR] • [ROL] • [CEDULA] • [EQUIPOS] • [FECHA] • [ORGANIZACION]').classes('text-[9.5px] font-mono text-indigo-700 font-semibold leading-tight')

            # Cláusula de Apertura
            def toggle_apertura(e):
                estado_reporte['mostrar_clausula_apertura'] = e.value
                textarea_apertura.set_visibility(e.value)
                disparar_actualizacion()

            ui.switch('Incluir Cláusula de Apertura', value=estado_reporte.get('mostrar_clausula_apertura', True), on_change=toggle_apertura).classes('text-xs font-bold text-indigo-900')

            def actualizar_texto_apertura(e):
                estado_reporte['texto_apertura'] = e.value
                disparar_actualizacion()

            textarea_apertura = ui.textarea(
                label='Cláusula de Apertura (Debajo del Título)',
                value=estado_reporte.get('texto_apertura', DEFAULT_APERTURA),
                on_change=actualizar_texto_apertura
            ).classes('w-full text-xs').props('outlined autogrow clearable')
            textarea_apertura.set_visibility(estado_reporte.get('mostrar_clausula_apertura', True))

            # Cláusula de Cierre
            def toggle_cierre(e):
                estado_reporte['mostrar_clausula_cierre'] = e.value
                textarea_cierre.set_visibility(e.value)
                disparar_actualizacion()

            ui.switch('Incluir Cláusula de Cierre y Declaraciones', value=estado_reporte.get('mostrar_clausula_cierre', True), on_change=toggle_cierre).classes('text-xs font-bold text-indigo-900 mt-2')

            def actualizar_texto_cierre(e):
                estado_reporte['texto_cierre'] = e.value
                disparar_actualizacion()

            textarea_cierre = ui.textarea(
                label='Declaraciones y Cláusulas de Cierre (Al Pie de la Tabla)',
                value=estado_reporte.get('texto_cierre', DEFAULT_CIERRE),
                on_change=actualizar_texto_cierre
            ).classes('w-full text-xs').props('outlined autogrow clearable')
            textarea_cierre.set_visibility(estado_reporte.get('mostrar_clausula_cierre', True))

            # SECCIÓN 5: FIRMAS LEGALES
            ui.label('5. Sección de Firmas').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-2 border-b w-full pb-1')

            firmas_config_box = ui.column().classes('w-full gap-2')

            def refrescar_firmas_config_ui():
                firmas_config_box.clear()
                with firmas_config_box:
                    def toggle_firmas(e):
                        estado_reporte['mostrar_firmas'] = e.value
                        refrescar_firmas_config_ui()
                        disparar_actualizacion()

                    ui.switch('Habilitar Sección de Firmas al Final', value=estado_reporte.get('mostrar_firmas', True), on_change=toggle_firmas).classes('text-xs font-bold text-indigo-900')

                    if estado_reporte.get('mostrar_firmas', True):
                        with ui.card().classes('w-full p-3 bg-gray-50 border border-gray-200 shadow-sm gap-2'):
                            ui.label('Firma 1 (Principal / Receptor)').classes('text-xs font-bold text-gray-700')
                            
                            def actualizar_f1_tit(e):
                                estado_reporte['firma_1_titulo'] = e.value
                                disparar_actualizacion()
                            ui.input('Título / Cargo Firma 1', value=estado_reporte.get('firma_1_titulo', 'Firma de Recibido'), on_change=actualizar_f1_tit).classes('w-full text-xs').props('outlined dense')
                            
                            def actualizar_f1_sub(e):
                                estado_reporte['firma_1_subtitulo'] = e.value
                                disparar_actualizacion()
                            ui.input('Aclaración / C.C.', value=estado_reporte.get('firma_1_subtitulo', '[RESPONSABLE] / C.C.'), on_change=actualizar_f1_sub).classes('w-full text-xs').props('outlined dense')

                            def toggle_f2(e):
                                estado_reporte['mostrar_firma_2'] = e.value
                                refrescar_firmas_config_ui()
                                disparar_actualizacion()

                            ui.checkbox('Habilitar Segunda Firma (Emisor / Empresa)', value=estado_reporte.get('mostrar_firma_2', True), on_change=toggle_f2).classes('text-xs mt-2')

                            if estado_reporte.get('mostrar_firma_2', True):
                                ui.label('Firma 2 (Secundaria / Emisor)').classes('text-xs font-bold text-gray-700 mt-1')
                                def actualizar_f2_tit(e):
                                    estado_reporte['firma_2_titulo'] = e.value
                                    disparar_actualizacion()
                                ui.input('Título / Cargo Firma 2', value=estado_reporte.get('firma_2_titulo', 'Entregado Por'), on_change=actualizar_f2_tit).classes('w-full text-xs').props('outlined dense')
                                
                                def actualizar_f2_sub(e):
                                    estado_reporte['firma_2_subtitulo'] = e.value
                                    disparar_actualizacion()
                                ui.input('Aclaración / Área Firma 2', value=estado_reporte.get('firma_2_subtitulo', 'Departamento de Ingeniería'), on_change=actualizar_f2_sub).classes('w-full text-xs').props('outlined dense')

            refrescar_firmas_config_ui()

            # SECCIÓN 6: COLUMNAS Y MAPEO
            ui.label('6. Columnas de la Tabla').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-2 border-b w-full pb-1')

            builder_col_container = ui.column().classes('w-full gap-2')

            def redibujar_panel_columnas():
                builder_col_container.clear()
                with builder_col_container:
                    for idx, col in enumerate(estado_reporte['columnas']):
                        with ui.card().classes('w-full p-3 bg-gray-50 border border-gray-200 shadow-sm'):
                            with ui.row().classes('w-full justify-between items-center mb-1'):
                                ui.label(f'Columna {idx + 1}').classes('font-bold text-indigo-800 text-xs')
                                
                                def eliminar_col(c=col):
                                    estado_reporte['columnas'].remove(c)
                                    redibujar_panel_columnas()
                                    disparar_actualizacion()
                                ui.button(icon='delete', on_click=eliminar_col).props('flat color=red round size=sm').tooltip('Eliminar Columna')

                            def actualizar_titulo_col(e, c=col):
                                c['titulo'] = e.value
                                disparar_actualizacion()
                            ui.input('Título de Columna', value=col['titulo'], on_change=actualizar_titulo_col).classes('w-full mb-1 text-xs').props('outlined dense')

                            def actualizar_campos_col(e, c=col):
                                c['campos'] = e.value
                                disparar_actualizacion()
                                
                            ui.select(
                                options=opciones_campos,
                                value=col['campos'],
                                multiple=True,
                                label='Campos en esta columna',
                                on_change=actualizar_campos_col
                            ).props('use-chips outlined dense').classes('w-full text-xs')

            redibujar_panel_columnas()

            def agregar_columna():
                if len(estado_reporte['columnas']) >= 5:
                    ui.notify('Máximo 5 columnas para evitar desborde en el formato A4', type='warning')
                    return
                estado_reporte['columnas'].append({'id': str(uuid.uuid4()), 'titulo': 'Nueva Columna', 'campos': []})
                redibujar_panel_columnas()
                disparar_actualizacion()

            ui.button('Añadir Columna', icon='add_box', on_click=agregar_columna).classes('w-full bg-indigo-50 text-indigo-800 shadow-none hover:bg-indigo-100 py-1.5 mt-1 text-xs')

        # Botones de Descarga/Exportación
        with ui.column().classes('w-full p-4 border-t border-gray-200 bg-gray-50 shrink-0 gap-2'):
            ui.label('7. Exportación').classes('text-xs font-bold text-gray-500 uppercase tracking-wider')
            ui.button('Descargar PDF Completo', icon='picture_as_pdf', on_click=disparar_descarga_pdf).classes('w-full bg-red-600 text-white font-bold py-2 shadow-md text-xs')
            ui.button('Descargar JPG (Pág 1)', icon='image', on_click=disparar_descarga_jpg).classes('w-full bg-indigo-600 text-white font-bold py-2 shadow-md text-xs')

    # Ejecución inicial
    disparar_actualizacion()
