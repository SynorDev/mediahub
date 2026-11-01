from nicegui import ui
import io
import csv
import math
import openpyxl
try:
    import xlrd
except ImportError:
    xlrd = None
from database import (
    get_all_custom_modules, get_all_categories, bulk_add_custom_records, bulk_add_categories
)

def auto_detect_mapping(excel_headers: list, target_label: str) -> str:
    """
    Intenta adivinar la columna de Excel más adecuada para un campo objetivo.
    """
    lbl_lower = target_label.lower()
    for header in excel_headers:
        hdr_lower = str(header).strip().lower()
        if not hdr_lower:
            continue
        if 'nombre' in lbl_lower or 'modelo' in lbl_lower or 'equipo' in lbl_lower:
            if any(k in hdr_lower for k in ['descrip', 'nombre', 'equipo', 'modelo', 'articulo']):
                return header
        elif 'marca' in lbl_lower:
            if 'marca' in hdr_lower or 'fabricante' in hdr_lower:
                return header
        elif 'categor' in lbl_lower:
            if any(k in hdr_lower for k in ['categ', 'tipo', 'clase', 'familia', 'grupo']):
                return header
        elif 'serie' in lbl_lower or 'serial' in lbl_lower:
            if any(k in hdr_lower for k in ['serie', 'serial', 'sn', 's/n', 'placa']):
                return header
        elif 'ubicaci' in lbl_lower:
            if any(k in hdr_lower for k in ['ubic', 'lugar', 'sitio', 'sede', 'area', 'departamento']):
                return header
        elif 'estado' in lbl_lower:
            if any(k in hdr_lower for k in ['estado', 'status', 'condicion']):
                return header
        elif 'responsable' in lbl_lower or 'custodio' in lbl_lower:
            if any(k in hdr_lower for k in ['responsable', 'custodio', 'asignado', 'encargado', 'usuario']):
                return header
        elif 'observac' in lbl_lower or 'nota' in lbl_lower:
            if any(k in hdr_lower for k in ['observ', 'nota', 'comentario', 'detalle']):
                return header
    return None

def parse_uploaded_file(file_bytes: bytes, filename: str) -> tuple[list, list]:
    """
    Lee bytes de un archivo (.xlsx, .xls, .csv) y retorna (headers, rows).
    rows es una lista de diccionarios {header: valor}.
    """
    filename_lower = filename.lower()
    is_zip = file_bytes.startswith(b'PK\x03\x04')
    is_ole = file_bytes.startswith(b'\xd0\xcf\x11\xe0')
    headers = []
    raw_rows = []

    if is_zip or filename_lower.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        all_rows = list(sheet.iter_rows(values_only=True))
        if not all_rows:
            return [], []
        
        header_row_idx = 0
        for idx, row in enumerate(all_rows):
            if any(cell is not None and str(cell).strip() != '' for cell in row):
                headers = [str(cell).strip() if cell is not None else f"Columna_{i+1}" for i, cell in enumerate(row)]
                header_row_idx = idx
                break
                
        for row in all_rows[header_row_idx + 1:]:
            if not any(cell is not None and str(cell).strip() != '' for cell in row):
                continue
            row_dict = {}
            for col_idx, cell_value in enumerate(row):
                if col_idx < len(headers):
                    hdr_key = headers[col_idx]
                    row_dict[hdr_key] = "" if cell_value is None else str(cell_value).strip()
            raw_rows.append(row_dict)

    elif is_ole or filename_lower.endswith('.xls'):
        if xlrd is None:
            raise ImportError("Para procesar archivos .xls se requiere 'xlrd'. Ejecute 'pip install xlrd' en su entorno virtual (venv).")
        book = xlrd.open_workbook(file_contents=file_bytes)
        sheet = book.sheet_by_index(0)
        all_rows = []
        for r in range(sheet.nrows):
            row_vals = []
            for c in range(sheet.ncols):
                val = sheet.cell_value(r, c)
                cell_type = sheet.cell_type(r, c)
                if cell_type == xlrd.XL_CELL_DATE:
                    try:
                        dt = xlrd.xldate_as_datetime(val, book.datemode)
                        val = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                elif cell_type == xlrd.XL_CELL_NUMBER and isinstance(val, float) and val.is_integer():
                    val = int(val)
                row_vals.append(val if val != '' else None)
            all_rows.append(row_vals)
            
        if not all_rows:
            return [], []
        
        header_row_idx = 0
        for idx, row in enumerate(all_rows):
            if any(cell is not None and str(cell).strip() != '' for cell in row):
                headers = [str(cell).strip() if cell is not None else f"Columna_{i+1}" for i, cell in enumerate(row)]
                header_row_idx = idx
                break
                
        for row in all_rows[header_row_idx + 1:]:
            if not any(cell is not None and str(cell).strip() != '' for cell in row):
                continue
            row_dict = {}
            for col_idx, cell_value in enumerate(row):
                if col_idx < len(headers):
                    hdr_key = headers[col_idx]
                    row_dict[hdr_key] = "" if cell_value is None else str(cell_value).strip()
            raw_rows.append(row_dict)

    elif filename_lower.endswith('.csv'):
        text_content = ""
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
            try:
                text_content = file_bytes.decode(encoding)
                break
            except Exception:
                continue
        
        if not text_content:
            return [], []

        first_line = text_content.splitlines()[0] if text_content.splitlines() else ""
        delimiter = ';' if ';' in first_line and first_line.count(';') > first_line.count(',') else ','
        if '\t' in first_line and first_line.count('\t') > first_line.count(delimiter):
            delimiter = '\t'

        reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
        all_rows = list(reader)
        if not all_rows:
            return [], []

        headers = [str(cell).strip() for cell in all_rows[0]]
        for row in all_rows[1:]:
            if not any(cell.strip() != '' for cell in row):
                continue
            row_dict = {}
            for col_idx, cell_value in enumerate(row):
                if col_idx < len(headers):
                    hdr_key = headers[col_idx]
                    row_dict[hdr_key] = cell_value.strip()
            raw_rows.append(row_dict)

    return headers, raw_rows


