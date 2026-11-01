from nicegui import ui
import io
import re
import csv
from datetime import datetime
import openpyxl
try:
    import xlrd
except ImportError:
    xlrd = None
from database import (
    bulk_add_events, get_template_by_area, get_all_staff, get_all_locations, get_all_inventory,
    events_match_cross_area, get_events_by_date
)
from components.template_builder import open_template_builder

def read_parrilla_file_rows(file_bytes: bytes, filename: str = '') -> list[tuple]:
    """
    Lee las filas de un archivo .xlsx, .xls o .csv retornando una lista de tuplas/listas con valores.
    Detecta tanto por extensión como por firmas de bytes (PK para xlsx, D0CF para xls).
    """
    if not file_bytes:
        return []

    filename_lower = (filename or '').lower()
    is_zip = file_bytes.startswith(b'PK\x03\x04')
    is_ole = file_bytes.startswith(b'\xd0\xcf\x11\xe0')

    # Caso 1: Archivos XLSX / ZIP
    if is_zip or filename_lower.endswith(('.xlsx', '.xlsm', '.xltx')):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet = wb.active
            return list(sheet.iter_rows(values_only=True))
        except Exception:
            if not is_ole and not filename_lower.endswith('.xls'):
                raise

    # Caso 2: Archivos XLS antiguos (BIFF8 / OLE2)
    if is_ole or filename_lower.endswith('.xls'):
        if xlrd is None:
            raise ImportError("Para leer archivos .xls antiguos es necesario instalar xlrd. Ejecute 'pip install xlrd' en su entorno virtual (venv).")
        try:
            book = xlrd.open_workbook(file_contents=file_bytes)
            sheet = book.sheet_by_index(0)
            rows = []
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
                    elif cell_type == xlrd.XL_CELL_NUMBER:
                        if isinstance(val, float) and val.is_integer():
                            val = int(val)
                    row_vals.append(val if val != '' else None)
                rows.append(tuple(row_vals))
            return rows
        except Exception:
            if not filename_lower.endswith('.csv'):
                raise

    # Caso 3: CSV o archivos delimitados por texto
    for enc in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            text = file_bytes.decode(enc)
            first_line = text.splitlines()[0] if text.splitlines() else ''
            delim = ';' if ';' in first_line and first_line.count(';') > first_line.count(',') else ','
            if '\t' in first_line and first_line.count('\t') > first_line.count(delim):
                delim = '\t'
            reader = csv.reader(io.StringIO(text), delimiter=delim)
            return [tuple(r) for r in reader]
        except Exception:
            continue

    raise ValueError("Formato de archivo no soportado. Cargue un archivo .xlsx, .xls o .csv válido.")

MESES_MAP = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

def parse_date_from_text(text: str) -> str:
    """Intenta extraer una fecha 'YYYY-MM-DD' desde texto como 'MARTES 8 DE SEPTIEMBRE DE 2026'."""
    if not text:
        return ""
    text_lower = text.lower()
    m = re.search(r'(\d{1,2})\s*(?:de)?\s*([a-záéíóúñ]+)\s*(?:de)?\s*(\d{4})', text_lower)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).replace('é', 'e').replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        año = int(m.group(3))
        mes = MESES_MAP.get(mes_str)
        if mes:
            return f"{año:04d}-{mes:02d}-{dia:02d}"
    m2 = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', text)
    if m2:
        return f"{int(m2.group(3)):04d}-{int(m2.group(2)):02d}-{int(m2.group(1)):02d}"
    return ""

def extract_time_range(cell_text: str) -> tuple[str, str] | None:
    """
    Extrae (hora_inicio, hora_fin) de forma tolerante a separadores, caracteres sueltos o puntos
    (ej: '7:30 . - 8:30', '9:00 - 10:00', '10:30-11:30', '7:00 - 1:00', '2:30 a 4:30', '14:00/15:00',
     '7:30 - 9', '7 - 8:30', '7 - 8', '7:00 AM - 1:00 PM', '07:00:00 - 08:30:00').
    Retorna estrictamente una tupla de dos cadenas no vacías (h1, h2) o None.
    """
    if not cell_text:
        return None
    s = str(cell_text).strip()
    # Normalizar puntos usados como separadores de hora (ej: 9.00 -> 9:00, 8.30 -> 8:30, 07.30 -> 07:30)
    s = re.sub(r'\b(\d{1,2})\.(\d{2})\b', r'\1:\2', s)
    
    # 1. Buscar dos horas con formato H:MM o HH:MM (o HH:MM:SS) con posibles sufijos AM/PM
    m_full = re.findall(r'\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.|m\.)?', s, re.IGNORECASE)
    if len(m_full) >= 2:
        h1 = int(m_full[0][0])
        m1 = int(m_full[0][1])
        ap1 = (m_full[0][2] or '').lower().replace('.', '')
        if ap1 == 'pm' and h1 < 12: h1 += 12
        elif ap1 == 'am' and h1 == 12: h1 = 0
        
        h2 = int(m_full[1][0])
        m2 = int(m_full[1][1])
        ap2 = (m_full[1][2] or '').lower().replace('.', '')
        if ap2 == 'pm' and h2 < 12: h2 += 12
        elif ap2 == 'am' and h2 == 12: h2 = 0
        
        return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"
        
    # 2. Tolerancia a separadores libres (-, a, hasta, /) con horas completas o sin minutos
    #    (ej: '7:30 - 9', '7:30 a 9', '2:00 - 5', '7 - 8:30', '7 - 8', '2 a 5')
    pattern_mixed = re.compile(
        r'\b(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.|m\.)?'
        r'[^\d\n\r]*?(?:[-–—/]|(?:\b(?:a|hasta)\b))[^\d\n\r]*?'
        r'(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.|m\.)?\b',
        re.IGNORECASE
    )
    m = pattern_mixed.search(s)
    if m:
        h1_raw, m1_raw, ap1_raw, h2_raw, m2_raw, ap2_raw = m.groups()
        h1 = int(h1_raw)
        m1 = int(m1_raw) if m1_raw is not None else 0
        ap1 = (ap1_raw or '').lower().replace('.', '')
        if ap1 == 'pm' and h1 < 12: h1 += 12
        elif ap1 == 'am' and h1 == 12: h1 = 0

        h2 = int(h2_raw)
        m2 = int(m2_raw) if m2_raw is not None else 0
        ap2 = (ap2_raw or '').lower().replace('.', '')
        if ap2 == 'pm' and h2 < 12: h2 += 12
        elif ap2 == 'am' and h2 == 12: h2 = 0

        return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"
        
    return None