def open_excel_importer_dialog(module_info=None, on_success_callback=None):
    """
    Abre el modal interactivo de importación masiva en 3 pasos con layout compatible con Quasar.
    """
    if not module_info:
        modules = get_all_custom_modules()
        module_info = next((m for m in modules if m['id'] == 'system_inventory'), None)
        if not module_info and modules:
            module_info = modules[0]

    module_id = module_info['id'] if module_info else 'system_inventory'
    raw_fields = module_info['config'] if module_info else []
    
    # Filtrar solo campos de datos mapeables (excluir imágenes y accesorios)
    fields = []
    for idx, f in enumerate(raw_fields):
        if f.get('type') in ['images', 'accessories']:
            continue
        f_copy = dict(f)
        if 'key' not in f_copy:
            f_copy['key'] = f"field_{idx}"
        fields.append(f_copy)

    if not fields:
        fields = [
            {"key": "field_0", "label": "Nombre / Modelo", "type": "text"},
            {"key": "field_1", "label": "Categoría", "type": "text"},
            {"key": "field_2", "label": "Número de Serie (Serial)", "type": "text"},
            {"key": "field_3", "label": "Cantidad", "type": "number"},
            {"key": "field_7", "label": "Tipo de Asignación", "type": "select", "options": ["Inventario Fijo", "Préstamo", "Alquiler"]},
            {"key": "field_8", "label": "Contenedor / Grupo", "type": "select", "options": ["Ninguno", "Contenedor Principal"]},
            {"key": "field_9", "label": "Estado del Artículo", "type": "select", "options": ["En uso", "En desuso", "En bodega", "De baja"]}
        ]

    # Encontrar la clave del campo de Nombre / Modelo principal
    name_field_key = fields[0]['key']
    for f in fields:
        lbl = f['label'].lower()
        if 'nombre' in lbl or 'modelo' in lbl or 'equipo' in lbl:
            name_field_key = f['key']
            break

    import_state = {
        'step': 1,
        'filename': '',
        'headers': [],
        'raw_rows': [],
        'column_mappings': {},
        'combine_name_cols': False,
        'name_cols_list': [],
        'batch_defaults': {
            'estado': 'En uso',
            'tipo_asignacion': 'Inventario Fijo',
            'categoria_default': 'GENERAL',
            'ubicacion_default': 'Bodega Principal',
            'empty_as_na': True
        },
        'processed_rows': [],
        'page': 1,
        'per_page': 15
    }

    categorias_existentes = [c['nombre_categoria'] for c in get_all_categories()]
    if not categorias_existentes:
        categorias_existentes = ['GENERAL', 'TECNOLOGIA', 'EQUIPOS']

    # Contenedor Quasar Card con scroll vertical interno estándar
    with ui.dialog() as dlg, ui.card().classes('w-[940px] max-w-[95vw] max-h-[88vh] overflow-y-auto bg-gray-50 p-6 rounded-2xl shadow-2xl gap-4'):
        
        # --- HEADER PERMANENTE ---
        with ui.row().classes('w-full justify-between items-center pb-3 border-b border-gray-200'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('file_upload', size='md').classes('text-green-600')
                ui.label('Importador de Inventario desde Excel / CSV').classes('text-xl font-bold text-gray-800')
            ui.button(icon='close', on_click=dlg.close).props('flat round size=sm color=gray')

        # Header del Indicador de Pasos
        steps_header_container = ui.row().classes('w-full justify-around items-center bg-white p-2.5 rounded-lg border border-gray-200 shadow-sm text-xs font-bold')

        # --- CUERPO PRINCIPAL DE LOS PASOS ---
        wizard_body = ui.column().classes('w-full gap-4')

        def render_wizard():
            steps_header_container.clear()
            wizard_body.clear()

            step = import_state['step']

            with steps_header_container:
                p1_cls = 'text-green-600 font-extrabold border-b-2 border-green-600 pb-0.5' if step == 1 else 'text-gray-400'
                p2_cls = 'text-green-600 font-extrabold border-b-2 border-green-600 pb-0.5' if step == 2 else 'text-gray-400'
                p3_cls = 'text-green-600 font-extrabold border-b-2 border-green-600 pb-0.5' if step == 3 else 'text-gray-400'

                ui.label('1. Cargar Archivo (.xlsx / .csv)').classes(p1_cls)
                ui.icon('chevron_right', size='xs').classes('text-gray-400')
                ui.label('2. Homologación & Lotes').classes(p2_cls)
                ui.icon('chevron_right', size='xs').classes('text-gray-400')
                ui.label('3. Vista Previa & Confirmar').classes(p3_cls)

            # ==========================================
            # PASO 1: CARGA DE ARCHIVO
            # ==========================================
            if step == 1:
                with wizard_body:
                    with ui.column().classes('w-full items-center p-10 bg-white rounded-xl border-2 border-dashed border-gray-300 gap-4 text-center my-4 shadow-sm'):
                        ui.icon('cloud_upload', size='4rem').classes('text-green-500 animate-bounce')
                        ui.label('Selecciona un archivo Excel (.xlsx, .xls) o CSV (.csv)').classes('text-lg font-semibold text-gray-700')
                        ui.label('El sistema leerá las filas y te permitirá homologar las columnas en el siguiente paso.').classes('text-xs text-gray-500')

                        async def handle_file_upload(e):
                            try:
                                bytes_data = await e.file.read()
                                fname = e.file.name
                                headers, rows = parse_uploaded_file(bytes_data, fname)

                                if not headers or not rows:
                                    ui.notify('No se pudieron extraer datos del archivo subido. Verifica el formato.', type='negative')
                                    return

                                import_state['filename'] = fname
                                import_state['headers'] = headers
                                import_state['raw_rows'] = rows
                                import_state['column_mappings'] = {}

                                NO_MAP = '-- Ninguna (Usar valor en lote) --'
                                for f in fields:
                                    f_key = f['key']
                                    matched = auto_detect_mapping(headers, f['label'])
                                    import_state['column_mappings'][f_key] = matched if matched else NO_MAP

                                import_state['step'] = 2
                                ui.notify(f"Archivo '{fname}' cargado: {len(rows)} filas encontradas.", type='positive')
                                render_wizard()
                            except Exception as ex:
                                ui.notify(f"Error al procesar archivo: {str(ex)}", type='negative')

                        ui.upload(
                            label='Examinar o Soltar Archivo Aquí',
                            on_upload=handle_file_upload,
                            auto_upload=True
                        ).props('accept=.xlsx,.xls,.csv').classes('w-full max-w-md')

                    # Footer Paso 1
                    with ui.row().classes('w-full justify-between items-center mt-4 pt-3 border-t border-gray-200'):
                        ui.button('Cancelar', on_click=dlg.close).props('flat text-gray-500')

            # ==========================================
            # PASO 2: HOMOLOGACIÓN Y VALORES EN LOTE
            # ==========================================
            elif step == 2:
                step2_inputs = {}

                with wizard_body:
                    # Banner del archivo
                    with ui.row().classes('w-full bg-blue-50 border-l-4 border-blue-500 p-3 rounded-lg items-center justify-between shadow-sm'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('analytics', color='primary')
                            ui.label(f"Archivo: {import_state['filename']} ({len(import_state['raw_rows'])} filas cargadas)").classes('font-bold text-sm text-blue-900')
                        ui.button('Cambiar Archivo', icon='refresh', on_click=lambda: [import_state.update({'step': 1}), render_wizard()]).props('flat size=xs color=primary')

                    # SECCIÓN 1: HOMOLOGACIÓN DE COLUMNAS
                    with ui.card().classes('w-full p-5 bg-white border border-gray-200 shadow-sm rounded-xl gap-3'):
                        with ui.row().classes('w-full items-center justify-between border-b pb-2 mb-1'):
                            ui.label('1. Homologar Campos (Mapeo de Columnas del Excel -> Campos del Sistema)').classes('text-sm font-bold text-gray-800')
                            ui.label(f"{len(fields)} campos detectados").classes('text-xs text-indigo-600 font-semibold bg-indigo-50 px-2 py-0.5 rounded')

                        NO_MAP = '-- Ninguna (Usar valor en lote) --'
                        header_options = [NO_MAP] + import_state['headers']

                        # Opción de concatenar columnas compuestas (Ej. DESCRIPCION + MARCA + MODELO)
                        with ui.row().classes('w-full items-center bg-indigo-50 p-3 rounded-lg border border-indigo-200'):
                            chk_combine = ui.checkbox('Combinar múltiples columnas del Excel para el Nombre / Modelo (Ej: DESCRIPCION + MARCA + MODELO)', value=import_state['combine_name_cols'])
                            
                        name_combo_container = ui.row().classes('w-full gap-2 p-3 bg-white rounded-lg border border-indigo-300 shadow-sm' if chk_combine.value else 'hidden')
                        
                        with name_combo_container:
                            ui.label('Selecciona las columnas del Excel a combinar en el orden deseado:').classes('w-full text-xs font-bold text-indigo-900')
                            c1 = ui.select(header_options, label='Columna 1 (Ej: DESCRIPCION)', value=import_state['name_cols_list'][0] if len(import_state['name_cols_list'])>0 else (header_options[1] if len(header_options)>1 else NO_MAP)).classes('w-1/3 text-xs')
                            c2 = ui.select(header_options, label='Columna 2 (Ej: MARCA)', value=import_state['name_cols_list'][1] if len(import_state['name_cols_list'])>1 else NO_MAP).classes('w-1/3 text-xs')
                            c3 = ui.select(header_options, label='Columna 3 (Ej: MODELO)', value=import_state['name_cols_list'][2] if len(import_state['name_cols_list'])>2 else NO_MAP).classes('w-1/3 text-xs')

                        def toggle_combine(e):
                            import_state['combine_name_cols'] = e.value
                            if e.value:
                                name_combo_container.remove_classes('hidden')
                            else:
                                name_combo_container.add_classes('hidden')
                        chk_combine.on('change', toggle_combine)

                        # Rejilla de selectores de homologación por cada campo del sistema
                        mapping_inputs = {}
                        with ui.grid().classes('grid-cols-1 md:grid-cols-2 gap-3 w-full mt-2'):
                            for f in fields:
                                f_key = f['key']
                                f_label = f['label']
                                val_actual = import_state['column_mappings'].get(f_key, NO_MAP)
                                if val_actual not in header_options:
                                    val_actual = NO_MAP
                                    
                                with ui.column().classes('w-full p-3 bg-gray-50 rounded-lg border border-gray-200'):
                                    with ui.row().classes('w-full justify-between items-center mb-1'):
                                        ui.label(f_label).classes('text-xs font-bold text-gray-800')
                                        if f_key == name_field_key:
                                            ui.label('Campo Principal').classes('text-[10px] bg-green-100 text-green-800 px-1.5 py-0.5 rounded font-bold')
                                    sel = ui.select(header_options, value=val_actual).classes('w-full text-xs')
                                    mapping_inputs[f_key] = sel

                        step2_inputs['mapping_inputs'] = mapping_inputs
                        step2_inputs['chk_combine'] = chk_combine
                        step2_inputs['c1'] = c1
                        step2_inputs['c2'] = c2
                        step2_inputs['c3'] = c3

                    # SECCIÓN 2: CONFIGURACIÓN EN LOTE PARA FALTANTES
                    with ui.card().classes('w-full p-5 bg-white border border-gray-200 shadow-sm rounded-xl gap-3'):
                        ui.label('2. Configuración por Lote (Para campos sin mapear o celdas vacías)').classes('text-sm font-bold text-gray-800 border-b pb-2 mb-1')
                        
                        with ui.grid().classes('grid-cols-1 md:grid-cols-3 gap-3 w-full'):
                            b_estado = ui.select(
                                ['En uso', 'En desuso', 'En bodega', 'De baja'],
                                label='Estado del Artículo (Lote)',
                                value=import_state['batch_defaults']['estado']
                            ).classes('w-full text-xs')

                            b_tipo = ui.select(
                                ['Inventario Fijo', 'Préstamo', 'Alquiler'],
                                label='Tipo de Asignación (Lote)',
                                value=import_state['batch_defaults']['tipo_asignacion']
                            ).classes('w-full text-xs')

                            b_cat = ui.select(
                                categorias_existentes + ['OTRA / CREAR NUEVA'],
                                label='Categoría por Defecto',
                                value=import_state['batch_defaults']['categoria_default'] if import_state['batch_defaults']['categoria_default'] in categorias_existentes else categorias_existentes[0]
                            ).classes('w-full text-xs')

                            b_ubicacion = ui.input(
                                'Ubicación / Contenedor (Lote)',
                                value=import_state['batch_defaults']['ubicacion_default']
                            ).classes('w-full text-xs')

                        with ui.row().classes('w-full items-center mt-2 pt-2 border-t border-gray-100'):
                            b_na_chk = ui.checkbox(
                                'Poner "N/A" automáticamente en celdas de texto que queden en blanco o vacías',
                                value=import_state['batch_defaults']['empty_as_na']
                            ).classes('text-xs text-gray-700 font-medium')

                        step2_inputs['b_estado'] = b_estado
                        step2_inputs['b_tipo'] = b_tipo
                        step2_inputs['b_cat'] = b_cat
                        step2_inputs['b_ubicacion'] = b_ubicacion
                        step2_inputs['b_na_chk'] = b_na_chk

                    def procesar_vista_previa():
                        NO_MAP = '-- Ninguna (Usar valor en lote) --'
                        for f_key, sel_in in step2_inputs['mapping_inputs'].items():
                            import_state['column_mappings'][f_key] = sel_in.value if sel_in.value != NO_MAP else None
                        
                        chk = step2_inputs['chk_combine']
                        import_state['combine_name_cols'] = chk.value
                        if chk.value:
                            import_state['name_cols_list'] = [step2_inputs['c1'].value, step2_inputs['c2'].value, step2_inputs['c3'].value]

                        import_state['batch_defaults']['estado'] = step2_inputs['b_estado'].value
                        import_state['batch_defaults']['tipo_asignacion'] = step2_inputs['b_tipo'].value
                        import_state['batch_defaults']['categoria_default'] = step2_inputs['b_cat'].value
                        import_state['batch_defaults']['ubicacion_default'] = step2_inputs['b_ubicacion'].value.strip() or 'Bodega Principal'
                        import_state['batch_defaults']['empty_as_na'] = step2_inputs['b_na_chk'].value

                        processed = []
                        empty_replacement = "N/A" if step2_inputs['b_na_chk'].value else ""

                        for row_idx, r in enumerate(import_state['raw_rows']):
                            rec_data = {}
                            
                            for f in fields:
                                f_key = f['key']
                                f_label = f['label']
                                f_type = f['type']
                                hdr_mapped = import_state['column_mappings'].get(f_key)

                                if f_key == name_field_key and import_state['combine_name_cols']:
                                    partes = []
                                    for col_h in import_state['name_cols_list']:
                                        if col_h and col_h != NO_MAP and col_h in r:
                                            v = str(r[col_h]).strip()
                                            if v: partes.append(v)
                                    rec_data[f_key] = " - ".join(partes) if partes else (empty_replacement or f"Equipo_{row_idx+1}")
                                
                                elif hdr_mapped and hdr_mapped in r:
                                    val_raw = str(r[hdr_mapped]).strip()
                                    if val_raw:
                                        if f_type == 'number':
                                            try: rec_data[f_key] = int(float(val_raw))
                                            except Exception: rec_data[f_key] = 1
                                        else:
                                            rec_data[f_key] = val_raw
                                    else:
                                        if f_type == 'number': rec_data[f_key] = 1
                                        else: rec_data[f_key] = empty_replacement
                                
                                else:
                                    if f_key == name_field_key:
                                        rec_data[f_key] = f"Equipo_{row_idx+1}"
                                    elif 'cat' in f_label.lower():
                                        rec_data[f_key] = step2_inputs['b_cat'].value if step2_inputs['b_cat'].value != 'OTRA / CREAR NUEVA' else 'GENERAL'
                                    elif 'serial' in f_label.lower():
                                        rec_data[f_key] = empty_replacement
                                    elif f_type == 'number':
                                        rec_data[f_key] = 1
                                    elif 'tipo' in f_label.lower() and 'asignac' in f_label.lower():
                                        rec_data[f_key] = step2_inputs['b_tipo'].value
                                    elif 'estado' in f_label.lower():
                                        rec_data[f_key] = step2_inputs['b_estado'].value
                                    elif 'ubicac' in f_label.lower() or 'contenedor' in f_label.lower() or 'grupo' in f_label.lower():
                                        rec_data[f_key] = step2_inputs['b_ubicacion'].value.strip() or 'Bodega Principal'
                                    else:
                                        rec_data[f_key] = empty_replacement

                            processed.append(rec_data)

                        import_state['processed_rows'] = processed
                        import_state['page'] = 1
                        import_state['step'] = 3
                        render_wizard()

                    # BARRA DE ACCIÓN PEGAJOSA FIJA EN PASO 2
                    with ui.row().classes('w-full justify-between items-center mt-4 pt-3 border-t border-gray-300 bg-white p-4 rounded-xl shadow-lg sticky bottom-0 z-30'):
                        ui.button('Cancelar', on_click=dlg.close).props('flat text-gray-500 font-bold')
                        ui.button('Generar Vista Previa', icon='arrow_forward', on_click=procesar_vista_previa).classes('bg-green-600 hover:bg-green-700 text-white font-extrabold text-sm px-8 py-3 rounded-xl shadow-xl transform transition-transform hover:scale-105')

            # ==========================================
            # PASO 3: VISTA PREVIA Y EDICIÓN PUNTUAL
            # ==========================================
            elif step == 3:
                processed = import_state['processed_rows']
                
                cat_key = next((f['key'] for f in fields if 'cat' in f['label'].lower()), 'field_1')
                cats_detectadas = set()
                for r in processed:
                    val_c = str(r.get(cat_key, '')).strip()
                    if val_c and val_c != 'N/A':
                        cats_detectadas.add(val_c)

                cats_nuevas = [c for c in cats_detectadas if c not in categorias_existentes]

                with wizard_body:
                    # Tarjetas Resumen
                    with ui.row().classes('w-full gap-4 items-center'):
                        with ui.card().classes('w-1/2 p-3 bg-green-50 border border-green-200 rounded-xl flex flex-row items-center gap-3 shadow-sm'):
                            ui.icon('inventory_2', size='md').classes('text-green-700')
                            with ui.column().classes('gap-0'):
                                ui.label(f"{len(processed)} Equipos Listos para Importar").classes('font-bold text-sm text-green-900')
                                ui.label('Revisa la tabla abajo o edita filas individualmente').classes('text-xs text-green-700')

                        with ui.card().classes('w-1/2 p-3 bg-indigo-50 border border-indigo-200 rounded-xl flex flex-row items-center gap-3 shadow-sm'):
                            ui.icon('category', size='md').classes('text-indigo-700')
                            with ui.column().classes('gap-0'):
                                ui.label(f"{len(cats_nuevas)} Categorías Nuevas a Registrar").classes('font-bold text-sm text-indigo-900')
                                ui.label(f"Nuevas: {', '.join(cats_nuevas[:4]) if cats_nuevas else 'Ninguna (usando existentes)'}").classes('text-xs text-indigo-700 truncate max-w-xs')

                    # Paginación Superior
                    with ui.row().classes('w-full justify-between items-center mt-1 bg-white p-2.5 rounded-xl border border-gray-200 shadow-sm'):
                        ui.label('Tabla de Vista Previa (Edición Puntual en Vivo):').classes('text-xs font-bold text-gray-700')
                        
                        total_pages = max(1, math.ceil(len(processed) / import_state['per_page']))
                        curr_p = max(1, min(import_state['page'], total_pages))
                        import_state['page'] = curr_p

                        start_idx = (curr_p - 1) * import_state['per_page']
                        end_idx = min(start_idx + import_state['per_page'], len(processed))

                        with ui.row().classes('items-center gap-2 text-xs'):
                            def pag_prev():
                                if import_state['page'] > 1:
                                    import_state['page'] -= 1
                                    refrescar_grilla_preview()

                            def pag_next():
                                if import_state['page'] < total_pages:
                                    import_state['page'] += 1
                                    refrescar_grilla_preview()

                            ui.button(icon='chevron_left', on_click=pag_prev).props('flat dense round size=xs').classes('border')
                            ui.label(f"Página {curr_p} de {total_pages} (Filas {start_idx+1}-{end_idx} de {len(processed)})").classes('font-bold text-gray-700')
                            ui.button(icon='chevron_right', on_click=pag_next).props('flat dense round size=xs').classes('border')

                    # Grilla de filas editables
                    grid_rows_container = ui.column().classes('w-full min-h-[220px] max-h-[320px] overflow-y-auto bg-white border border-gray-300 rounded-xl shadow-inner p-2 gap-1.5')
                    
                    def refrescar_grilla_preview():
                        grid_rows_container.clear()
                        tot_p = max(1, math.ceil(len(processed) / import_state['per_page']))
                        c_page = max(1, min(import_state['page'], tot_p))
                        import_state['page'] = c_page

                        st_idx = (c_page - 1) * import_state['per_page']
                        ed_idx = min(st_idx + import_state['per_page'], len(processed))
                        page_items = processed[st_idx:ed_idx]

                        k_nom = name_field_key
                        k_cat = next((f['key'] for f in fields if 'cat' in f['label'].lower()), 'field_1')
                        k_ser = next((f['key'] for f in fields if 'serial' in f['label'].lower() or 'serie' in f['label'].lower()), 'field_2')
                        k_cant = next((f['key'] for f in fields if 'cantidad' in f['label'].lower()), 'field_3')
                        k_tipo = next((f['key'] for f in fields if 'tipo' in f['label'].lower()), 'field_7')
                        k_est = next((f['key'] for f in fields if 'estado' in f['label'].lower()), 'field_9')

                        with grid_rows_container:
                            if not processed:
                                ui.label('No hay filas en el lote. Se han eliminado todas.').classes('text-gray-400 italic text-xs text-center py-6 w-full')
                            else:
                                with ui.row().classes('w-full font-bold text-xs text-gray-600 border-b pb-1 px-2 flex-nowrap items-center gap-2 bg-gray-100 rounded sticky top-0 z-10 shadow-sm'):
                                    ui.label('#').classes('w-8 text-center')
                                    ui.label('Nombre / Modelo').classes('w-44 truncate')
                                    ui.label('Categoría').classes('w-28 truncate')
                                    ui.label('Serial').classes('w-28 truncate')
                                    ui.label('Cant.').classes('w-12 text-center')
                                    ui.label('Tipo').classes('w-24 truncate')
                                    ui.label('Estado').classes('w-24 truncate')
                                    ui.label('Acciones').classes('w-16 text-center')

                                for offset, r in enumerate(page_items):
                                    real_idx = st_idx + offset
                                    with ui.row().classes('w-full text-xs items-center gap-2 px-2 py-1 border-b border-gray-100 hover:bg-blue-50 transition-colors flex-nowrap'):
                                        ui.label(str(real_idx + 1)).classes('w-8 text-center text-gray-400 font-mono')
                                        
                                        in_nom = ui.input(value=r.get(k_nom, 'N/A')).classes('w-44 text-xs').props('dense compact')
                                        in_cat = ui.input(value=r.get(k_cat, 'GENERAL')).classes('w-28 text-xs').props('dense compact')
                                        in_ser = ui.input(value=r.get(k_ser, 'N/A')).classes('w-28 text-xs').props('dense compact')
                                        in_cant = ui.number(value=r.get(k_cant, 1), format='%d').classes('w-12 text-xs').props('dense compact')
                                        in_tipo = ui.select(['Inventario Fijo', 'Préstamo', 'Alquiler'], value=r.get(k_tipo, 'Inventario Fijo')).classes('w-24 text-xs').props('dense compact')
                                        in_est = ui.select(['En uso', 'En desuso', 'En bodega', 'De baja'], value=r.get(k_est, 'En uso')).classes('w-24 text-xs').props('dense compact')

                                        def bind_change(row_ref=r, n=in_nom, c=in_cat, s=in_ser, q=in_cant, t=in_tipo, e=in_est):
                                            row_ref[k_nom] = n.value.strip() or 'N/A'
                                            row_ref[k_cat] = c.value.strip() or 'GENERAL'
                                            row_ref[k_ser] = s.value.strip() or 'N/A'
                                            row_ref[k_cant] = int(q.value or 1)
                                            row_ref[k_tipo] = t.value
                                            row_ref[k_est] = e.value

                                        in_nom.on('change', lambda _, fn=bind_change: fn())
                                        in_cat.on('change', lambda _, fn=bind_change: fn())
                                        in_ser.on('change', lambda _, fn=bind_change: fn())
                                        in_cant.on('change', lambda _, fn=bind_change: fn())
                                        in_tipo.on('change', lambda _, fn=bind_change: fn())
                                        in_est.on('change', lambda _, fn=bind_change: fn())

                                        def eliminar_fila(idx_to_del=real_idx):
                                            processed.pop(idx_to_del)
                                            render_wizard()

                                        ui.button(icon='delete', on_click=lambda _, i=real_idx: eliminar_fila(i)).props('flat color=red round size=xs').classes('w-16').tooltip('Eliminar fila')

                    refrescar_grilla_preview()

                    # BARRA DE ACCIÓN PEGAJOSA FIJA EN PASO 3
                    def ejecutar_importacion_final():
                        if not processed:
                            ui.notify('No hay registros para importar.', type='warning')
                            return

                        k_cat_target = next((f['key'] for f in fields if 'cat' in f['label'].lower()), 'field_1')
                        todas_cats = [r.get(k_cat_target, '').strip() for r in processed if r.get(k_cat_target, '').strip() and r.get(k_cat_target) != 'N/A']
                        cats_agregadas = bulk_add_categories(todas_cats)

                        success, msg, count = bulk_add_custom_records(module_id, processed)

                        if success:
                            ui.notify(f"¡Éxito! Se importaron {count} registros y se crearon {cats_agregadas} categorías nuevas.", type='positive')
                            dlg.close()
                            if on_success_callback:
                                on_success_callback()
                        else:
                            ui.notify(msg, type='negative')

                    with ui.row().classes('w-full justify-between items-center mt-4 pt-3 border-t border-gray-300 bg-white p-4 rounded-xl shadow-lg sticky bottom-0 z-30'):
                        ui.button('Volver a Homologación', icon='arrow_back', on_click=lambda: [import_state.update({'step': 2}), render_wizard()]).props('flat text-gray-600 font-bold')
                        ui.button(
                            f"Confirmar e Importar ({len(processed)}) Registros",
                            icon='cloud_done',
                            on_click=ejecutar_importacion_final
                        ).classes('bg-green-600 hover:bg-green-700 text-white font-extrabold text-sm px-8 py-3 rounded-xl shadow-xl transform transition-transform hover:scale-105')

        render_wizard()

    dlg.open()