def extract_single_time(cell_text: str) -> str | None:
    """
    Extrae una hora única de una celda cuando el cronograma solo especifica hora de inicio
    (ej: '06:00', '7:30 a.m.', '1:00 p.m.', '07:00:00', '7:00 AM', '14:30', '9.00').
    """
    if not cell_text:
        return None
    s = str(cell_text).strip()
    s = re.sub(r'\b(\d{1,2})\.(\d{2})\b', r'\1:\2', s)
    m = re.search(r'\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.|m\.)?', s, re.IGNORECASE)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2))
        ap = (m.group(3) or '').lower().replace('.', '')
        if ap == 'pm' and h < 12: h += 12
        elif ap == 'am' and h == 12: h = 0
        return f"{h:02d}:{mn:02d}"
    m2 = re.search(r'\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b', s, re.IGNORECASE)
    if m2:
        h = int(m2.group(1))
        ap = m2.group(2).lower().replace('.', '')
        if ap == 'pm' and h < 12: h += 12
        elif ap == 'am' and h == 12: h = 0
        return f"{h:02d}:00"
    return None

def normalize_str(s: str) -> str:
    if not s: return ''
    return ''.join(c for c in str(s).lower() if c.isalnum() or c == ' ').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')

def match_staff_name(raw_name: str, staff_list: list) -> str:
    """
    Empareja inteligentemente nombres informales o nombres de pila de Excel ('FREDY', 'ALFREDO', 'NESTOR')
    con el catálogo completo de personal de MediaHub ('Fredy Bohórquez', 'Alfredo Gutiérrez Manrique').
    """
    if not raw_name: return ''
    raw_s = str(raw_name).strip()
    raw_norm = normalize_str(raw_s)
    raw_words = raw_norm.split()
    if not raw_words: return raw_s
    
    # Manejo de casos compuestos tipo 'LAURA - ALFREDO' o 'EDGAR / FREDY'
    if '-' in raw_s or '/' in raw_s:
        parts = [p.strip() for p in re.split(r'[-/]', raw_s) if p.strip()]
        matched_parts = [match_staff_name(p, staff_list) for p in parts]
        return ' - '.join(matched_parts)

    # 1. Coincidencia por primer nombre exacto
    for p in staff_list:
        p_words = normalize_str(p.get('nombre', '')).split()
        if p_words and raw_words[0] == p_words[0]:
            return p.get('nombre', '')

    # 2. Tolerancias conocidas
    if raw_words[0] == 'william':
        for p in staff_list:
            if 'wiliam' in normalize_str(p.get('nombre', '')): return p.get('nombre', '')
    if raw_words[0] in ['josep', 'joseph']:
        for p in staff_list:
            p_norm = normalize_str(p.get('nombre', ''))
            if 'joseph' in p_norm or 'jose' in p_norm: return p.get('nombre', '')

    # 3. Coincidencia en cualquier parte del nombre
    for p in staff_list:
        p_words = normalize_str(p.get('nombre', '')).split()
        if any(rw in p_words for rw in raw_words):
            return p.get('nombre', '')
            
    return raw_s

def get_area_template_fields(tpl, area_usuario: str):
    """
    Extrae la lista de campos dinámicos definidos en la plantilla activa del área.
    Si no hay plantilla, genera los campos correspondientes al área.
    """
    fields = []
    if tpl and 'layout' in tpl:
        for cont in tpl['layout']:
            for campo in cont.get('campos', []):
                nid = campo.get('name_id')
                if nid and nid not in [f['name_id'] for f in fields]:
                    fields.append({
                        'name_id': nid,
                        'label': campo.get('label', nid),
                        'ui_component': campo.get('ui_component', 'text_input'),
                        'multiple': campo.get('multiple', False),
                        'contenedor': cont.get('titulo', 'General')
                    })
    if not fields:
        if area_usuario == 'programacion':
            fields = [
                {'name_id': 'time_range', 'label': 'Horario de Emisión', 'ui_component': 'time_range', 'contenedor': 'Emisión'},
                {'name_id': 'nombre_programa', 'label': 'Nombre del Programa', 'ui_component': 'text_input', 'contenedor': 'Emisión'},
                {'name_id': 'modalidad', 'label': 'Modalidad (V / P / R)', 'ui_component': 'select', 'contenedor': 'Emisión'},
                {'name_id': 'observaciones', 'label': 'Observaciones / Pautas', 'ui_component': 'textarea', 'contenedor': 'Emisión'}
            ]
        elif area_usuario == 'produccion':
            fields = [
                {'name_id': 'time_range', 'label': 'Horario de Grabación / Emisión', 'ui_component': 'time_range', 'contenedor': 'Producción'},
                {'name_id': 'nombre_programa', 'label': 'Nombre del Programa', 'ui_component': 'text_input', 'contenedor': 'Producción'},
                {'name_id': 'productor', 'label': 'Productor Encargado', 'ui_component': 'searchable_select', 'contenedor': 'Producción'},
                {'name_id': 'locacion', 'label': 'Estudio / Locación', 'ui_component': 'searchable_select', 'contenedor': 'Producción'},
                {'name_id': 'camaras', 'label': 'Camarógrafos', 'ui_component': 'searchable_select', 'multiple': True, 'contenedor': 'Producción'},
                {'name_id': 'switcher', 'label': 'Switcher / Máster', 'ui_component': 'searchable_select', 'contenedor': 'Producción'},
                {'name_id': 'sonido', 'label': 'Sonido / Audio', 'ui_component': 'searchable_select', 'contenedor': 'Producción'},
                {'name_id': 'equipos', 'label': 'Equipos Técnicos', 'ui_component': 'searchable_select', 'multiple': True, 'contenedor': 'Producción'}
            ]
        else:
            fields = [
                {'name_id': 'time_range', 'label': 'Horario', 'ui_component': 'time_range', 'contenedor': 'General'},
                {'name_id': 'nombre_programa', 'label': 'Nombre del Evento / Programa', 'ui_component': 'text_input', 'contenedor': 'General'},
                {'name_id': 'responsable', 'label': 'Responsable', 'ui_component': 'text_input', 'contenedor': 'General'},
                {'name_id': 'observaciones', 'label': 'Observaciones / Detalles', 'ui_component': 'textarea', 'contenedor': 'General'}
            ]
    return fields

def auto_detect_column_mapping(headers: list, field_id: str, field_label: str) -> int:
    """
    Determina de manera inteligente cuál columna del Excel corresponde a un campo de la plantilla.
    """
    lbl = field_label.lower()
    fid = field_id.lower()
    for idx, h in enumerate(headers):
        h_low = str(h).lower().strip()
        if not h_low:
            continue
        # 1. Horario / Tiempo
        if any(k in fid for k in ['hora', 'time', 'horario']) and any(k in h_low for k in ['hora', 'horario', 'time']):
            return idx
        # 2. Nombre del programa o actividad
        if any(k in fid for k in ['programa', 'titulo', 'título', 'nombre', 'actividad']) and any(k in h_low for k in ['programa', 'titulo', 'título', 'emision', 'emisión', 'nombre']):
            return idx
        # 3. Productor encargado
        if 'productor' in fid and any(k in h_low for k in ['productor', 'producc', 'producción']):
            return idx
        # 4. Locación / Estudio
        if any(k in fid for k in ['locacion', 'locación', 'estudio', 'lugar', 'sitio']) and any(k in h_low for k in ['locac', 'estudio', 'sitio', 'lugar']):
            return idx
        # 5. Cámaras
        if any(k in fid for k in ['camara', 'cámara']) and any(k in h_low for k in ['camara', 'cámara', 'cam']):
            return idx
        # 6. Sonido / Audio
        if any(k in fid for k in ['sonido', 'audio']) and any(k in h_low for k in ['sonido', 'audio']):
            return idx
        # 7. Equipos técnicos
        if any(k in fid for k in ['equipo', 'tecnico', 'técnico']) and any(k in h_low for k in ['equipo', 'tecnic', 'técnic']):
            return idx
        # 8. Switcher / Director
        if any(k in fid for k in ['switcher', 'master', 'máster']) and any(k in h_low for k in ['switcher', 'master', 'máster', 'director']):
            return idx
        # 9. Transporte
        if any(k in fid for k in ['transporte', 'vehiculo', 'carro']) and any(k in h_low for k in ['transporte', 'vehic', 'carro', 'movil', 'móvil']):
            return idx
        # 10. Observaciones / Notas / Pautas
        if any(k in fid for k in ['observ', 'pauta', 'nota', 'corte', 'detalle']) and any(k in h_low for k in ['observ', 'pauta', 'nota', 'corte', 'detalle']):
            return idx
        # Coincidencia directa por palabras del label
        palabras_lbl = [w for w in re.split(r'\W+', lbl) if len(w) >= 4]
        if any(w in h_low for w in palabras_lbl):
            return idx
    return -1

def open_parrilla_importer_dialog(user_info, on_success_callback=None, default_date=None):
    """
    Abre un modal interactivo multitenant de importación y homologación desde Excel/CSV,
    adaptado al área activa (Producción, Programación, Ingeniería, etc.).
    """
    area_usuario = user_info.get('area', 'programacion').lower() if user_info else 'programacion'
    
    # Nombres dinámicos multitenant según el área del usuario
    if area_usuario == 'produccion':
        area_nombre_tipo = 'Cronograma de Producción'
        area_subtitulo = 'Homologación inteligente con la Ficha Técnica de Producción'
        default_compartir_prod = False
        default_compartir_ing = False
    elif area_usuario == 'programacion':
        area_nombre_tipo = 'Parrilla de Emisión'
        area_subtitulo = 'Homologación de parrilla y enlace con Producción'
        default_compartir_prod = True
        default_compartir_ing = False
    else:
        area_nombre_tipo = f'Cronograma de {area_usuario.capitalize()}'
        area_subtitulo = f'Homologación de campos con la plantilla de {area_usuario.capitalize()}'
        default_compartir_prod = False
        default_compartir_ing = False
    
    import_state = {
        'step': 1,
        'filename': '',
        'file_bytes': None,
        'headers': [],
        'all_rows': [],
        'header_row_idx': 0,
        'fecha_emision': default_date or datetime.now().strftime('%Y-%m-%d'),
        'default_date_provided': default_date is not None,
        'field_mappings': {}, # {name_id: col_idx}
        'idx_horario': 0,
        'idx_programa': 1,
        'auto_detect_pm': True,
        'auto_parse_modalidad': (area_usuario == 'programacion'),
        'compartir_produccion': default_compartir_prod,
        'compartir_ingenieria': default_compartir_ing,
        'sobrescribir_existentes': True,
        'parsed_programas': []
    }

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-5xl max-h-[90vh] overflow-y-auto bg-white p-6 rounded-2xl shadow-2xl gap-4'):
        
        # Cabecera del Modal Dinámica
        with ui.row().classes('w-full justify-between items-center border-b pb-3 shrink-0'):
            with ui.row().classes('items-center gap-2'):
                with ui.element('div').classes('w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-md'):
                    ui.icon('table_view', size='sm')
                with ui.column().classes('gap-0'):
                    ui.label(f'Importador de {area_nombre_tipo} (Excel)').classes('text-lg font-bold text-gray-800 leading-tight')
                    ui.label(area_subtitulo).classes('text-xs text-gray-500')
            ui.button(icon='close', on_click=dialog.close).props('flat round color=grey')

        # Barra de progreso de pasos
        steps_header = ui.row().classes('w-full justify-around items-center border-b py-2 text-xs font-bold text-gray-500 shrink-0')

        # Contenedor central de los pasos
        steps_container = ui.column().classes('w-full gap-4')

        def render_steps_header():
            steps_header.clear()
            with steps_header:
                s = import_state['step']
                ui.label('1. Cargar Archivo').classes(f'{"text-indigo-600 font-extrabold" if s == 1 else "text-gray-400"}')
                ui.icon('chevron_right', size='xs').classes('text-gray-300')
                ui.label('2. Homologación de Campos').classes(f'{"text-indigo-600 font-extrabold" if s == 2 else "text-gray-400"}')
                ui.icon('chevron_right', size='xs').classes('text-gray-300')
                ui.label('3. Vista Previa y Confirmación').classes(f'{"text-indigo-600 font-extrabold" if s == 3 else "text-gray-400"}')

        # ==========================================
        # PASO 1: CARGA DE ARCHIVO
        # ==========================================
        def render_step_1():
            steps_container.clear()
            render_steps_header()
            with steps_container:
                with ui.column().classes('w-full items-center justify-center py-10 border-2 border-dashed border-indigo-200 rounded-2xl bg-indigo-50/40 gap-4 mt-4'):
                    with ui.element('div').classes('w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm'):
                        ui.icon('upload_file', size='lg')
                    
                    ui.label(f'Arrastra o selecciona el archivo Excel de {area_nombre_tipo}').classes('text-base font-bold text-gray-800')
                    ui.label('Soporta archivos .xlsx, .xls y .csv (Ej: PRODUCCION MARTES 15 DE SEPTIEMBRE DE 2026.xlsx)').classes('text-xs text-gray-500 text-center max-w-md')
                    
                    async def handle_upload(e):
                        import_state['filename'] = e.file.name
                        import_state['file_bytes'] = await e.file.read()
                        procesar_excel_cargado()

                    ui.upload(
                        label='Seleccionar Archivo Excel',
                        on_upload=handle_upload,
                        auto_upload=True
                    ).classes('w-72 mt-2').props('accept=".xlsx,.xls,.csv" outlined color=indigo')

        def procesar_excel_cargado():
            try:
                fname = import_state.get('filename', '')
                fbytes = import_state.get('file_bytes', b'')
                all_rows = read_parrilla_file_rows(fbytes, fname)
                
                if not all_rows:
                    ui.notify('El archivo no contiene filas o está vacío', type='warning')
                    return
                    
                import_state['all_rows'] = all_rows
                
                # 1. Buscar fecha en las primeras 15 filas
                fecha_detectada = ""
                for row in all_rows[:15]:
                    for cell in row:
                        if cell:
                            f = parse_date_from_text(str(cell))
                            if f:
                                fecha_detectada = f
                                break
                    if fecha_detectada:
                        break
                        
                if fecha_detectada:
                    # Si no vino de un día específico preseleccionado, adoptamos la fecha detectada
                    if not import_state.get('default_date_provided'):
                        import_state['fecha_emision'] = fecha_detectada
                    else:
                        # Si ya tenía día seleccionado, pero es diferente, adoptamos la del archivo para evitar inconsistencias
                        import_state['fecha_emision'] = fecha_detectada
                    
                # 2. Detectar encabezados de columna
                headers = []
                header_row_idx = 0
                
                # Buscamos fila con HORA o HORARIO
                for idx, row in enumerate(all_rows[:15]):
                    row_strs = [str(c).strip().upper() for c in row if c is not None and str(c).strip()]
                    if any('PARRILLA DIARIA' in s for s in row_strs) or any('CRONOGRAMA' in s and 'DE' in s for s in row_strs):
                        continue
                    if any('HORARIO' in s or 'HORA' in s for s in row_strs):
                        headers = [str(c).strip() if c is not None and str(c).strip() != '' else f"Columna {i+1}" for i, c in enumerate(row)]
                        header_row_idx = idx
                        break
                        
                if not headers:
                    for idx, row in enumerate(all_rows[:12]):
                        row_strs = [str(c).strip().upper() for c in row if c is not None and str(c).strip()]
                        if any('PROGRAMA' in s or 'OBSERVACION' in s or 'PRODUCCION' in s or 'LOCACION' in s for s in row_strs):
                            headers = [str(c).strip() if c is not None and str(c).strip() != '' else f"Columna {i+1}" for i, c in enumerate(row)]
                            header_row_idx = idx
                            break
                        
                if not headers:
                    for idx, row in enumerate(all_rows):
                        if any(c is not None and str(c).strip() != '' for c in row):
                            headers = [str(c).strip() if c is not None else f"Columna {i+1}" for i, c in enumerate(row)]
                            header_row_idx = idx
                            break
                            
                import_state['headers'] = headers
                import_state['header_row_idx'] = header_row_idx
                
                # Auto-detectar índices de mapeo contra la plantilla del área
                tpl = get_template_by_area(area_usuario)
                template_fields = get_area_template_fields(tpl, area_usuario)
                
                mappings = {}
                idx_h = -1
                idx_p = -1
                
                for f in template_fields:
                    fid = f['name_id']
                    flbl = f['label']
                    detected_col = auto_detect_column_mapping(headers, fid, flbl)
                    mappings[fid] = detected_col
                    
                    if any(k in fid for k in ['hora', 'time', 'horario']) and detected_col != -1 and idx_h == -1:
                        idx_h = detected_col
                    if any(k in fid for k in ['programa', 'titulo', 'nombre', 'actividad']) and detected_col != -1 and idx_p == -1:
                        idx_p = detected_col

                if idx_h == -1:
                    for i, h in enumerate(headers):
                        if any(k in str(h).lower() for k in ['hora', 'horario', 'time']):
                            idx_h = i
                            break
                    if idx_h == -1:
                        idx_h = 0
                        
                if idx_p == -1:
                    for i, h in enumerate(headers):
                        if any(k in str(h).lower() for k in ['programa', 'emision', 'titulo', 'nombre']):
                            idx_p = i
                            break
                    if idx_p == -1:
                        idx_p = 1 if len(headers) > 1 else 0

                import_state['idx_horario'] = idx_h
                import_state['idx_programa'] = idx_p
                import_state['field_mappings'] = mappings
                    
                import_state['step'] = 2
            except Exception as ex:
                ui.notify(f'Error al leer el archivo Excel: {str(ex)}', type='negative')
                return
                
            render_step_2()

        # ==========================================
        # PASO 2: HOMOLOGACIÓN Y MAPEO DE COLUMNAS
        # ==========================================
        def render_step_2():
            steps_container.clear()
            render_steps_header()
            
            tpl = get_template_by_area(area_usuario)
            template_fields = get_area_template_fields(tpl, area_usuario)
            col_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']
            hdrs = import_state['headers']
            
            # Crear mapa amigable: {índice: "Col X: Nombre"}
            opciones_cols = {}
            for i, h in enumerate(hdrs):
                letra = col_letters[i] if i < len(col_letters) else f"Col{i+1}"
                opciones_cols[i] = f"Col {letra}: {h}"

            opciones_con_ninguna = {-1: "(Ninguna / Omitir)", **opciones_cols}

            # Validar que los índices existan
            val_h = import_state.get('idx_horario', 0)
            if val_h not in opciones_cols:
                val_h = 0
            import_state['idx_horario'] = val_h

            val_p = import_state.get('idx_programa', 1 if len(hdrs) > 1 else 0)
            if val_p not in opciones_cols:
                val_p = 1 if len(hdrs) > 1 else 0
            import_state['idx_programa'] = val_p

            with steps_container:
                # Banner informativo de archivo y plantilla activa (Multitenant)
                with ui.row().classes('w-full justify-between items-center bg-indigo-50/70 p-3 rounded-xl border border-indigo-200'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('check_circle', size='sm').classes('text-indigo-600')
                        with ui.column().classes('gap-0'):
                            ui.label(f"Archivo: {import_state['filename']}").classes('text-xs font-bold text-indigo-950')
                            nombre_tpl = tpl.get('template_meta', {}).get('nombre', f'Ficha Técnica - {area_usuario.capitalize()}') if tpl else f'Plantilla Base ({area_usuario.capitalize()})'
                            ui.label(f"Plantilla Activa: {nombre_tpl} (Área: {area_usuario.upper()})").classes('text-[11px] text-indigo-700')
                    
                    with ui.row().classes('items-center gap-1'):
                        def on_tpl_edited():
                            render_step_2()
                        ui.button('Editar Plantilla', icon='tune', on_click=lambda: open_template_builder(user_info, on_tpl_edited)).props('flat dense size=sm color=indigo')
                        ui.button('Cambiar archivo', icon='refresh', on_click=render_step_1).props('flat dense size=sm color=grey')

                # Sección 1: Fecha y sobreescritura
                ui.label('1. Fecha del Cronograma y Configuración').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-2 border-b w-full pb-1')
                
                with ui.row().classes('w-full gap-6 items-center flex-wrap'):
                    ui.input('Fecha del Cronograma (YYYY-MM-DD)', value=import_state['fecha_emision']) \
                        .bind_value(import_state, 'fecha_emision') \
                        .props('type=date outlined dense') \
                        .classes('w-64 text-xs')
                                
                    ui.checkbox('Sobrescribir eventos existentes de esta fecha en el área') \
                        .bind_value(import_state, 'sobrescribir_existentes').classes('text-xs text-slate-700 font-semibold')

                # Sección 2: Columnas Principales del Evento (Horario y Título)
                ui.label('2. Columnas Principales (Horario y Programa / Actividad)').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-3 border-b w-full pb-1')
                
                with ui.grid(columns=2).classes('w-full gap-4'):
                    def set_col_h(e):
                        import_state['idx_horario'] = e.value
                        render_step_2()
                    ui.select(
                        options=opciones_cols,
                        value=val_h,
                        label='Columna de Horarios (Inicio - Fin)',
                        on_change=set_col_h
                    ).classes('w-full text-xs').props('outlined dense')

                    def set_col_p(e):
                        import_state['idx_programa'] = e.value
                        render_step_2()
                    ui.select(
                        options=opciones_cols,
                        value=val_p,
                        label='Columna de Nombre del Programa / Actividad',
                        on_change=set_col_p
                    ).classes('w-full text-xs').props('outlined dense')

                # Sección 3: Matriz Dinámica de Homologación de Campos con la Plantilla del Área
                ui.label(f'3. Homologación de Campos de la Ficha Técnica ({area_usuario.capitalize()})').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-3 border-b w-full pb-1')
                ui.label('Mapea las columnas del Excel con los campos que se guardarán en los detalles del evento:').classes('text-[11px] text-gray-500 -mt-2')

                # Filtrar campos que no sean estrictamente el nombre y el time_range porque ya se seleccionaron arriba
                campos_a_mapear = [f for f in template_fields if f['name_id'] not in ['time_range', 'nombre_programa']]

                with ui.element('div').classes('w-full border border-gray-200 rounded-xl p-3 bg-gray-50/50 shadow-sm'):
                    with ui.grid().classes('grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 w-full'):
                        for f in campos_a_mapear:
                            fid = f['name_id']
                            flbl = f['label']
                            val_campo = import_state['field_mappings'].get(fid, -1)
                            if val_campo not in opciones_con_ninguna:
                                val_campo = -1
                                
                            with ui.column().classes('bg-white p-2.5 rounded-lg border border-gray-200 shadow-xs gap-1'):
                                with ui.row().classes('w-full justify-between items-center'):
                                    ui.label(flbl).classes('text-xs font-bold text-gray-800 truncate')
                                    ui.label(f['contenedor']).classes('text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded')
                                
                                def make_on_change(field_key):
                                    return lambda e: import_state['field_mappings'].update({field_key: e.value})

                                ui.select(
                                    options=opciones_con_ninguna,
                                    value=val_campo,
                                    on_change=make_on_change(fid)
                                ).classes('w-full text-xs').props('outlined dense')

                # Sección 4: Opciones Inteligentes de Conversión y Enlace
                ui.label('4. Reglas de Tratamiento Inteligente').classes('text-xs font-bold text-gray-500 uppercase tracking-wider mt-3 border-b w-full pb-1')
                
                with ui.column().classes('w-full bg-indigo-50/50 p-3 rounded-xl border border-indigo-200 gap-2'):
                    ui.checkbox(
                        'Detección inteligente de horarios de la tarde (conversión automática 12h a 24h / PM)', 
                        value=import_state['auto_detect_pm']
                    ).bind_value(import_state, 'auto_detect_pm').classes('text-xs text-indigo-950 font-bold')
                    ui.label('Si los horarios del cronograma vienen como 2:00, 3:30, 4:30 o cruzan el mediodía (ej: 7:00 a 1:00), se ajustarán automáticamente a formato 24 horas para ubicarse correctamente en la tarde.').classes('text-[11px] text-indigo-800 pl-7 leading-tight')

                    if area_usuario == 'programacion':
                        ui.checkbox(
                            'Auto-detectar modalidad TV: (V) En Vivo, (P) Pregrabado, (R) Repetición', 
                            value=import_state['auto_parse_modalidad']
                        ).bind_value(import_state, 'auto_parse_modalidad').classes('text-xs text-indigo-950 font-bold mt-1')
                        
                        ui.checkbox(
                            'Compartir automáticamente emisiones EN VIVO (V) con el área de Producción', 
                            value=import_state['compartir_produccion']
                        ).bind_value(import_state, 'compartir_produccion').classes('text-xs text-red-950 font-bold mt-1')

                    if area_usuario == 'produccion':
                        ui.checkbox(
                            'Solicitar soporte técnico al área de Ingeniería por defecto', 
                            value=import_state['compartir_ingenieria']
                        ).bind_value(import_state, 'compartir_ingenieria').classes('text-xs text-purple-950 font-bold mt-1')

                # Botones de navegación
                with ui.row().classes('w-full justify-between items-center mt-4 border-t pt-4 shrink-0'):
                    ui.button('Atrás', icon='arrow_back', on_click=render_step_1).props('flat text-color=grey')
                    ui.button('Continuar a Vista Previa', icon='arrow_forward', on_click=ejecutar_analisis_parrilla).classes('bg-indigo-600 text-white font-bold px-6 shadow-md')

        def ejecutar_analisis_parrilla():
            all_rows = import_state['all_rows']
            hdr_idx = import_state.get('header_row_idx', 0)
            hdrs = import_state['headers']
            
            idx_horario = import_state.get('idx_horario', 0)
            idx_programa = import_state.get('idx_programa', 1)
            mappings = import_state.get('field_mappings', {})
            
            tpl = get_template_by_area(area_usuario)
            template_fields = get_area_template_fields(tpl, area_usuario)
            staff_list = get_all_staff()
            
            # Detectar todas las columnas que contengan "camara" o "cámara" para consolidar cámaras múltiples
            cam_col_indices = [i for i, h in enumerate(hdrs) if 'camara' in str(h).lower() or 'cámara' in str(h).lower()]
            
            programas = []
            is_pm_mode = False
            last_h1 = 0
            
            for r_idx, row in enumerate(all_rows[hdr_idx + 1:]):
                if not any(row):
                    continue
                row_strs = [str(c).strip() if c is not None else "" for c in row]
                
                # 1. Extraer celda de horario con extractor tolerante
                celda_hora = row_strs[idx_horario] if idx_horario < len(row_strs) else ""
                rango_hora = extract_time_range(celda_hora)
                hora_fin_auto = False
                
                if not rango_hora:
                    # Búsqueda de respaldo en otras celdas de la fila
                    for c_str in row_strs:
                        rango_sub = extract_time_range(c_str)
                        if rango_sub:
                            rango_hora = rango_sub
                            break
                            
                if not rango_hora:
                    # Si no hay rango de dos horas, verificar si la celda de horario tiene una hora única de inicio
                    hora_sola = extract_single_time(celda_hora)
                    if hora_sola:
                        h_s, m_s = map(int, hora_sola.split(':'))
                        rango_hora = (hora_sola, f"{(h_s + 1) % 24:02d}:{m_s:02d}")
                        hora_fin_auto = True

                if not rango_hora:
                    continue
                    
                h1_raw, h2_raw = rango_hora
                if not h1_raw:
                    continue
                if not h2_raw:
                    try:
                        h1_tmp, m1_tmp = map(int, str(h1_raw).split(':'))
                        h2_raw = f"{(h1_tmp + 1) % 24:02d}:{m1_tmp:02d}"
                    except Exception:
                        h2_raw = "01:00"

                try:
                    h1, m1 = map(int, str(h1_raw).split(':'))
                    h2, m2 = map(int, str(h2_raw).split(':'))
                except Exception:
                    continue
                
                # 2. Tratamiento Inteligente de Horarios PM y cruces de mediodía (ej: 7:00 a 1:00)
                if import_state.get('auto_detect_pm', True):
                    # Si la hora de inicio retrocede a la tarde (ej: 10:30 -> 1:00, 2:30) y veníamos de la mañana, pasamos a PM
                    if not is_pm_mode and last_h1 >= 8 and h1 < last_h1 and 1 <= h1 <= 6:
                        is_pm_mode = True
                        
                    if is_pm_mode:
                        if h1 < 12: h1 += 12
                        if h2 < 12: h2 += 12
                    else:
                        # Si estamos en la mañana pero la hora fin es menor que la de inicio (ej: 7:00 - 1:00 o 8:00 - 1:00)
                        # significa que termina en la tarde (1:00 PM = 13:00)
                        if h2 < h1 and h2 < 12 and h1 >= 6:
                            h2 += 12
                            
                last_h1 = h1
                h_ini_fmt = f"{h1:02d}:{m1:02d}"
                h_fin_fmt = f"{h2:02d}:{m2:02d}"

                # Si el evento anterior tenía fin auto-calculado, enlazar con el inicio de este evento
                if programas and programas[-1].get('_hora_fin_auto'):
                    programas[-1]['hora_fin'] = h_ini_fmt
                
                # 3. Extraer nombre del programa
                prog_raw = row_strs[idx_programa] if idx_programa < len(row_strs) else ""
                if not prog_raw or extract_time_range(prog_raw):
                    for c_str in row_strs:
                        if c_str and not extract_time_range(c_str):
                            prog_raw = c_str
                            break
                            
                if not prog_raw:
                    continue
                    
                # 4. Detectar modalidad (si aplica a programación o etiquetas V/P/R)
                modalidad = "Pregrabado"
                if import_state['auto_parse_modalidad']:
                    if re.search(r'\(\s*[vV]\s*\)', prog_raw):
                        modalidad = "En Vivo"
                    elif re.search(r'\(\s*[rR]\s*\)', prog_raw):
                        modalidad = "Repetición"
                    elif re.search(r'\(\s*[pP]\s*\)', prog_raw):
                        modalidad = "Pregrabado"
                    elif re.search(r'\(\s*[cC]\s*\)|\(\s*[eE]\s*\)', prog_raw):
                        modalidad = "Comercial / Especial"
                        
                nombre_limpio = prog_raw
                detalle_tema = ""
                partes_guion = re.split(r'[-–—]', prog_raw, maxsplit=1)
                if len(partes_guion) > 1:
                    nombre_limpio = partes_guion[0].strip()
                    detalle_tema = partes_guion[1].strip()
                else:
                    nombre_limpio = re.sub(r'\(\s*[vVpPrRcCeE]\s*\)', '', prog_raw).strip()
                    
                if detalle_tema:
                    detalle_tema = re.sub(r'^\s*\(\s*[vVpPrRcCeE]\s*\)\s*', '', detalle_tema).strip()

                # 5. Extraer y homologar todos los campos de la fila según el mapeo y catálogo
                campos_homologados = {}
                for f in template_fields:
                    fid = f['name_id']
                    c_idx = mappings.get(fid, -1)
                    val = row_strs[c_idx] if c_idx >= 0 and c_idx < len(row_strs) else ''
                    
                    if fid in ['productor', 'switcher', 'sonido']:
                        # Emparejar con staff oficial
                        campos_homologados[fid] = match_staff_name(val, staff_list) if val else ''
                    elif fid == 'locacion':
                        # Limpiar saltos de línea de celdas compuestas
                        campos_homologados[fid] = val.replace('\r', '').replace('\n', ' - ') if val else ''
                    elif fid == 'camaras':
                        # Si hay múltiples columnas de cámara (Cámara 1, Cámara 2), consolidar en lista
                        cams = []
                        if cam_col_indices:
                            for ci in cam_col_indices:
                                if ci < len(row_strs) and row_strs[ci]:
                                    matched_cam = match_staff_name(row_strs[ci], staff_list)
                                    if matched_cam and matched_cam not in cams:
                                        cams.append(matched_cam)
                        elif val:
                            matched_cam = match_staff_name(val, staff_list)
                            if matched_cam:
                                cams.append(matched_cam)
                        campos_homologados[fid] = cams
                    elif fid == 'equipos':
                        cleaned_eq = val.replace('\r', '').replace('\n', ' ') if val else ''
                        campos_homologados[fid] = [cleaned_eq] if cleaned_eq else []
                    else:
                        campos_homologados[fid] = val

                programas.append({
                    'id_temp': len(programas) + 1,
                    'fecha': import_state['fecha_emision'],
                    'hora_inicio': h_ini_fmt,
                    'hora_fin': h_fin_fmt,
                    'nombre_programa': nombre_limpio,
                    'tipo': area_usuario,
                    'modalidad': modalidad,
                    'detalle_tema': detalle_tema,
                    'campos_homologados': campos_homologados,
                    'compartir_produccion': (modalidad == 'En Vivo' and import_state.get('compartir_produccion', False)),
                    'compartir_ingenieria': import_state.get('compartir_ingenieria', False),
                    '_hora_fin_auto': hora_fin_auto
                })
                
            if not programas:
                ui.notify('No se pudieron detectar bloques de emisión u horarios válidos en el archivo', type='warning')
                return

            for p in programas:
                p.pop('_hora_fin_auto', None)

            import_state['parsed_programas'] = programas
            import_state['step'] = 3
            render_step_3()

        # ==========================================
        # PASO 3: VISTA PREVIA Y CONFIRMACIÓN
        # ==========================================
        def render_step_3():
            steps_container.clear()
            render_steps_header()
            programas = import_state['parsed_programas']
            total_progs = len(programas)
            
            with steps_container:
                # Banner de Resumen
                with ui.row().classes('w-full justify-between items-center p-3 bg-slate-900 text-white rounded-xl shadow-md flex-wrap gap-2'):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('calendar_month', size='md').classes('text-indigo-400')
                        with ui.column().classes('gap-0'):
                            ui.label(f"{area_nombre_tipo} - {import_state['fecha_emision']}").classes('text-sm font-bold leading-tight')
                            ui.label(f"Total: {total_progs} Eventos listos para importar").classes('text-xs text-gray-300')
                            
                    with ui.row().classes('items-center gap-2 text-xs flex-wrap'):
                        ui.label(f"📅 {total_progs} Programados").classes('bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 px-2 py-0.5 rounded font-bold')
                        if area_usuario == 'programacion':
                            total_vivos = sum(1 for p in programas if p['modalidad'] == 'En Vivo')
                            if total_vivos > 0:
                                ui.label(f"🔴 {total_vivos} En Vivo").classes('bg-red-500/20 text-red-300 border border-red-500/40 px-2 py-0.5 rounded font-bold')
                        if import_state.get('compartir_ingenieria'):
                            ui.label('⚡ Enlace a Ingeniería').classes('bg-purple-500/20 text-purple-300 border border-purple-500/40 px-2 py-0.5 rounded font-bold')

                # Tabla interactiva de vista previa
                with ui.column().classes('w-full flex-grow overflow-y-auto border border-gray-200 rounded-xl max-h-[50vh] gap-0 bg-white shadow-xs'):
                    # Encabezados de tabla
                    with ui.grid(columns=12).classes('w-full bg-gray-100 text-gray-700 p-2 text-xs font-bold border-b gap-2 items-center'):
                        ui.label('HORARIO (24H)').classes('col-span-2')
                        ui.label('PROGRAMA / ACTIVIDAD').classes('col-span-4')
                        ui.label('CAMPOS HOMOLOGADOS DETECTADOS').classes('col-span-6')

                    # Buscar eventos existentes de la otra área para identificar interconexiones
                    otra_area = 'programacion' if area_usuario == 'produccion' else ('produccion' if area_usuario == 'programacion' else None)
                    eventos_otra_area = get_events_by_date(import_state['fecha_emision'], otra_area) if otra_area else []

                    for p in programas:
                        coincide_cruzado = False
                        if otra_area:
                            for ex in eventos_otra_area:
                                if events_match_cross_area(p['nombre_programa'], p['hora_inicio'], p['hora_fin'], ex['nombre_programa'], ex['hora_inicio'], ex['hora_fin']):
                                    coincide_cruzado = True
                                    break

                        with ui.grid(columns=12).classes('w-full p-2.5 text-xs border-b hover:bg-gray-50 items-center gap-2'):
                            ui.label(f"{p['hora_inicio']} - {p['hora_fin']}").classes('col-span-2 font-mono font-bold text-indigo-900 bg-indigo-50 px-2 py-1 rounded text-center')
                            
                            with ui.column().classes('col-span-4 gap-0'):
                                ui.label(p['nombre_programa']).classes('font-bold text-slate-900 text-xs')
                                if p.get('detalle_tema'):
                                    ui.label(p['detalle_tema']).classes('text-[10px] text-gray-500 truncate')
                                if coincide_cruzado:
                                    ui.label(f'🔗 Se interconectará con {otra_area.capitalize()}').classes('bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-1.5 py-0.5 rounded w-fit mt-0.5')
                                    
                            # Mostrar resumen de los campos homologados
                            with ui.row().classes('col-span-6 items-center gap-1 flex-wrap'):
                                ch = p.get('campos_homologados', {})
                                if not ch:
                                    ui.label('(Sin campos adicionales)').classes('text-gray-400 italic text-[11px]')
                                else:
                                    for k_id, k_val in ch.items():
                                        if k_val:
                                            val_display = ", ".join(k_val) if isinstance(k_val, list) else str(k_val)
                                            if val_display:
                                                ui.label(f"{k_id.capitalize()}: {val_display}").classes('bg-slate-100 text-slate-700 border border-slate-200 px-1.5 py-0.5 rounded text-[10px] truncate max-w-[200px]')

                # Botones finales
                with ui.row().classes('w-full justify-between items-center mt-4 border-t pt-3 shrink-0'):
                    ui.button('Atrás (Reajustar Mapeo)', icon='arrow_back', on_click=render_step_2).props('flat text-color=grey')
                    
                    async def guardar_parrilla():
                        events_to_save = []
                        for p in programas:
                            es_vivo = p.get('modalidad') == 'En Vivo'
                            compartir_prod = p.get('compartir_produccion', False)
                            compartir_ing = p.get('compartir_ingenieria', False)
                            
                            detalles_ev = {
                                'nombre_programa': p['nombre_programa'],
                                'modalidad': p.get('modalidad', 'Pregrabado'),
                                'capitulo_tema': p.get('detalle_tema', ''),
                                'es_parrilla_tv': (area_usuario == 'programacion')
                            }
                            
                            # Guardar todos los campos homologados en el diccionario de detalles
                            for k_field, v_val in p.get('campos_homologados', {}).items():
                                detalles_ev[k_field] = v_val

                            # Sincronizar observaciones y pautas si existen
                            if 'observaciones' in detalles_ev and detalles_ev['observaciones']:
                                detalles_ev['pautas_cortes'] = detalles_ev['observaciones']
                                
                            if compartir_prod:
                                detalles_ev['compartir_produccion'] = True
                                detalles_ev['estado_compartido'] = 'pendiente'
                                detalles_ev['requiere_produccion'] = True
                                detalles_ev['requiere_tecnica'] = True

                            if compartir_ing:
                                detalles_ev['compartir_ingenieria'] = True
                                detalles_ev['estado_compartido'] = 'pendiente'

                            events_to_save.append({
                                'fecha': p['fecha'],
                                'hora_inicio': p['hora_inicio'],
                                'hora_fin': p['hora_fin'],
                                'tipo': area_usuario,
                                'nombre_programa': p['nombre_programa'],
                                'detalles': detalles_ev
                            })
                            
                        success, msg, count = bulk_add_events(events_to_save, overwrite_date_and_area=import_state['sobrescribir_existentes'])
                        if success:
                            ui.notify(f'¡Éxito! {msg}', type='positive', icon='done_all')
                            dialog.close()
                            if on_success_callback:
                                try:
                                    on_success_callback(import_state["fecha_emision"])
                                except TypeError:
                                    on_success_callback()
                        else:
                            ui.notify(f'Error al guardar: {msg}', type='negative')


                    ui.button(f'Confirmar e Importar {total_progs} Eventos al Calendario', icon='cloud_upload', on_click=guardar_parrilla).classes('bg-emerald-600 text-white font-bold px-6 shadow-md')

        render_step_1()

    dialog.open()
