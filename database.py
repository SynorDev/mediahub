import sqlite3
import hashlib
import os
import json
import unicodedata
import re
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, 'mediahub.db')

def get_db_connection(timeout: float = 30.0) -> sqlite3.Connection:
    """Retorna una conexión a SQLite optimizada para alta concurrencia y tolerancia a latencia (Modo WAL)."""
    conn = sqlite3.connect(DB_NAME, timeout=timeout)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -32000;")  # 32MB cache
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombres TEXT NOT NULL,
            apellidos TEXT NOT NULL,
            cargo TEXT NOT NULL,
            area_encargada TEXT NOT NULL,
            celular TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT DEFAULT 'Colaborador'
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN rol TEXT DEFAULT 'Colaborador'")
    except Exception:
        pass
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin TEXT NOT NULL,
            tipo TEXT NOT NULL,
            nombre_programa TEXT NOT NULL,
            detalles TEXT NOT NULL
        )
    ''')
    # TABLA STAFF ACTUALIZADA (Teléfono y Correo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL,
            telefono TEXT,
            correo TEXT
        )
    ''')
    # NUEVA TABLA DE CATEGORÍAS DE INVENTARIO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_categoria TEXT UNIQUE NOT NULL
        )
    ''')
    # NUEVA TABLA DE INVENTARIO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            serial TEXT,
            foto TEXT,
            complemento TEXT,
            cantidad INTEGER DEFAULT 1
        )
    ''')
    
    # Garantizar que las nuevas columnas existan en bases de datos ya creadas
    cursor.execute("PRAGMA table_info(inventory)")
    columnas_actuales = [row[1] for row in cursor.fetchall()]
    if columnas_actuales:
        if 'serial' not in columnas_actuales:
            cursor.execute("ALTER TABLE inventory ADD COLUMN serial TEXT")
        if 'foto' not in columnas_actuales:
            cursor.execute("ALTER TABLE inventory ADD COLUMN foto TEXT")
        if 'complemento' not in columnas_actuales:
            cursor.execute("ALTER TABLE inventory ADD COLUMN complemento TEXT")
        if 'cantidad' not in columnas_actuales:
            cursor.execute("ALTER TABLE inventory ADD COLUMN cantidad INTEGER DEFAULT 1")
    # NUEVA TABLA DE LOCACIONES (Separada del inventario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')
    # NUEVA TABLA DE ROLES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_rol TEXT UNIQUE NOT NULL
        )
    ''')
    # NUEVA TABLA PARA LAS PLANTILLAS DINÁMICAS (JSON)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id TEXT UNIQUE NOT NULL,
            tenant_id TEXT NOT NULL,
            config_json TEXT NOT NULL
        )
    ''')
    # NUEVA TABLA DE GESTIONES PERSONALIZADAS (MÓDULOS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_modules (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            icono TEXT NOT NULL,
            config_json TEXT NOT NULL
        )
    ''')
    # NUEVA TABLA DE REGISTROS DE GESTIONES PERSONALIZADAS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_module_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            data_json TEXT NOT NULL,
            FOREIGN KEY (module_id) REFERENCES custom_modules (id) ON DELETE CASCADE
        )
    ''')
    # NUEVA TABLA DE AUTORIZACIONES DE RETRANSMISIÓN (MINTIC / RTI / ACTAS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS retransmission_authorizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            operator_name TEXT NOT NULL,
            nit TEXT,
            rti_number TEXT,
            rep_name TEXT,
            rep_doc TEXT,
            channel_target TEXT DEFAULT 'Canal Teleamiga',
            municipality TEXT,
            department TEXT,
            address TEXT,
            notification_email TEXT,
            status TEXT DEFAULT 'pendiente_revision',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            file_rti_path TEXT,
            file_camara_path TEXT,
            file_cedula_path TEXT,
            ocr_data_json TEXT,
            match_results_json TEXT,
            approved_by TEXT,
            approved_at TEXT,
            signature_img_b64 TEXT,
            notes TEXT
        )
    ''')
    # Migraciones defensivas de columnas opcionales
    try:
        cursor.execute("ALTER TABLE retransmission_authorizations ADD COLUMN address TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE retransmission_authorizations ADD COLUMN notification_email TEXT")
    except Exception:
        pass
    # NUEVAS TABLAS DE ENCUESTAS INTERNAS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_cargo TEXT,
            user_area TEXT,
            responses_json TEXT NOT NULL,
            is_draft INTEGER DEFAULT 0,
            submitted_at TEXT NOT NULL,
            UNIQUE(survey_id, user_id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    # NUEVA TABLA DE ACTAS DE ENTREGA DE EQUIPOS Y FIRMAS VIRTUALES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment_delivery_acts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            record_id INTEGER NOT NULL,
            module_id TEXT DEFAULT 'system_inventory',
            equipo_nombre TEXT NOT NULL,
            serial TEXT,
            receptor_id TEXT,
            receptor_nombre TEXT NOT NULL,
            receptor_correo TEXT,
            receptor_cargo TEXT,
            emisor_usuario TEXT,
            emisor_nombre TEXT,
            emisor_cargo TEXT,
            estado TEXT DEFAULT 'pendiente_firma',
            firma_receptor_b64 TEXT,
            firma_receptor_fecha TEXT,
            firma_emisor_b64 TEXT,
            firma_emisor_fecha TEXT,
            layout_config TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acts_code ON equipment_delivery_acts(code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acts_record ON equipment_delivery_acts(record_id, module_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acts_receptor ON equipment_delivery_acts(receptor_correo, estado);")

    # Seed system custom modules if they do not exist
    seed_system_modules(cursor)
    # Seed default event templates for programacion and produccion
    seed_default_event_templates(cursor)
    # Seed encuesta interna Teleamiga
    seed_teleamiga_survey(cursor)
    
    # --- ÍNDICES ESTRATÉGICOS PARA MÁXIMA VELOCIDAD Y CONCURRENCIA ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_fecha ON events(fecha);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom_records_module ON custom_module_records(module_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retrans_status ON retransmission_authorizations(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retrans_code ON retransmission_authorizations(code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retrans_rti ON retransmission_authorizations(rti_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_survey_responses_draft ON survey_responses(is_draft);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_survey_responses_survey_user ON survey_responses(survey_id, user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_usuario ON users(usuario);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_correo ON users(correo);")

    conn.commit()
    conn.close()


def seed_system_modules(cursor):
    # Seed system_staff
    cursor.execute("SELECT id FROM custom_modules WHERE id = 'system_staff'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO custom_modules (id, nombre, icono, config_json) VALUES (?, ?, ?, ?)",
                       ('system_staff', 'Gestión de Personal', 'person', json.dumps([
                           {"label": "Nombre completo", "type": "text"},
                           {"label": "Teléfono", "type": "text"},
                           {"label": "Correo", "type": "text"},
                           {"label": "Rol asignado", "type": "text"}
                       ])))
        # Migrate existing staff data
        cursor.execute("SELECT nombre, rol, telefono, correo FROM staff")
        for r in cursor.fetchall():
            cursor.execute("INSERT INTO custom_module_records (module_id, data_json) VALUES ('system_staff', ?)",
                           (json.dumps({"field_0": r[0], "field_1": r[2], "field_2": r[3], "field_3": r[1]}),))
            
    # Seed system_inventory
    cursor.execute("SELECT id, config_json FROM custom_modules WHERE id = 'system_inventory'")
    row = cursor.fetchone()
    
    inventory_fields = [
        {"label": "Nombre / Modelo", "type": "text"},
        {"label": "Categoría", "type": "text"},
        {"label": "Número de Serie (Serial)", "type": "text"},
        {"label": "Cantidad", "type": "number"},
        {"label": "Fotos", "type": "images"},
        {"label": "Accesorios / Complementos", "type": "accessories"},
        {"label": "Tipo de Asignación", "type": "select", "options": ["Inventario Fijo", "Préstamo", "Alquiler"]},
        {"label": "Contenedor / Grupo", "type": "select", "options": ["Ninguno", "Contenedor Principal"]},
        {"label": "Estado del Artículo", "type": "select", "options": ["En uso", "En desuso", "En bodega", "De baja"]},
        {"label": "Responsable / Asignado a", "type": "linked_data", "linked_module_id": "system_staff", "linked_multiple": False}
    ]
    
    if not row:
        cursor.execute("INSERT INTO custom_modules (id, nombre, icono, config_json) VALUES (?, ?, ?, ?)",
                       ('system_inventory', 'Gestión de Inventario', 'inventory', json.dumps(inventory_fields)))
        # Migrate existing inventory data
        cursor.execute("SELECT nombre, categoria, serial, foto, complemento, cantidad FROM inventory")
        for r in cursor.fetchall():
            fotos_list = []
            if r[3]:
                try:
                    fotos_list = json.loads(r[3])
                except Exception:
                    fotos_list = [r[3]]
            accs_list = []
            if r[4]:
                try:
                    accs_list = json.loads(r[4])
                except Exception:
                    accs_list = [{"nombre": r[4], "serial": ""}]
            cursor.execute("INSERT INTO custom_module_records (module_id, data_json) VALUES ('system_inventory', ?)",
                           (json.dumps({
                               "field_0": r[0],
                               "field_1": r[1],
                               "field_2": r[2],
                               "field_3": r[5],
                               "field_4": fotos_list,
                               "field_5": accs_list
                           }),))
    else:
        # Migration: Ensure existing system_inventory has the new fields
        current_config = json.loads(row[1])
        labels_present = [f.get('label') for f in current_config]
        updated = False
        for new_f in inventory_fields[6:]:
            if new_f['label'] not in labels_present:
                new_f_copy = dict(new_f)
                if 'key' not in new_f_copy:
                    if new_f_copy['type'] == 'linked_data':
                        new_f_copy['key'] = 'field_responsable'
                    else:
                        new_f_copy['key'] = f"field_{len(current_config)}"
                current_config.append(new_f_copy)
                updated = True
        
        if updated:
            cursor.execute("UPDATE custom_modules SET config_json = ? WHERE id = 'system_inventory'", (json.dumps(current_config),))

    # Seed system_roles
    cursor.execute("SELECT id FROM custom_modules WHERE id = 'system_roles'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO custom_modules (id, nombre, icono, config_json) VALUES (?, ?, ?, ?)",
                       ('system_roles', 'Gestión de Roles', 'assignment', json.dumps([
                           {"label": "Nombre del Rol", "type": "text"}
                       ])))
        # Migrate existing roles
        cursor.execute("SELECT nombre_rol FROM roles")
        for r in cursor.fetchall():
            cursor.execute("INSERT INTO custom_module_records (module_id, data_json) VALUES ('system_roles', ?)",
                           (json.dumps({"field_0": r[0]}),))

def seed_default_event_templates(cursor):
    """Inicializa plantillas dinámicas por defecto para áreas clave como Programación y Producción"""
    # 1. Template para Programación
    cursor.execute("SELECT id FROM event_templates WHERE tenant_id = 'programacion' AND template_id NOT LIKE 'report_%'")
    if not cursor.fetchone():
        tpl_prog = {
            "template_meta": {
                "tenant_id": "programacion",
                "template_id": "tpl_programacion_v1",
                "nombre": "Ficha Técnica - Programación",
                "estado": "activo"
            },
            "layout": [
                {
                    "tipo_contenedor": "grid",
                    "titulo": "Datos de la Emisión (Parrilla TV)",
                    "columnas": 2,
                    "campos": [
                        {
                            "name_id": "nombre_programa",
                            "label": "Nombre del Programa",
                            "ui_component": "text_input"
                        },
                        {
                            "name_id": "time_range",
                            "label": "Horario de Emisión",
                            "ui_component": "time_range"
                        },
                        {
                            "name_id": "modalidad",
                            "label": "Modalidad de Emisión",
                            "ui_component": "select",
                            "data_source": {
                                "tipo": "estatico",
                                "opciones": ["En Vivo", "Pregrabado", "Repetición", "Especial"]
                            }
                        },
                        {
                            "name_id": "capitulo_tema",
                            "label": "Capítulo / Subtítulo / Tema",
                            "ui_component": "text_input"
                        },
                        {
                            "name_id": "observaciones",
                            "label": "Observaciones / Pauta Comercial",
                            "ui_component": "text_input"
                        },
                        {
                            "name_id": "locacion",
                            "label": "Estudio / Locación / Master",
                            "ui_component": "searchable_select",
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "locations",
                                "filtros": {}
                            }
                        },
                        {
                            "name_id": "compartir_produccion",
                            "label": "Compartir con Producción (En Vivo)",
                            "ui_component": "switch",
                            "target_area": "produccion"
                        },
                        {
                            "name_id": "compartir_ingenieria",
                            "label": "Compartir con Ingeniería / Técnica",
                            "ui_component": "switch",
                            "target_area": "ingenieria"
                        }
                    ]
                }
            ]
        }
        cursor.execute("INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)",
                       ('tpl_programacion_v1', 'programacion', json.dumps(tpl_prog)))

    # 2. Template para Producción
    cursor.execute("SELECT id FROM event_templates WHERE tenant_id = 'produccion' AND template_id NOT LIKE 'report_%'")
    if not cursor.fetchone():
        tpl_prod = {
            "template_meta": {
                "tenant_id": "produccion",
                "template_id": "tpl_produccion_v1",
                "nombre": "Ficha Técnica - Producción",
                "estado": "activo"
            },
            "layout": [
                {
                    "tipo_contenedor": "grid",
                    "titulo": "Asignaciones de Producción",
                    "columnas": 2,
                    "campos": [
                        {
                            "name_id": "nombre_programa",
                            "label": "Nombre del Programa",
                            "ui_component": "text_input"
                        },
                        {
                            "name_id": "time_range",
                            "label": "Horario de Grabación / Emisión",
                            "ui_component": "time_range"
                        },
                        {
                            "name_id": "productor",
                            "label": "Productor Encargado",
                            "ui_component": "searchable_select",
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "staff",
                                "filtros": {"rol_tags": ["productor", "produccion", "coordinador"]}
                            }
                        },
                        {
                            "name_id": "locacion",
                            "label": "Estudio / Locación",
                            "ui_component": "searchable_select",
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "locations",
                                "filtros": {}
                            }
                        },
                        {
                            "name_id": "camaras",
                            "label": "Camarógrafos",
                            "ui_component": "searchable_select",
                            "multiple": True,
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "staff",
                                "filtros": {"rol_tags": ["camara", "camarografo", "operador"]}
                            }
                        },
                        {
                            "name_id": "switcher",
                            "label": "Switcher / Director de Cámara",
                            "ui_component": "searchable_select",
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "staff",
                                "filtros": {"rol_tags": ["switcher", "director", "realizador"]}
                            }
                        },
                        {
                            "name_id": "sonido",
                            "label": "Sonido / Audio",
                            "ui_component": "searchable_select",
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "staff",
                                "filtros": {"rol_tags": ["sonido", "sonidista", "audio"]}
                            }
                        },
                        {
                            "name_id": "equipos",
                            "label": "Equipos Técnicos",
                            "ui_component": "searchable_select",
                            "multiple": True,
                            "data_source": {
                                "tipo": "dinamico",
                                "entidad": "inventory",
                                "filtros": {}
                            }
                        },
                        {
                            "name_id": "compartir_ingenieria",
                            "label": "Solicitar Soporte de Ingeniería",
                            "ui_component": "switch",
                            "target_area": "ingenieria"
                        }
                    ]
                }
            ]
        }
        cursor.execute("INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)",
                       ('tpl_produccion_v1', 'produccion', json.dumps(tpl_prod)))


# --- FUNCIONES DE USUARIO (Se mantienen igual) ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def extraer_primer_nombre(nombre: str) -> str:
    partes = nombre.strip().split()
    return partes[0].lower() if partes else ""

def register_user(nombres, apellidos, cargo, area, celular, correo, password, rol='Colaborador'):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed = hash_password(password)
        usuario_interno = extraer_primer_nombre(nombres)
        rol_guardar = rol.strip() if rol else 'Colaborador'
        
        cursor.execute('''
            INSERT INTO users (usuario, nombres, apellidos, cargo, area_encargada, celular, correo, password, rol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (usuario_interno, nombres, apellidos, cargo, area, celular, correo, hashed, rol_guardar))
        
        conn.commit()
        conn.close()
        return True, "Usuario registrado con éxito"
    except sqlite3.IntegrityError as e:
        if "users.usuario" in str(e):
            primer_nom = extraer_primer_nombre(nombres)
            return False, f"El acceso para '{primer_nom}' ya está en uso."
        return False, "El correo electrónico ya está registrado."
    except Exception as e:
        return False, f"Error en el registro: {str(e)}"

def verify_user(primer_nombre_input, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed = hash_password(password)
    usuario_interno = extraer_primer_nombre(primer_nombre_input)
    
    cursor.execute('SELECT * FROM users WHERE usuario = ? AND password = ?', (usuario_interno, hashed))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def is_admin_user(usuario='', nombres='', apellidos='', cargo='', rol='') -> bool:
    """Determina si un usuario tiene el rol de Administrador General del sistema."""
    uname = (usuario or '').strip().lower()
    full = f"{nombres} {apellidos}".strip().lower()
    c = (cargo or '').strip().lower()
    r = (rol or '').strip().lower()
    return (
        r in ['admin general', 'administrador general', 'admin', 'administrador'] or
        uname in ['jose', 'admin', 'administrador'] or
        ('jose rafael' in full and 'cifuentes' in full) or
        'admin' in c or 'administrador' in c
    )

def is_subadmin_user(usuario='', nombres='', apellidos='', cargo='', rol='') -> bool:
    """Determina si un usuario tiene el rol de Sub Admin del sistema."""
    r = (rol or '').strip().lower()
    return r in ['sub admin', 'sub-admin', 'subadmin']

def get_user_by_usuario(usuario_interno):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nombres, apellidos, cargo, usuario, area_encargada, correo, celular, id, rol FROM users WHERE usuario = ?', (usuario_interno,))
    user = cursor.fetchone()
    conn.close()
    if user:
        nom_comp = f"{user[0]} {user[1]}".strip()
        u_id = user[7] if len(user) > 7 and user[7] is not None else user[3]
        db_rol = (user[8] if len(user) > 8 and user[8] else 'Colaborador').strip()
        es_adm = is_admin_user(user[3], user[0], user[1], user[2], db_rol)
        es_sub = is_subadmin_user(user[3], user[0], user[1], user[2], db_rol)
        rol_final = 'Admin General' if es_adm else ('Sub Admin' if es_sub else db_rol)
        return {
            'nombres': user[0],
            'apellidos': user[1],
            'cargo': user[2],
            'usuario': user[3],
            'nombre_completo': nom_comp if nom_comp else user[3],
            'id': u_id,
            'user_id': u_id,
            'iniciales': f"{user[0][0] if user[0] else 'U'}{user[1][0] if user[1] else ''}".upper(),
            'area': user[4],
            'area_encargada': user[4],
            'correo': (user[5] or '').strip(),
            'celular': (user[6] or '').strip(),
            'rol': rol_final,
            'es_admin': es_adm,
            'es_subadmin': es_sub
        }
    return None

def get_all_users() -> list[dict]:
    """Retorna la lista de todos los usuarios registrados en el sistema con su rol y estado de administrador."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, usuario, nombres, apellidos, cargo, area_encargada, celular, correo, rol FROM users ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        db_rol = (r[8] if len(r) > 8 and r[8] else 'Colaborador').strip()
        es_adm = is_admin_user(r[1], r[2], r[3], r[4], db_rol)
        es_sub = is_subadmin_user(r[1], r[2], r[3], r[4], db_rol)
        rol_final = 'Admin General' if es_adm else ('Sub Admin' if es_sub else db_rol)
        res.append({
            'id': r[0],
            'usuario': r[1],
            'nombres': r[2],
            'apellidos': r[3],
            'cargo': r[4],
            'area_encargada': r[5],
            'celular': r[6],
            'correo': r[7],
            'nombre_completo': f"{r[2]} {r[3]}".strip(),
            'rol': rol_final,
            'es_admin': es_adm,
            'es_subadmin': es_sub
        })
    return res

def reset_user_password(user_id: int, new_password: str) -> tuple[bool, str]:
    """Actualiza la contraseña hasheada de un usuario por su ID."""
    if not new_password or len(new_password.strip()) < 3:
        return False, "La contraseña debe tener al menos 3 caracteres."
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed = hash_password(new_password.strip())
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user_id))
        conn.commit()
        conn.close()
        return True, "Contraseña actualizada exitosamente."
    except Exception as e:
        return False, f"Error al restablecer contraseña: {str(e)}"

def delete_user(user_id: int) -> tuple[bool, str]:
    """Elimina un usuario por su ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, "Usuario eliminado correctamente."
    except Exception as e:
        return False, f"Error al eliminar usuario: {str(e)}"

def update_user_profile(user_id: int, nombres: str, apellidos: str, cargo: str, area: str, celular: str, correo: str, rol: str = None) -> tuple[bool, str]:
    """Actualiza la información de perfil de un usuario garantizando protección del Administrador Principal."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si es la cuenta de Jose Rafael (Administrador Principal Inamovible)
        cursor.execute('SELECT usuario, nombres, apellidos, rol FROM users WHERE id = ?', (user_id,))
        curr = cursor.fetchone()
        es_principal = False
        if curr:
            full_curr = f"{curr[1]} {curr[2]}".lower()
            if curr[0].lower() == 'jose' or ('jose rafael' in full_curr and 'cifuentes' in full_curr):
                es_principal = True
        
        usuario_interno = extraer_primer_nombre(nombres)
        rol_guardar = 'Admin General' if es_principal else ((rol or 'Colaborador').strip())
        
        cursor.execute('''
            UPDATE users 
            SET usuario = ?, nombres = ?, apellidos = ?, cargo = ?, area_encargada = ?, celular = ?, correo = ?, rol = ?
            WHERE id = ?
        ''', (usuario_interno, nombres.strip(), apellidos.strip(), cargo.strip(), area.strip(), celular.strip(), correo.strip(), rol_guardar, user_id))
        conn.commit()
        conn.close()
        return True, "Perfil de usuario actualizado correctamente."
    except sqlite3.IntegrityError as e:
        if "users.correo" in str(e):
            return False, "El correo electrónico ya está registrado con otro usuario."
        return False, f"Error de unicidad: {str(e)}"
    except Exception as e:
        return False, f"Error al actualizar usuario: {str(e)}"

# --- NUEVAS FUNCIONES PARA EVENTOS ---
def create_event(fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles_dict):
    """Guarda un nuevo evento en SQLite"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if isinstance(detalles_dict, dict):
        detalles_dict['hora_inicio'] = hora_inicio
        detalles_dict['hora_fin'] = hora_fin
        detalles_dict['nombre_programa'] = nombre_programa
    detalles_json = json.dumps(detalles_dict)
    
    cursor.execute('''
        INSERT INTO events (fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles_json))
    
    conn.commit()
    conn.close()

def normalize_program_name(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    name = re.sub(r'\(.*?\)', '', name) # Quita contenido entre parentesis como (V), (R), (EN VIVO)
    name = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    return name

def time_to_minutes(time_str: str) -> int:
    if not time_str:
        return 0
    parts = str(time_str).strip().split(':')
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0

def events_match_cross_area(name_a, ini_a_str, fin_a_str, name_b, ini_b_str, fin_b_str) -> bool:
    norm_a = normalize_program_name(name_a)
    norm_b = normalize_program_name(name_b)
    if not norm_a or not norm_b:
        return False
        
    name_matches = (norm_a == norm_b) or (len(norm_a) >= 4 and len(norm_b) >= 4 and (norm_a in norm_b or norm_b in norm_a))
    if not name_matches:
        return False
        
    ini_a = time_to_minutes(ini_a_str)
    fin_a = time_to_minutes(fin_a_str) or (ini_a + 30)
    ini_b = time_to_minutes(ini_b_str)
    fin_b = time_to_minutes(fin_b_str) or (ini_b + 30)
    
    # Se solapan en el tiempo o su hora de inicio difiere en <= 30 minutos
    solapan = max(ini_a, ini_b) < min(fin_a, fin_b)
    cercanos = abs(ini_a - ini_b) <= 30
    return solapan or cercanos

def bulk_add_events(events_list: list, overwrite_date_and_area: bool = False) -> tuple[bool, str, int]:
    """
    Inserta o fusiona masivamente eventos de parrilla/cronograma en SQLite en una sola transacción.
    Si overwrite_date_and_area es True, limpia eventos previos de esa fecha y área,
    pero interconecta inteligentemente (Smart Merge) eventos cruzados entre Programación y Producción
    para evitar duplicados y preservar asignaciones técnicas de crew.
    """
    if not events_list:
        return True, "No hay eventos para registrar", 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        fecha_target = events_list[0]['fecha']
        area_target = events_list[0]['tipo'].lower()
        
        # 1. Obtener eventos existentes para la fecha
        cursor.execute('SELECT id, fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles FROM events WHERE fecha = ?', (fecha_target,))
        existing_rows = cursor.fetchall()
        
        existing_events = []
        for r in existing_rows:
            try:
                det = json.loads(r[6])
            except Exception:
                det = {}
            existing_events.append({
                'id': r[0], 'fecha': r[1], 'hora_inicio': r[2], 'hora_fin': r[3],
                'tipo': r[4], 'nombre_programa': r[5], 'detalles': det
            })
            
        interconnected_count = 0
        records_to_insert = []
        
        # 2. Si es Producción importando su cronograma técnico:
        if area_target == 'produccion':
            if overwrite_date_and_area:
                # Elimina solo los eventos independientes creados por Producción previamente
                cursor.execute('DELETE FROM events WHERE fecha = ? AND tipo = ?', (fecha_target, area_target))
                
            campos_prod = ['productor', 'locacion', 'camaras', 'switcher', 'sonido', 'equipos', 'compartir_ingenieria']
            
            for ev in events_list:
                detalles = ev.get('detalles', {})
                if not isinstance(detalles, dict):
                    detalles = {}
                detalles['hora_inicio'] = ev.get('hora_inicio', '')
                detalles['hora_fin'] = ev.get('hora_fin', '')
                detalles['nombre_programa'] = ev.get('nombre_programa', '')
                
                # Buscar el mejor evento de Programación correspondiente (Best Match)
                candidates = []
                p_ini_min = time_to_minutes(ev.get('hora_inicio', ''))
                for ex in existing_events:
                    if ex['tipo'] == 'programacion' and events_match_cross_area(
                        ev['nombre_programa'], ev['hora_inicio'], ev['hora_fin'],
                        ex['nombre_programa'], ex['hora_inicio'], ex['hora_fin']
                    ):
                        ex_ini_min = time_to_minutes(ex.get('hora_inicio', ''))
                        diff = abs(p_ini_min - ex_ini_min)
                        score = 1000 - diff
                        
                        det_ex = ex.get('detalles', {})
                        # Priorizar bloques que requieren producción o son en vivo
                        if det_ex.get('requiere_produccion') or det_ex.get('modalidad') == 'En Vivo':
                            score += 200
                        # Desempate positivo: priorizar estreno / vivo sobre repeticiones (R)
                        raw_title = (ex.get('nombre_programa') or '').lower()
                        if '(r)' not in raw_title and '(repeticion)' not in raw_title:
                            score += 100
                            
                        candidates.append((score, ex))
                        
                matched_prog = None
                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    matched_prog = candidates[0][1]
                        
                if matched_prog:
                    # SMART MERGE: Enriquecer el evento existente de Programación
                    det_existente = matched_prog['detalles']
                    for k in campos_prod:
                        if detalles.get(k):
                            det_existente[k] = detalles[k]
                    # Incorporar campos adicionales homologados que no choquen
                    for k, v in detalles.items():
                        if k not in ['nombre_programa', 'hora_inicio', 'hora_fin', 'modalidad', 'es_parrilla_tv', 'capitulo_tema', 'observaciones', 'pautas_cortes', 'time_range'] and v:
                            det_existente[k] = v
                            
                    det_existente['compartir_produccion'] = True
                    det_existente['requiere_produccion'] = True
                    det_existente['estado_compartido'] = 'confirmado'
                    
                    cursor.execute('UPDATE events SET detalles = ? WHERE id = ?', (json.dumps(det_existente), matched_prog['id']))
                    interconnected_count += 1
                else:
                    # Evento exclusivo de Producción (ej. grabación exterior, cápsulas, etc.)
                    records_to_insert.append((
                        ev['fecha'], ev['hora_inicio'], ev['hora_fin'],
                        'produccion', ev['nombre_programa'], json.dumps(detalles)
                    ))
                    
        # 3. Si es Programación importando su parrilla de emisión:
        elif area_target == 'programacion':
            # Rescatar crew y datos técnicos previamente cargados por Producción para no perderlos
            preserved_crew = []
            for ex in existing_events:
                det = ex['detalles']
                norm = normalize_program_name(ex['nombre_programa'])
                has_crew = any(det.get(k) for k in ['productor', 'locacion', 'camaras', 'switcher', 'sonido'])
                if has_crew:
                    crew_payload = {
                        k: det[k] for k in ['productor', 'locacion', 'camaras', 'switcher', 'sonido', 'equipos', 'compartir_ingenieria', 'estado_compartido'] if k in det
                    }
                    preserved_crew.append({
                        'nombre': ex['nombre_programa'],
                        'norm': norm,
                        'hora_inicio': ex['hora_inicio'],
                        'hora_fin': ex['hora_fin'],
                        'data': crew_payload,
                        'assigned': False
                    })
                    
            # Si existen eventos 'produccion' aislados que coinciden con la parrilla, se absorberán
            prod_absorbed_ids = set()
            for ev in events_list:
                for ex in existing_events:
                    if ex['tipo'] == 'produccion' and events_match_cross_area(
                        ev['nombre_programa'], ev['hora_inicio'], ev['hora_fin'],
                        ex['nombre_programa'], ex['hora_inicio'], ex['hora_fin']
                    ):
                        norm = normalize_program_name(ev['nombre_programa'])
                        crew_payload = {
                            k: ex['detalles'][k] for k in ['productor', 'locacion', 'camaras', 'switcher', 'sonido', 'equipos', 'compartir_ingenieria', 'estado_compartido'] if k in ex['detalles']
                        }
                        preserved_crew.append({
                            'nombre': ev['nombre_programa'],
                            'norm': norm,
                            'hora_inicio': ex['hora_inicio'],
                            'hora_fin': ex['hora_fin'],
                            'data': crew_payload,
                            'assigned': False
                        })
                        prod_absorbed_ids.add(ex['id'])
                        
            if overwrite_date_and_area:
                cursor.execute('DELETE FROM events WHERE fecha = ? AND tipo = ?', (fecha_target, area_target))
                # Eliminar los eventos de produccion que acaban de ser absorbidos para evitar duplicados
                for pid in prod_absorbed_ids:
                    cursor.execute('DELETE FROM events WHERE id = ?', (pid,))
                    
            for ev in events_list:
                detalles = ev.get('detalles', {})
                if not isinstance(detalles, dict):
                    detalles = {}
                detalles['hora_inicio'] = ev.get('hora_inicio', '')
                detalles['hora_fin'] = ev.get('hora_fin', '')
                detalles['nombre_programa'] = ev.get('nombre_programa', '')
                
                # Asignar personal rescatado al bloque horario más cercano (sin duplicar en repeticiones)
                ev_ini_min = time_to_minutes(ev.get('hora_inicio', ''))
                best_pc = None
                best_score = -999999
                for pc in preserved_crew:
                    if pc['assigned']:
                        continue
                    if events_match_cross_area(ev['nombre_programa'], ev['hora_inicio'], ev['hora_fin'], pc['nombre'], pc['hora_inicio'], pc['hora_fin']):
                        diff = abs(ev_ini_min - time_to_minutes(pc['hora_inicio']))
                        score = 1000 - diff
                        raw_title = (ev.get('nombre_programa') or '').lower()
                        if '(r)' not in raw_title and '(repeticion)' not in raw_title:
                            score += 150
                        if score > best_score:
                            best_score = score
                            best_pc = pc
                            
                if best_pc:
                    best_pc['assigned'] = True
                    detalles.update(best_pc['data'])
                    detalles['compartir_produccion'] = True
                    detalles['requiere_produccion'] = True
                    if 'estado_compartido' not in detalles:
                        detalles['estado_compartido'] = 'confirmado'
                    interconnected_count += 1
                    
                records_to_insert.append((
                    ev['fecha'], ev['hora_inicio'], ev['hora_fin'],
                    'programacion', ev['nombre_programa'], json.dumps(detalles)
                ))
                
        # 4. Otras áreas (ingeniería, etc.)
        else:
            if overwrite_date_and_area and len(events_list) > 0:
                cursor.execute('DELETE FROM events WHERE fecha = ? AND tipo = ?', (fecha_target, area_target))
            for ev in events_list:
                detalles = ev.get('detalles', {})
                if isinstance(detalles, dict):
                    detalles['hora_inicio'] = ev.get('hora_inicio', '')
                    detalles['hora_fin'] = ev.get('hora_fin', '')
                    detalles['nombre_programa'] = ev.get('nombre_programa', '')
                records_to_insert.append((
                    ev['fecha'], ev['hora_inicio'], ev['hora_fin'],
                    area_target, ev['nombre_programa'],
                    json.dumps(detalles) if isinstance(detalles, dict) else str(detalles)
                ))
                
        if records_to_insert:
            cursor.executemany('''
                INSERT INTO events (fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', records_to_insert)
            
        conn.commit()
        total_saved = len(records_to_insert) + interconnected_count
        conn.close()
        
        msg_inter = f" (incluyendo {interconnected_count} interconectados con éxito)" if interconnected_count > 0 else ""
        return True, f"Se procesaron {total_saved} programas{msg_inter} exitosamente", total_saved
    except Exception as e:
        return False, f"Error al registrar eventos: {str(e)}", 0


def get_events_by_date(fecha, area_usuario):
    """Obtiene eventos de un día filtrando por la privacidad Universal (V4)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE fecha = ? ORDER BY hora_inicio ASC', (fecha,))
    rows = cursor.fetchall()
    conn.close()
    
    area = area_usuario.lower()
    events = []
    
    for r in rows:
        tipo_evento = r[4]
        detalles = json.loads(r[6])
        
        # ========================================================
        # LÓGICA DE VISIBILIDAD (V4 PURA)
        # ========================================================
        visible = False
        
        # REGLA 1: El evento fue creado por mi área (Soy el dueño)
        if tipo_evento == area:
            visible = True
            
        # REGLA 2: El evento tiene un Switch encendido apuntando a mi área
        elif detalles.get(f'compartir_{area}', False) == True:
            visible = True
            
        if visible:
            events.append({
                'id': r[0], 'fecha': r[1], 'hora_inicio': r[2], 'hora_fin': r[3],
                'tipo': tipo_evento, 'nombre_programa': r[5], 'detalles': detalles
            })
    return events


def get_events_by_month(year, month, area_usuario):
    """Filtra los eventos del mes para dibujar solo los puntos y badges autorizados (V4)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    prefix = f"{year}-{month:02d}-%"
    cursor.execute('SELECT id, fecha, hora_inicio, hora_fin, tipo, nombre_programa, detalles FROM events WHERE fecha LIKE ? ORDER BY hora_inicio ASC', (prefix,))
    rows = cursor.fetchall()
    conn.close()
    
    area = area_usuario.lower()
    events_by_day = {}
    
    for r in rows:
        fecha_completa = r[1]
        dia = int(fecha_completa.split('-')[2])
        tipo_evento = r[4]
        detalles = json.loads(r[6])
        
        # ========================================================
        # LÓGICA DE VISIBILIDAD (EL PUENTE ENTRE MUNDOS V4)
        # ========================================================
        visible = False
        
        if tipo_evento == area:
            visible = True
        elif detalles.get(f'compartir_{area}', False) == True:
            visible = True
            
        if visible:
            if dia not in events_by_day:
                events_by_day[dia] = []
            events_by_day[dia].append({
                'id': r[0],
                'fecha': r[1],
                'hora_inicio': r[2],
                'hora_fin': r[3],
                'tipo': tipo_evento,
                'nombre_programa': r[5],
                'detalles': detalles
            })
            
    return events_by_day

def update_event(event_id, hora_inicio, hora_fin, nombre_programa, detalles_dict):
    """Actualiza el JSON y las columnas principales de un evento existente"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if isinstance(detalles_dict, dict):
        detalles_dict['hora_inicio'] = hora_inicio
        detalles_dict['hora_fin'] = hora_fin
        detalles_dict['nombre_programa'] = nombre_programa
    detalles_json = json.dumps(detalles_dict)
    
    cursor.execute('''
        UPDATE events 
        SET hora_inicio = ?, hora_fin = ?, nombre_programa = ?, detalles = ? 
        WHERE id = ?
    ''', (hora_inicio, hora_fin, nombre_programa, detalles_json, event_id))
    
    conn.commit()
    conn.close()

def delete_event(event_id):
    """Elimina un evento por su ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

# --- FUNCIONES DE CATÁLOGO (PERSONAL, INVENTARIO Y ROLES) ---
def add_staff(nombre, rol, telefono, correo):
    data_dict = {
        "field_0": nombre,
        "field_1": telefono,
        "field_2": correo,
        "field_3": rol
    }
    add_custom_record('system_staff', data_dict)

def get_all_staff():
    records = get_all_custom_records('system_staff')
    return [{
        'id': r['id'],
        'nombre': r['data'].get('field_0') or '',
        'telefono': r['data'].get('field_1') or '',
        'correo': r['data'].get('field_2') or '',
        'rol': r['data'].get('field_3') or ''
    } for r in records]

def delete_staff(id_staff):
    delete_custom_record(id_staff)

def add_inventory(nombre, categoria, serial=None, foto=None, complemento=None, cantidad=1):
    fotos_list = []
    if foto:
        try:
            fotos_list = json.loads(foto)
            if not isinstance(fotos_list, list):
                fotos_list = [foto]
        except Exception:
            fotos_list = [foto]
            
    accs_list = []
    if complemento:
        try:
            accs_list = json.loads(complemento)
            if not isinstance(accs_list, list):
                accs_list = [{'nombre': complemento, 'serial': ''}]
        except Exception:
            accs_list = [{'nombre': complemento, 'serial': ''}]
            
    data_dict = {
        "field_0": nombre,
        "field_1": categoria,
        "field_2": serial,
        "field_3": cantidad,
        "field_4": fotos_list,
        "field_5": accs_list
    }
    add_custom_record('system_inventory', data_dict)

def get_all_inventory():
    records = get_all_custom_records('system_inventory')
    return [{
        'id': r['id'],
        'nombre': r['data'].get('field_0') or '',
        'categoria': r['data'].get('field_1') or '',
        'serial': r['data'].get('field_2') or '',
        'cantidad': r['data'].get('field_3') or 1,
        'foto': json.dumps(r['data'].get('field_4')) if r['data'].get('field_4') else None,
        'complemento': json.dumps(r['data'].get('field_5')) if r['data'].get('field_5') else None
    } for r in records]

def delete_inventory(id_item):
    delete_custom_record(id_item)

# --- NUEVAS: GESTIÓN DE ROLES ---
def add_role(nombre_rol):
    # Validar si ya existe
    records = get_all_custom_records('system_roles')
    if any(r['data'].get('field_0', '').strip().lower() == nombre_rol.strip().lower() for r in records):
        return False, "Este rol ya existe en el sistema"
    
    data_dict = {"field_0": nombre_rol.strip()}
    success, msg = add_custom_record('system_roles', data_dict)
    if success:
        return True, "Rol creado exitosamente"
    return False, msg

def get_all_roles():
    records = get_all_custom_records('system_roles')
    return [{
        'id': r['id'],
        'nombre_rol': r['data'].get('field_0') or ''
    } for r in records]

def delete_role(id_role):
    delete_custom_record(id_role)

def update_role(id_role, nuevo_nombre_rol, nombre_antiguo):
    try:
        # Validar si el nuevo nombre ya existe en otro registro
        records = get_all_custom_records('system_roles')
        if any(r['data'].get('field_0', '').strip().lower() == nuevo_nombre_rol.strip().lower() and r['id'] != id_role for r in records):
            return False, "Ya existe un rol registrado con ese nombre exacto"
            
        data_dict = {"field_0": nuevo_nombre_rol.strip()}
        success, msg = update_custom_record(id_role, data_dict)
        if not success:
            return False, msg
            
        # Reemplazo en cascada en los registros del personal (system_staff)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, data_json FROM custom_module_records WHERE module_id = 'system_staff'")
        staff_rows = cursor.fetchall()
        for s_id, s_json in staff_rows:
            try:
                s_data = json.loads(s_json)
                rol_val = s_data.get('field_3', '')
                if rol_val and nombre_antiguo in rol_val:
                    s_data['field_3'] = rol_val.replace(nombre_antiguo, nuevo_nombre_rol)
                    cursor.execute("UPDATE custom_module_records SET data_json = ? WHERE id = ?", (json.dumps(s_data), s_id))
            except Exception:
                pass
        conn.commit()
        conn.close()
        return True, "Rol actualizado correctamente"
    except Exception as e:
        return False, f"Error al actualizar: {str(e)}"
    
def get_template_config(template_id):
    """Busca el JSON de la plantilla en la base de datos y lo devuelve como diccionario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT config_json FROM event_templates WHERE template_id = ?', (template_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None

def check_area_has_template(area_usuario):
    """
    Verifica si el área del usuario ya ha configurado su propia plantilla de eventos.
    Retorna True si existe, False si es un área nueva sin configurar.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Buscamos si hay alguna plantilla guardada bajo el tenant_id (área) de este usuario,
    # excluyendo los reportes
    cursor.execute("SELECT COUNT(*) FROM event_templates WHERE tenant_id = ? AND template_id NOT LIKE 'report_%'", (area_usuario.lower(),))
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0

def get_template_by_area(area_usuario):
    """Busca la plantilla JSON correspondiente al área del usuario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Buscamos la plantilla de eventos correspondiente al área, excluyendo reportes
    cursor.execute("SELECT config_json FROM event_templates WHERE tenant_id = ? AND template_id NOT LIKE 'report_%'", (area_usuario.lower(),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None

def save_report_layout(area_usuario, config_dict):
    """Guarda la configuración visual del reporte (columnas, logo, título) en la base de datos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    config_json = json.dumps(config_dict)
    
    # Creamos un ID único para diferenciarlo de la plantilla de formularios
    template_id = f"report_{area_usuario.lower()}"
    tenant = area_usuario.lower()
    
    try:
        cursor.execute('INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)',
                       (template_id, tenant, config_json))
    except sqlite3.IntegrityError:
        cursor.execute('UPDATE event_templates SET config_json = ? WHERE template_id = ?',
                       (config_json, template_id))
    conn.commit()
    conn.close()

def get_report_layout(area_usuario):
    """Recupera la configuración guardada del reporte."""
    conn = get_db_connection()
    cursor = conn.cursor()
    template_id = f"report_{area_usuario.lower()}"
    
    cursor.execute('SELECT config_json FROM event_templates WHERE template_id = ?', (template_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None

def save_system_logo(logo_b64: str) -> bool:
    """Guarda el logo del sistema de forma persistente para todos los reportes y módulos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    config_json = json.dumps({'logo_b64': logo_b64})
    template_id = 'system_global_logo'
    cursor.execute('SELECT id FROM event_templates WHERE template_id = ?', (template_id,))
    if cursor.fetchone():
        cursor.execute('UPDATE event_templates SET config_json = ? WHERE template_id = ?', (config_json, template_id))
    else:
        cursor.execute('INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)',
                       (template_id, 'system', config_json))
    conn.commit()
    conn.close()
    return True

def get_system_logo() -> str | None:
    """Recupera el logo persistente del sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_json FROM event_templates WHERE template_id = 'system_global_logo'")
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row[0]).get('logo_b64')
        except Exception:
            return None
    return None

# --- CONFIGURACIÓN DE PLANTILLA DE ACTA DE RETRANSMISIÓN ---

DEFAULT_ACTA_RETRANSMISION_TEMPLATE = {
    'titulo': 'AUTORIZACIÓN TRANSMISIÓN CANAL TELEAMIGA',
    'entidad': 'FUNDACIÓN ICTUS',
    'nit_entidad': 'NIT. 830080615-2',
    'texto_apertura': (
        'La Fundación Ictus, entidad sin ánimo de lucro, operadora de la señal del Canal Teleamiga, '
        'NIT 830.080.615-2, representada por {gerente_nombre}, en su calidad de Representante Legal '
        'y Gerente de la institución, se permite autorizar a:'
    ),
    'clausula_cabeceras': 'La autorización cubre todas sus cabeceras, tanto actuales como próximas.',
    'clausula_vigencia': (
        'Esta autorización se expide a los {fecha_legal}, por un periodo de {periodo_vigencia}, '
        'contando a partir de la fecha de expedición.'
    ),
    'periodo_vigencia': 'un (1) año',
    'clausula_tecnica': 'El medio actual para la recepción de la señal es por el satélite comercial SES-6 y por IP protocolo SRT.',
    'despedida': 'Atentamente,',
    'nombre_firmante': 'CLAUDIA GARZON',
    'cargo_firmante': 'Gerente del Canal',
    'celular_firmante': '3138932021',
    'pie_pagina': 'MediaHub • Validación Documental MINTIC RTI • Radicado: {codigo_acta}',
}

def get_acta_retransmision_template() -> dict:
    """Recupera la plantilla configurable del Acta de Retransmisión desde la BD o devuelve la plantilla oficial por defecto."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_json FROM event_templates WHERE template_id = 'retransmision_acta_template'")
    row = cursor.fetchone()
    conn.close()
    merged = dict(DEFAULT_ACTA_RETRANSMISION_TEMPLATE)
    if row:
        try:
            saved = json.loads(row[0])
            if isinstance(saved, dict):
                merged.update(saved)
        except Exception:
            pass
    return merged

def save_acta_retransmision_template(tpl: dict) -> bool:
    """Guarda la configuración personalizada del Acta de Retransmisión."""
    conn = get_db_connection()
    cursor = conn.cursor()
    config_json = json.dumps(tpl, ensure_ascii=False)
    template_id = 'retransmision_acta_template'
    cursor.execute('SELECT id FROM event_templates WHERE template_id = ?', (template_id,))
    if cursor.fetchone():
        cursor.execute('UPDATE event_templates SET config_json = ? WHERE template_id = ?', (config_json, template_id))
    else:
        cursor.execute('INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES (?, ?, ?)',
                       (template_id, 'system', config_json))
    conn.commit()
    conn.close()
    return True

def reset_acta_retransmision_template() -> bool:
    """Restaura la plantilla oficial predeterminada de Retransmisión."""
    return save_acta_retransmision_template(DEFAULT_ACTA_RETRANSMISION_TEMPLATE)


# =========================================================================
# --- CONFIGURACIÓN Y MOTOR DE REGLAS DE TRASLADO Y TRANSICIÓN TÉCNICA ---
# =========================================================================

DEFAULT_TRANSITION_RULES = {
    'activo': True,
    'tiempo_mismo_estudio': 3,            # minutos mínimos requeridos entre programas en el mismo estudio/locación
    'tiempo_cambio_estudio': 10,          # minutos mínimos requeridos cuando cambia de estudio/locación (ej: Estudio 1 a Estudio 3)
    'tiempo_exterior': 30,                # minutos mínimos requeridos si involucra locación de exterior
    'tiempo_ajuste_parrilla_sugerido': 3, # minutos sugeridos para que Programación/Emisión ajuste en parrilla
    'modo_bloqueo': False,                # False = Advertencia y notificación; True = Bloqueo estricto al guardar
    'campos_supervisados': ['sonido', 'sonidista', 'camaras', 'camara', 'camarografo', 'switcher', 'productor'],
    'roles_supervisados': ['Sonidista', 'Camarógrafo', 'Switcher', 'Técnico de Audio', 'Productor'],
    'areas_notificar': ['programacion', 'master', 'emision', 'produccion'],
    'exterior_keywords': ['exterior', 'exteriores', 'remoto', 'unidad movil', 'calle', 'banco de alimentos']
}

def get_transition_rules_config() -> dict:
    """Recupera las reglas de traslado de personal desde la base de datos o retorna las predeterminadas."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_json FROM event_templates WHERE template_id = 'personnel_transition_rules'")
    row = cursor.fetchone()
    conn.close()
    
    cfg = dict(DEFAULT_TRANSITION_RULES)
    if row and row[0]:
        try:
            saved = json.loads(row[0])
            cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_transition_rules_config(config_dict: dict) -> tuple[bool, str]:
    """Guarda la configuración personalizada de reglas de traslado en la BD."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        config_json = json.dumps(config_dict, ensure_ascii=False)
        cursor.execute("SELECT template_id FROM event_templates WHERE template_id = 'personnel_transition_rules'")
        if cursor.fetchone():
            cursor.execute("UPDATE event_templates SET config_json = ? WHERE template_id = 'personnel_transition_rules'", (config_json,))
        else:
            cursor.execute("INSERT INTO event_templates (template_id, tenant_id, config_json) VALUES ('personnel_transition_rules', 'system', ?)", (config_json,))
        conn.commit()
        conn.close()
        return True, "Reglas de traslado guardadas correctamente."
    except Exception as e:
        return False, f"Error al guardar reglas: {str(e)}"

def reset_transition_rules_config() -> tuple[bool, str]:
    """Restaura los valores oficiales predeterminados para las reglas de traslado."""
    return save_transition_rules_config(DEFAULT_TRANSITION_RULES)

def detect_personnel_transition_conflicts(fecha: str, candidate_event: dict = None) -> list[dict]:
    """
    Analiza todos los eventos de una fecha en busca de personal técnico asignado en bloques
    consecutivos o casi consecutivos con margen de tiempo insuficiente para el traslado
    entre estudios o locaciones.
    
    Si se pasa candidate_event (un evento que se está creando o editando), se simula su inclusión.
    """
    rules = get_transition_rules_config()
    if not rules.get('activo', True):
        return []
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, hora_inicio, hora_fin, tipo, nombre_programa, detalles FROM events WHERE fecha = ?', (fecha,))
    rows = cursor.fetchall()
    conn.close()

    parsed_events = []
    seen_ids = set()
    candidate_id = candidate_event.get('id') if candidate_event else None

    for r in rows:
        eid, h_ini, h_fin, tipo, prog, det_raw = r
        if candidate_id and eid == candidate_id:
            continue
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        try:
            det = json.loads(det_raw)
        except Exception:
            det = {}
        parsed_events.append({
            'id': eid,
            'hora_inicio': h_ini,
            'hora_fin': h_fin,
            'min_ini': time_to_minutes(h_ini),
            'min_fin': time_to_minutes(h_fin),
            'tipo': tipo,
            'nombre': prog,
            'nombre_programa': prog,
            'locacion': str(det.get('locacion') or det.get('estudio') or 'Canal').strip(),
            'detalles': det
        })

    if candidate_event:
        h_ini_c = candidate_event.get('hora_inicio', '00:00')
        h_fin_c = candidate_event.get('hora_fin', '00:00')
        det_c = candidate_event.get('detalles') if isinstance(candidate_event.get('detalles'), dict) else candidate_event
        loc_c = str(det_c.get('locacion') or det_c.get('estudio') or 'Canal').strip()
        cand_nom = candidate_event.get('nombre_programa') or candidate_event.get('nombre') or 'Nuevo Evento'
        parsed_events.append({
            'id': candidate_id or -999,
            'hora_inicio': h_ini_c,
            'hora_fin': h_fin_c,
            'min_ini': time_to_minutes(h_ini_c),
            'min_fin': time_to_minutes(h_fin_c),
            'tipo': candidate_event.get('tipo', 'produccion'),
            'nombre': cand_nom,
            'nombre_programa': cand_nom,
            'locacion': loc_c,
            'detalles': det_c
        })

    campos = rules.get('campos_supervisados', ['sonido', 'sonidista', 'camaras', 'camara', 'camarografo', 'switcher', 'productor'])
    person_events = {}

    for ev in parsed_events:
        det = ev['detalles']
        for c in campos:
            val = det.get(c)
            if not val:
                continue
            raw_names = []
            if isinstance(val, list):
                raw_names = [str(x).strip() for x in val if x]
            else:
                raw_names = [x.strip() for x in re.split(r'[,;\n]+', str(val)) if x.strip()]
            for name in raw_names:
                norm_name = re.sub(r'[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ]', '', name.lower())
                if len(norm_name) < 3:
                    continue
                if norm_name not in person_events:
                    person_events[norm_name] = {'nombre_display': name, 'eventos': []}
                if not any(item['evento']['id'] == ev['id'] for item in person_events[norm_name]['eventos']):
                    person_events[norm_name]['eventos'].append({
                        'campo': c,
                        'evento': ev
                    })

    conflicts = []
    ext_keys = [k.lower() for k in rules.get('exterior_keywords', ['exterior', 'exteriores', 'remoto', 'unidad movil', 'calle', 'banco de alimentos'])]

    for p_key, p_data in person_events.items():
        p_data['eventos'].sort(key=lambda x: x['evento']['min_ini'])
        ev_list = p_data['eventos']
        for i in range(len(ev_list) - 1):
            item_a = ev_list[i]
            item_b = ev_list[i+1]
            ev_a = item_a['evento']
            ev_b = item_b['evento']
            if ev_a['id'] == ev_b['id']:
                continue
            
            margen = ev_b['min_ini'] - ev_a['min_fin']
            
            loc_a = ev_a['locacion'].lower()
            loc_b = ev_b['locacion'].lower()
            es_exterior = any(k in loc_a or k in loc_b for k in ext_keys)
            cambio_loc = (loc_a != loc_b)
            
            if es_exterior:
                req = rules.get('tiempo_exterior', 30)
            elif cambio_loc:
                req = rules.get('tiempo_cambio_estudio', 10)
            else:
                req = rules.get('tiempo_mismo_estudio', 3)
                
            if margen < req:
                tipo_alerta = "Solapamiento Horario" if margen < 0 else ("Traslado con Cambio de Locación" if cambio_loc else "Margen Muy Ajustado")
                ajuste_sug = rules.get('tiempo_ajuste_parrilla_sugerido', 3)
                conflicts.append({
                    'persona': p_data['nombre_display'],
                    'rol_a': item_a['campo'].capitalize(),
                    'rol_b': item_b['campo'].capitalize(),
                    'tipo_alerta': tipo_alerta,
                    'fecha': fecha,
                    'evento_a': ev_a,
                    'evento_b': ev_b,
                    'margen': margen,
                    'requerido': req,
                    'cambio_locacion': cambio_loc,
                    'locacion_a': ev_a['locacion'],
                    'locacion_b': ev_b['locacion'],
                    'ajuste_sugerido': ajuste_sug,
                    'mensaje': f"{p_data['nombre_display']} ({item_a['campo']}) finaliza '{ev_a['nombre_programa']}' ({ev_a['locacion']}) a las {ev_a['hora_fin']} e inicia '{ev_b['nombre_programa']}' ({ev_b['locacion']}) a las {ev_b['hora_inicio']} (Margen: {margen} min, Requerido: {req} min). Requiere ajuste de hasta {ajuste_sug} min en parrilla."
                })

    return conflicts

def get_active_transition_alerts(area_usuario: str = None, fecha: str = None) -> list[dict]:
    """
    Obtiene las alertas activas de traslado para una fecha dada (o la fecha de hoy por defecto),
    filtrando según las áreas que tienen configurado recibir notificaciones.
    """
    rules = get_transition_rules_config()
    if not rules.get('activo', True):
        return []
    
    if area_usuario:
        area_clean = area_usuario.strip().lower()
        areas_notif = [a.strip().lower() for a in rules.get('areas_notificar', ['programacion', 'master', 'emision', 'produccion'])]
        if area_clean not in areas_notif and area_clean not in ['administracion', 'ingenieria', 'sistemas']:
            return []

    if not fecha:
        fecha = datetime.now().strftime('%Y-%m-%d')
        
    return detect_personnel_transition_conflicts(fecha)


# --- NUEVAS FUNCIONES PARA ADMINISTRACIÓN ---

def update_staff(id_staff, nombre, rol, telefono, correo):
    """Actualiza la información de un miembro del personal."""
    data_dict = {
        "field_0": nombre,
        "field_1": telefono,
        "field_2": correo,
        "field_3": rol
    }
    success, msg = update_custom_record(id_staff, data_dict)
    if success:
        return True, "Personal actualizado correctamente"
    return False, msg

def add_category(nombre_categoria):
    """Añade una nueva categoría para el inventario."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO inventory_categories (nombre_categoria) VALUES (?)', (nombre_categoria,))
        conn.commit()
        conn.close()
        return True, "Categoría creada exitosamente"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Esta categoría ya existe"

def get_all_categories():
    """Obtiene todas las categorías de inventario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory_categories ORDER BY nombre_categoria')
    rows = cursor.fetchall()
    conn.close()
    return [{'id': r[0], 'nombre_categoria': r[1]} for r in rows]

def delete_category(id_category):
    """Elimina una categoría del inventario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM inventory_categories WHERE id = ?', (id_category,))
    conn.commit()
    conn.close()

def update_category(id_category, nuevo_nombre, nombre_antiguo):
    """Actualiza el nombre de una categoría y lo aplica en cascada al inventario."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE inventory_categories SET nombre_categoria = ? WHERE id = ?', (nuevo_nombre, id_category))
        
        # 1. Copia de respaldo (cascada de tabla legacy)
        cursor.execute('UPDATE inventory SET categoria = ? WHERE categoria = ?', (nuevo_nombre, nombre_antiguo))
        
        # 2. Cascada en registros dinámicos de inventario (system_inventory)
        cursor.execute("SELECT id, data_json FROM custom_module_records WHERE module_id = 'system_inventory'")
        inv_rows = cursor.fetchall()
        for i_id, i_json in inv_rows:
            try:
                i_data = json.loads(i_json)
                if i_data.get('field_1') == nombre_antiguo:
                    i_data['field_1'] = nuevo_nombre
                    cursor.execute("UPDATE custom_module_records SET data_json = ? WHERE id = ?", (json.dumps(i_data), i_id))
            except Exception:
                pass
                
        conn.commit()
        conn.close()
        return True, "Categoría actualizada correctamente"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Ya existe una categoría con ese nombre"

# --- NUEVAS FUNCIONES PARA EDICIÓN Y LOCACIONES ---
def update_inventory(id_item, nombre, categoria, serial=None, foto=None, complemento=None, cantidad=1):
    """Actualiza el nombre, categoría, serial, foto, complementos y cantidad de un equipo existente."""
    fotos_list = []
    if foto:
        try:
            fotos_list = json.loads(foto)
            if not isinstance(fotos_list, list):
                fotos_list = [foto]
        except Exception:
            fotos_list = [foto]
            
    accs_list = []
    if complemento:
        try:
            accs_list = json.loads(complemento)
            if not isinstance(accs_list, list):
                accs_list = [{'nombre': complemento, 'serial': ''}]
        except Exception:
            accs_list = [{'nombre': complemento, 'serial': ''}]
            
    data_dict = {
        "field_0": nombre,
        "field_1": categoria,
        "field_2": serial,
        "field_3": cantidad,
        "field_4": fotos_list,
        "field_5": accs_list
    }
    success, msg = update_custom_record(id_item, data_dict)
    if success:
        return True, "Equipo actualizado correctamente"
    return False, msg

def add_location(nombre):
    """Añade una nueva locación/estudio."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO locations (nombre) VALUES (?)', (nombre,))
        conn.commit()
        conn.close()
        return True, "Locación agregada"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Esta locación ya existe"

def get_all_locations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM locations ORDER BY nombre')
    rows = cursor.fetchall()
    conn.close()
    return [{'id': r[0], 'nombre': r[1]} for r in rows]

def delete_location(id_loc):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM locations WHERE id = ?', (id_loc,))
    conn.commit()
    conn.close()

def update_location(id_loc, nuevo_nombre):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE locations SET nombre = ? WHERE id = ?', (nuevo_nombre, id_loc))
        conn.commit()
        conn.close()
        return True, "Locación actualizada"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Ya existe una locación con ese nombre"

# --- FUNCIONES PARA GESTIONES PERSONALIZADAS ---

def add_custom_module(module_id, nombre, icono, config_dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        config_json = json.dumps(config_dict)
        cursor.execute('INSERT INTO custom_modules (id, nombre, icono, config_json) VALUES (?, ?, ?, ?)',
                       (module_id, nombre, icono, config_json))
        conn.commit()
        conn.close()
        return True, "Gestión creada exitosamente"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Ya existe una gestión con ese identificador"
    except Exception as e:
        return False, f"Error: {str(e)}"

def update_custom_module(module_id, nombre, icono, config_dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        config_json = json.dumps(config_dict)
        cursor.execute('UPDATE custom_modules SET nombre = ?, icono = ?, config_json = ? WHERE id = ?',
                       (nombre, icono, config_json, module_id))
        conn.commit()
        conn.close()
        return True, "Gestión actualizada exitosamente"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_all_custom_modules():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, icono, config_json FROM custom_modules ORDER BY nombre')
    rows = cursor.fetchall()
    conn.close()
    return [{
        'id': r[0],
        'nombre': r[1],
        'icono': r[2],
        'config': json.loads(r[3])
    } for r in rows]

def delete_custom_module(module_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM custom_modules WHERE id = ?', (module_id,))
        conn.commit()
        conn.close()
        return True, "Gestión eliminada con éxito"
    except Exception as e:
        return False, f"Error: {str(e)}"

def add_custom_record(module_id, data_dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        data_json = json.dumps(data_dict)
        cursor.execute('INSERT INTO custom_module_records (module_id, data_json) VALUES (?, ?)',
                       (module_id, data_json))
        conn.commit()
        conn.close()
        return True, "Registro guardado correctamente"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_all_custom_records(module_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, data_json FROM custom_module_records WHERE module_id = ? ORDER BY id DESC', (module_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{
        'id': r[0],
        'data': json.loads(r[1])
    } for r in rows]

def update_custom_record(record_id, data_dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        data_json = json.dumps(data_dict)
        cursor.execute('UPDATE custom_module_records SET data_json = ? WHERE id = ?', (data_json, record_id))
        conn.commit()
        conn.close()
        return True, "Registro actualizado correctamente"
    except Exception as e:
        return False, f"Error: {str(e)}"

def delete_custom_record(record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM custom_module_records WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()
        return True, "Registro eliminado correctamente"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_custom_module(module_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, icono, config_json FROM custom_modules WHERE id = ?', (module_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'nombre': row[1],
            'icono': row[2],
            'config': json.loads(row[3])
        }
    return None

def get_admin_quick_access_modules() -> list[str]:
    """Retorna la lista de module_ids anclados como acceso rápido en el panel de ingeniería."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_quick_access (
            module_id TEXT PRIMARY KEY,
            created_at TEXT
        )
    ''')
    cursor.execute("SELECT module_id FROM admin_quick_access ORDER BY rowid ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def toggle_admin_quick_access(module_id: str) -> bool:
    """Alterna el estado de acceso rápido de una gestión en la barra superior. Retorna True si quedó anclada."""
    if not module_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_quick_access (
            module_id TEXT PRIMARY KEY,
            created_at TEXT
        )
    ''')
    cursor.execute("SELECT module_id FROM admin_quick_access WHERE module_id = ?", (module_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM admin_quick_access WHERE module_id = ?", (module_id,))
        is_pinned = False
    else:
        cursor.execute("INSERT INTO admin_quick_access (module_id, created_at) VALUES (?, ?)", 
                       (module_id, datetime.now().isoformat()))
        is_pinned = True
    conn.commit()
    conn.close()
    return is_pinned

def is_module_quick_access(module_id: str) -> bool:
    """Verifica si un módulo está actualmente anclado como acceso rápido."""
    if not module_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_quick_access (
            module_id TEXT PRIMARY KEY,
            created_at TEXT
        )
    ''')
    cursor.execute("SELECT module_id FROM admin_quick_access WHERE module_id = ?", (module_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)

def bulk_add_custom_records(module_id: str, records_dict_list: list) -> tuple[bool, str, int]:
    """
    Inserta múltiples registros en custom_module_records en una sola transacción.
    Retorna (success, message, count).
    """
    if not records_dict_list:
        return True, "No hay registros para importar", 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        data_tuples = [(module_id, json.dumps(rec)) for rec in records_dict_list]
        cursor.executemany('INSERT INTO custom_module_records (module_id, data_json) VALUES (?, ?)', data_tuples)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return True, f"Se importaron {count} registros exitosamente", count
    except Exception as e:
        return False, f"Error en importación masiva: {str(e)}", 0

def bulk_add_categories(categories_list: list) -> int:
    """
    Agrega una lista de categorías a inventory_categories si no existen.
    Retorna la cantidad de categorías creadas.
    """
    if not categories_list:
        return 0
    added_count = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    for cat in categories_list:
        cat_clean = str(cat).strip()
        if not cat_clean:
            continue
        try:
            cursor.execute('INSERT OR IGNORE INTO inventory_categories (nombre_categoria) VALUES (?)', (cat_clean,))
            if cursor.rowcount > 0:
                added_count += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return added_count

def obtener_detalles_modulo_vinculado(target_module_id: str) -> dict:
    """
    Obtiene los detalles completos de cada ítem de una gestión vinculada (incluyendo cantidad,
    fotos, serial, modelo, categoría, estado, correo, celular y rol para personal).
    Soporta tanto registros principales como accesorios o sub-equipos.
    Retorna un diccionario {id_item: dict_con_detalles}.
    """
    if not target_module_id:
        return {}
        
    target_module = get_custom_module(target_module_id)
    if not target_module:
        return {}
        
    records = get_all_custom_records(target_module_id)
    fields = target_module.get('config', [])
    mod_nombre_lower = target_module.get('nombre', '').lower()
    mod_icono = target_module.get('icono', '')
    
    es_modulo_personal = (
        target_module_id == 'system_staff' or
        mod_icono == 'person' or
        any(k in mod_nombre_lower for k in ['personal', 'staff', 'empleado', 'colaborador', 'usuario', 'persona', 'responsable', 'docente', 'funcionario'])
    )
    
    key_nombre = None
    key_serial = None
    lbl_serial = ""
    key_categoria = None
    key_cantidad = None
    key_estado = None
    key_fotos = None
    key_accs = None
    key_correo = None
    key_telefono = None
    key_rol = None
    key_cedula = None
    
    for f_idx, field in enumerate(fields):
        f_id = field.get('key', f"field_{f_idx}")
        lbl = str(field.get('label', '')).lower()
        f_type = field.get('type', 'text')
        
        if any(k in lbl for k in ['correo', 'email', 'e-mail']):
            key_correo = f_id
        elif any(k in lbl for k in ['teléfono', 'telefono', 'celular', 'cel', 'móvil', 'movil', 'phone']):
            key_telefono = f_id
        elif any(k in lbl for k in ['rol', 'cargo', 'puesto', 'función', 'funcion']):
            key_rol = f_id
        elif any(k in lbl for k in ['cédula', 'cedula', 'documento', 'identific', 'cc', 'c.c', 'dni']):
            key_cedula = f_id
            
        if f_type == 'accessories':
            key_accs = f_id
        elif f_type == 'images' or any(k in lbl for k in ['foto', 'imagen', 'fotos', 'imagenes']):
            if not key_fotos:
                key_fotos = f_id
        elif not key_cantidad and any(k in lbl for k in ['cantidad', 'cant', 'unidades', 'stock', 'qty']):
            key_cantidad = f_id
        elif not key_nombre and f_type in ['text', 'select'] and any(k in lbl for k in ['nombre', 'modelo', 'equipo', 'título', 'titulo', 'completo', 'responsable', 'colaborador', 'receptor']):
            key_nombre = f_id
        elif not key_serial and any(k in lbl for k in ['serial', 's/n', 'placa']):
            key_serial = f_id
            lbl_serial = lbl
        elif not key_categoria and any(k in lbl for k in ['categoría', 'categoria', 'tipo', 'área', 'area', 'cargo', 'rol', 'puesto']):
            key_categoria = f_id
        elif not key_estado and any(k in lbl for k in ['estado', 'condicion', 'condición', 'status']):
            key_estado = f_id
        elif not key_cantidad and f_type == 'number' and not es_modulo_personal:
            key_cantidad = f_id
            
    # Fallback si no detectó key_nombre: primer campo de texto o número que no sea imagen/accesorio
    if not key_nombre:
        for f_idx, field in enumerate(fields):
            if field.get('type') in ['text']:
                key_nombre = field.get('key', f"field_{f_idx}")
                break
    if not key_nombre:
        for f_idx, field in enumerate(fields):
            if field.get('type') in ['number', 'select']:
                key_nombre = field.get('key', f"field_{f_idx}")
                break
                
    detalles = {}
    for reg in records:
        data = reg.get('data', {})
        raw_nom = data.get(key_nombre, '') if key_nombre else ""
        if isinstance(raw_nom, list):
            val_nom = ", ".join([str(x) for x in raw_nom if x])
        else:
            val_nom = str(raw_nom).strip() if raw_nom is not None else ""
        if not val_nom:
            val_nom = f"Registro #{reg['id']}"
            
        val_ser = str(data.get(key_serial, '')).strip() if key_serial else ""
        val_cat = str(data.get(key_categoria, '')).strip() if key_categoria else ""
        val_est = str(data.get(key_estado, '')).strip() if key_estado else ""
        val_correo = str(data.get(key_correo, '')).strip() if key_correo else ""
        val_tel = str(data.get(key_telefono, '')).strip() if key_telefono else ""
        val_rol = str(data.get(key_rol, '')).strip() if key_rol else ""
        val_ced = str(data.get(key_cedula, '')).strip() if key_cedula else ""
        
        es_persona_item = es_modulo_personal or bool(val_correo or val_tel or (key_rol and val_rol))
        
        # Cantidad: SOLO para inventario/equipos, NUNCA para personal
        if es_persona_item:
            val_cant = None
        else:
            raw_cant = data.get(key_cantidad) if key_cantidad else None
            val_cant = None
            if raw_cant is not None and str(raw_cant).strip() != "":
                try:
                    f = float(raw_cant)
                    val_cant = int(f) if f.is_integer() else f
                except (ValueError, TypeError):
                    val_cant = str(raw_cant).strip()
            else:
                val_cant = 1
                
        # Fotos
        raw_fotos = data.get(key_fotos) if key_fotos else None
        val_fotos = []
        if raw_fotos:
            if isinstance(raw_fotos, list):
                val_fotos = [f for f in raw_fotos if f]
            elif isinstance(raw_fotos, str) and raw_fotos.strip():
                val_fotos = [raw_fotos.strip()]
        
        # Fallback de fotos si no se encontró en key_fotos
        if not val_fotos:
            for k, v in data.items():
                if isinstance(v, list) and v and isinstance(v[0], str) and ('data:image' in v[0] or v[0].startswith('http')):
                    val_fotos = [f for f in v if f]
                    break
                elif isinstance(v, str) and ('data:image' in v or v.startswith('http')):
                    val_fotos = [v.strip()]
                    break
                
        partes = [val_nom]
        if es_persona_item:
            rol_mostrar = val_rol or val_cat
            if rol_mostrar:
                partes.append(f"[{rol_mostrar}]")
            if val_ced:
                partes.append(f"(C.C.: {val_ced})")
            if val_correo:
                partes.append(f"• {val_correo}")
            if val_tel:
                partes.append(f"• Tel: {val_tel}")
        else:
            if val_ser:
                partes.append(f"(S/N: {val_ser})")
            if val_cat:
                partes.append(f"[{val_cat}]")
            if val_cant is not None:
                partes.append(f"• Cant: {val_cant}")
            
        etiqueta_principal = " ".join(partes)
        item_key = f"rec_{reg['id']}"
        detalles[item_key] = {
            'id': item_key,
            'nombre': val_nom,
            'serial': val_ser,
            'categoria': val_cat or val_rol,
            'cantidad': val_cant,
            'fotos': val_fotos,
            'estado': val_est,
            'correo': val_correo,
            'telefono': val_tel,
            'celular': val_tel,
            'rol': val_rol or val_cat,
            'cedula': val_ced,
            'es_persona': es_persona_item,
            'label': etiqueta_principal,
            'data': data
        }
        
        # Sub-equipos / accesorios dentro del ítem (ej. cargador dentro de kit o equipo de inventario)
        accs = data.get(key_accs) if key_accs else None
        if accs and isinstance(accs, list):
            for idx_a, acc in enumerate(accs):
                if isinstance(acc, dict):
                    a_nom = str(acc.get('nombre', '')).strip()
                    if not a_nom:
                        continue
                    a_ser = str(acc.get('serial', '')).strip()
                    a_cat = str(acc.get('categoria', '')).strip()
                    a_est = str(acc.get('estado', '')).strip()
                    
                    raw_a_cant = acc.get('cantidad')
                    a_cant = None
                    if raw_a_cant is not None and str(raw_a_cant).strip() != "":
                        try:
                            f = float(raw_a_cant)
                            a_cant = int(f) if f.is_integer() else f
                        except (ValueError, TypeError):
                            a_cant = str(raw_a_cant).strip()
                    else:
                        a_cant = 1
                            
                    a_foto_raw = acc.get('foto') or acc.get('fotos') or acc.get('imagen')
                    a_fotos = []
                    if isinstance(a_foto_raw, list):
                        a_fotos = [f for f in a_foto_raw if f]
                    elif isinstance(a_foto_raw, str) and a_foto_raw.strip():
                        a_fotos = [a_foto_raw.strip()]
                    
                    a_partes = [a_nom]
                    if a_ser:
                        a_partes.append(f"(S/N: {a_ser})")
                    if a_cat:
                        a_partes.append(f"[{a_cat}]")
                    if a_cant is not None:
                        a_partes.append(f"• Cant: {a_cant}")
                    a_partes.append(f"— Acc. de {val_nom}")
                    
                    sub_key = f"acc_{reg['id']}_{idx_a}"
                    detalles[sub_key] = {
                        'id': sub_key,
                        'nombre': a_nom,
                        'serial': a_ser,
                        'categoria': a_cat,
                        'cantidad': a_cant,
                        'fotos': a_fotos,
                        'estado': a_est,
                        'label': " ".join(a_partes),
                        'data': acc
                    }
                    
    return detalles

def obtener_opciones_modulo_vinculado(target_module_id: str) -> dict:
    """
    Obtiene las opciones disponibles de una gestión vinculada en formato {id_item: etiqueta_legible}.
    Soporta tanto registros principales como accesorios/sub-equipos desglosados (ej. kits de inventario).
    """
    detalles = obtener_detalles_modulo_vinculado(target_module_id)
    return {k: v['label'] for k, v in detalles.items()}

# ==============================================================================
# FUNCIONES CRUD PARA AUTORIZACIONES DE RETRANSMISIÓN (MINTIC / RTI / GERENCIA)
# ==============================================================================

def create_retransmission_authorization(data: dict) -> int:
    """Inserta una nueva solicitud de autorización de retransmisión."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO retransmission_authorizations (
            code, operator_name, nit, rti_number, rep_name, rep_doc,
            channel_target, municipality, department, address, notification_email,
            status, created_by, created_at, file_rti_path, file_camara_path, file_cedula_path,
            ocr_data_json, match_results_json, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('code'),
        data.get('operator_name'),
        data.get('nit'),
        data.get('rti_number'),
        data.get('rep_name'),
        data.get('rep_doc'),
        data.get('channel_target', 'Canal Teleamiga'),
        data.get('municipality', ''),
        data.get('department', ''),
        data.get('address', ''),
        data.get('notification_email', ''),
        data.get('status', 'pendiente_revision'),
        data.get('created_by'),
        data.get('created_at'),
        data.get('file_rti_path', ''),
        data.get('file_camara_path', ''),
        data.get('file_cedula_path', ''),
        json.dumps(data.get('ocr_data', {})),
        json.dumps(data.get('match_results', {})),
        data.get('notes', '')
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_all_retransmission_authorizations() -> list[dict]:
    """Retorna todas las solicitudes de retransmisión ordenadas de la más reciente a la más antigua."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM retransmission_authorizations ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d['ocr_data'] = json.loads(d.get('ocr_data_json') or '{}')
        d['match_results'] = json.loads(d.get('match_results_json') or '{}')
        res.append(d)
    return res

def get_retransmission_authorization_by_id(auth_id: int) -> dict:
    """Obtiene un expediente de retransmisión por su ID."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM retransmission_authorizations WHERE id = ?', (auth_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['ocr_data'] = json.loads(d.get('ocr_data_json') or '{}')
    d['match_results'] = json.loads(d.get('match_results_json') or '{}')
    return d

def update_retransmission_status(auth_id: int, status: str, approved_by: str = None, 
                                 approved_at: str = None, signature_b64: str = None, notes: str = None):
    """Actualiza el estado de aprobación, firma y notas de un expediente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE retransmission_authorizations 
        SET status = ?,
            approved_by = COALESCE(?, approved_by),
            approved_at = COALESCE(?, approved_at),
            signature_img_b64 = COALESCE(?, signature_img_b64),
            notes = COALESCE(?, notes)
        WHERE id = ?
    ''', (status, approved_by, approved_at, signature_b64, notes, auth_id))
    conn.commit()
    conn.close()

def delete_retransmission_authorization(auth_id: int):
    """Elimina un expediente de autorización de retransmisión."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM retransmission_authorizations WHERE id = ?', (auth_id,))
    conn.commit()
    conn.close()


# ==============================================================================
# MÓDULO DE ENCUESTAS INTERNAS (CANAL TELEAMIGA)
# ==============================================================================

def seed_teleamiga_survey(cursor):
    """Inicializa la encuesta interna oficial de Teleamiga si no existe."""
    try:
        from components.survey_data import get_teleamiga_survey_data
        data = get_teleamiga_survey_data()
        cursor.execute("SELECT id FROM surveys WHERE code = ?", (data['code'],))
        row = cursor.fetchone()
        questions_payload = json.dumps({
            'sections': data['sections'],
            'questions': data['questions']
        }, ensure_ascii=False)
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not row:
            cursor.execute('''
                INSERT INTO surveys (code, title, description, questions_json, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            ''', (data['code'], data['title'], data['description'], questions_payload, now))
        else:
            # Mantener actualizada la definición de preguntas si cambia
            cursor.execute('''
                UPDATE surveys 
                SET title = ?, description = ?, questions_json = ?, active = 1 
                WHERE code = ?
            ''', (data['title'], data['description'], questions_payload, data['code']))
    except Exception as e:
        print(f"Error seeding teleamiga survey: {e}")

def get_active_survey(code: str = 'teleamiga_interna_2026') -> dict:
    """Obtiene la encuesta activa según su código."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM surveys WHERE code = ? AND active = 1', (code,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        payload = json.loads(d.get('questions_json') or '{}')
        d['sections'] = payload.get('sections', [])
        d['questions'] = payload.get('questions', [])
    except Exception:
        d['sections'] = []
        d['questions'] = []
    return d

def get_user_survey_response(survey_id: int, user_id: int) -> dict:
    """Obtiene la respuesta (o borrador) de un usuario para una encuesta."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM survey_responses WHERE survey_id = ? AND user_id = ?', (survey_id, user_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['responses'] = json.loads(d.get('responses_json') or '{}')
    except Exception:
        d['responses'] = {}
    return d

def save_survey_response(survey_id: int, user_info: dict, responses_dict: dict, is_draft: bool = False) -> bool:
    """Guarda o actualiza las respuestas de la encuesta (borrador o envío definitivo)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = user_info.get('id')
    username = user_info.get('usuario', '')
    user_name = f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}".strip()
    user_cargo = user_info.get('cargo', '')
    user_area = user_info.get('area') or user_info.get('area_encargada', '')
    responses_json = json.dumps(responses_dict, ensure_ascii=False)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    draft_val = 1 if is_draft else 0
    
    try:
        cursor.execute('''
            INSERT INTO survey_responses (
                survey_id, user_id, username, user_name, user_cargo, user_area, 
                responses_json, is_draft, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(survey_id, user_id) DO UPDATE SET
                responses_json = excluded.responses_json,
                is_draft = excluded.is_draft,
                submitted_at = excluded.submitted_at,
                user_cargo = excluded.user_cargo,
                user_area = excluded.user_area,
                user_name = excluded.user_name
        ''', (survey_id, user_id, username, user_name, user_cargo, user_area, responses_json, draft_val, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving survey response: {e}")
        conn.close()
        return False

def get_pending_surveys_for_user(user_id: int) -> list:
    """
    Retorna la lista de encuestas activas que el usuario NO ha completado definitivamente.
    Si el usuario tiene un borrador (is_draft=1) o no ha respondido nada, la encuesta está pendiente.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.code, s.title, s.description, s.created_at,
               sr.is_draft, sr.submitted_at
        FROM surveys s
        LEFT JOIN survey_responses sr ON s.id = sr.survey_id AND sr.user_id = ?
        WHERE s.active = 1 AND (sr.id IS NULL OR sr.is_draft = 1)
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_survey_responses(survey_id: int) -> list:
    """Retorna todas las respuestas definitivas enviadas para una encuesta."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM survey_responses 
        WHERE survey_id = ? AND is_draft = 0 
        ORDER BY submitted_at DESC
    ''', (survey_id,))
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        try:
            d['responses'] = json.loads(d.get('responses_json') or '{}')
        except Exception:
            d['responses'] = {}
        res.append(d)
    return res

def get_survey_stats(survey_id: int) -> dict:
    """Calcula estadísticas consolidadas de las respuestas para gerencia y sistemas."""
    responses = get_all_survey_responses(survey_id)
    survey = get_active_survey()
    questions = survey.get('questions', []) if survey else []
    
    total = len(responses)
    by_area = {}
    by_cargo = {}
    question_stats = {}
    
    # Inicializar contadores por pregunta
    for q in questions:
        q_id = q['id']
        q_type = q['type']
        if q_type in ('multiple_choice', 'single_choice'):
            opt_counts = {opt: 0 for opt in q.get('options', [])}
            if q.get('has_other'):
                opt_counts['Otra / Otro'] = 0
            question_stats[q_id] = {
                'type': q_type,
                'counts': opt_counts,
                'other_texts': []
            }
        elif q_type == 'ranking':
            question_stats[q_id] = {
                'type': q_type,
                'options': q.get('options', []),
                'ranking_scores': {opt: [] for opt in q.get('options', [])}
            }
        else: # open_text
            question_stats[q_id] = {
                'type': 'open_text',
                'texts': []
            }
            
    for resp in responses:
        area = resp.get('user_area') or 'Sin Área'
        cargo = resp.get('user_cargo') or 'General'
        by_area[area] = by_area.get(area, 0) + 1
        by_cargo[cargo] = by_cargo.get(cargo, 0) + 1
        
        user_answers = resp.get('responses', {})
        for q in questions:
            q_id = q['id']
            ans = user_answers.get(q_id)
            if not ans:
                continue
                
            q_stat = question_stats.get(q_id)
            if not q_stat:
                continue
                
            if q['type'] == 'multiple_choice':
                selected = ans if isinstance(ans, list) else [ans]
                other_val = user_answers.get(f"{q_id}_other")
                for s in selected:
                    if s in q_stat['counts']:
                        q_stat['counts'][s] += 1
                if other_val:
                    q_stat['counts']['Otra / Otro'] = q_stat['counts'].get('Otra / Otro', 0) + 1
                    q_stat['other_texts'].append({'user': resp['user_name'], 'area': area, 'text': other_val})
            elif q['type'] == 'single_choice':
                if ans in q_stat['counts']:
                    q_stat['counts'][ans] += 1
            elif q['type'] == 'ranking':
                if isinstance(ans, dict):
                    for opt, rank in ans.items():
                        if opt in q_stat['ranking_scores']:
                            try:
                                q_stat['ranking_scores'][opt].append(int(rank))
                            except Exception:
                                pass
            elif q['type'] == 'open_text':
                if str(ans).strip():
                    q_stat['texts'].append({
                        'user': resp['user_name'],
                        'area': area,
                        'cargo': cargo,
                        'text': str(ans).strip()
                    })
                    
    # Promediar rankings
    for q_id, q_stat in question_stats.items():
        if q_stat['type'] == 'ranking':
            avg_ranks = {}
            for opt, scores in q_stat['ranking_scores'].items():
                avg = sum(scores) / len(scores) if scores else 0
                avg_ranks[opt] = round(avg, 2)
            q_stat['avg_ranks'] = avg_ranks

    return {
        'total_responses': total,
        'by_area': by_area,
        'by_cargo': by_cargo,
        'questions': question_stats,
        'raw_responses': responses
    }

def export_survey_to_excel(survey_id: int, output_path: str = None) -> str:
    """Genera un archivo Excel (.xlsx) con todas las respuestas y estadísticas de la encuesta."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    survey = get_active_survey()
    responses = get_all_survey_responses(survey_id)
    questions = survey.get('questions', []) if survey else []
    
    if not output_path:
        out_dir = os.path.join(BASE_DIR, 'uploads', 'reportes_encuesta')
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(out_dir, f"Encuesta_Teleamiga_{timestamp}.xlsx")
        
    wb = openpyxl.Workbook()
    
    # -------------------------------------------------------------
    # HOJA 1: MATRIZ COMPLETA DE RESPUESTAS
    # -------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Respuestas Detalladas"
    
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    border_thin = Border(left=Side(style='thin', color='CBD5E1'),
                         right=Side(style='thin', color='CBD5E1'),
                         top=Side(style='thin', color='CBD5E1'),
                         bottom=Side(style='thin', color='CBD5E1'))
                         
    headers = ["#", "Fecha Envío", "Usuario", "Colaborador", "Cargo", "Área"]
    for q in questions:
        headers.append(f"P{q['number']}: {q['question']}")
        if q.get('has_other'):
            headers.append(f"P{q['number']} - Detalle Otro/Otra")
            
    ws1.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws1.row_dimensions[1].height = 45
    
    for r_idx, resp in enumerate(responses, start=1):
        answers = resp.get('responses', {})
        row_vals = [
            r_idx,
            resp.get('submitted_at', ''),
            resp.get('username', ''),
            resp.get('user_name', ''),
            resp.get('user_cargo', ''),
            resp.get('user_area', '')
        ]
        for q in questions:
            q_id = q['id']
            ans = answers.get(q_id, '')
            if isinstance(ans, list):
                val_str = ", ".join(str(x) for x in ans)
            elif isinstance(ans, dict):
                # Para rankings
                val_str = "; ".join(f"{k}: Lugar {v}" for k, v in ans.items())
            else:
                val_str = str(ans) if ans is not None else ""
            row_vals.append(val_str)
            
            if q.get('has_other'):
                other_val = answers.get(f"{q_id}_other", "")
                row_vals.append(str(other_val) if other_val else "")
                
        ws1.append(row_vals)
        cur_row = ws1.max_row
        for col_idx in range(1, len(row_vals) + 1):
            c = ws1.cell(row=cur_row, column=col_idx)
            c.font = data_font
            c.border = border_thin
            if col_idx in (1, 2):
                c.alignment = Alignment(horizontal="center", vertical="top")
            else:
                c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                
    # Autoajuste de anchos de columna
    for col in ws1.columns:
        col_letter = col[0].column_letter
        ws1.column_dimensions[col_letter].width = 24
    ws1.column_dimensions['A'].width = 6
    ws1.column_dimensions['B'].width = 19
    ws1.column_dimensions['D'].width = 26
    
    # -------------------------------------------------------------
    # HOJA 2: RESUMEN EJECUTIVO Y PARTICIPACIÓN
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Resumen Ejecutivo")
    stats = get_survey_stats(survey_id)
    
    title_font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    subtitle_font = Font(name="Calibri", size=11, bold=True, color="334155")
    sub_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    
    ws2.cell(row=1, column=1, value="RESUMEN EJECUTIVO - ENCUESTA INTERNA TELEAMIGA").font = title_font
    ws2.cell(row=2, column=1, value=f"Total de respuestas recibidas: {stats['total_responses']} colaboradores").font = subtitle_font
    
    ws2.cell(row=4, column=1, value="Participación por Área").font = subtitle_font
    ws2.cell(row=5, column=1, value="Área").fill = sub_fill
    ws2.cell(row=5, column=2, value="Respuestas").fill = sub_fill
    ws2.cell(row=5, column=3, value="% del Total").fill = sub_fill
    
    cur = 6
    for area, cnt in stats.get('by_area', {}).items():
        pct = (cnt / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
        ws2.cell(row=cur, column=1, value=area)
        ws2.cell(row=cur, column=2, value=cnt)
        ws2.cell(row=cur, column=3, value=f"{pct:.1f}%")
        cur += 1
        
    cur += 2
    ws2.cell(row=cur, column=1, value="Resultados Clave de Programación").font = subtitle_font
    cur += 1
    
    for q in questions:
        if q['type'] in ('multiple_choice', 'single_choice'):
            q_id = q['id']
            q_stat = stats['questions'].get(q_id, {})
            ws2.cell(row=cur, column=1, value=f"P{q['number']}: {q['question']}").font = Font(name="Calibri", size=11, bold=True)
            cur += 1
            ws2.cell(row=cur, column=1, value="Opción").fill = sub_fill
            ws2.cell(row=cur, column=2, value="Votos").fill = sub_fill
            ws2.cell(row=cur, column=3, value="%").fill = sub_fill
            cur += 1
            
            sorted_counts = sorted(q_stat.get('counts', {}).items(), key=lambda x: x[1], reverse=True)
            for opt, cnt in sorted_counts:
                pct = (cnt / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
                ws2.cell(row=cur, column=1, value=opt)
                ws2.cell(row=cur, column=2, value=cnt)
                ws2.cell(row=cur, column=3, value=f"{pct:.1f}%")
                cur += 1
            cur += 1
            
    ws2.column_dimensions['A'].width = 45
    ws2.column_dimensions['B'].width = 16
    ws2.column_dimensions['C'].width = 16
    
    wb.save(output_path)
    return output_path


# --- FUNCIONES DE ACTAS DE ENTREGA DE EQUIPOS Y FIRMAS VIRTUALES ---

def archivar_acta_en_entrega_equipos(acta: dict, sel_rec_ids: list = None, staff_id: str = None) -> tuple[bool, str]:
    """
    Registra o sincroniza automáticamente el acta de entrega en el módulo de 'Entrega de equipos' (custom_mod_1788804389).
    Vincula:
    - EQUIPO: Lista de IDs de equipos en inventario (formato ['rec_XXX'])
    - Encargado: ID de personal en system_staff (formato 'rec_YYY')
    - Descripcion: Folio oficial, equipo, serial, responsable y estado actual de firmas.
    """
    if not acta:
        return False, "Datos de acta inválidos."
        
    code = acta.get('code')
    if not code:
        return False, "El acta no posee código oficial."

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Localizar el módulo de Entrega de equipos
    cursor.execute("SELECT id, config_json FROM custom_modules WHERE id = 'custom_mod_1788804389'")
    mod_row = cursor.fetchone()
    if not mod_row:
        cursor.execute("SELECT id, config_json FROM custom_modules WHERE LOWER(nombre) LIKE '%entrega%' AND LOWER(nombre) LIKE '%equipo%'")
        mod_row = cursor.fetchone()
        
    if not mod_row:
        conn.close()
        return False, "No se encontró el módulo de 'Entrega de equipos'."
        
    mod_id = mod_row[0]
    try:
        fields = json.loads(mod_row[1])
    except Exception:
        fields = []
        
    field_equipo = None
    field_encargado = None
    field_desc = None
    
    for f in fields:
        f_key = f.get('key') or f.get('id')
        lbl = (f.get('label') or '').lower()
        lmod = f.get('linked_module_id')
        if lmod == 'system_inventory' or 'equipo' in lbl:
            field_equipo = f_key
        elif lmod == 'system_staff' or 'encargad' in lbl or 'responsable' in lbl:
            field_encargado = f_key
        elif f.get('type') == 'text' or 'descrip' in lbl:
            field_desc = f_key
            
    # Fallback predeterminado a las claves conocidas de custom_mod_1788804389
    if not field_equipo:
        field_equipo = 'field_1788804343990'
    if not field_encargado:
        field_encargado = 'field_1788804585154'
    if not field_desc:
        field_desc = 'field_1788804603960'
        
    # 2. Armar lista de equipos vinculados
    equipos_list = []
    if sel_rec_ids:
        for x in sel_rec_ids:
            clean_id = str(x).replace('rec_', '').strip()
            if clean_id:
                equipos_list.append(f"rec_{clean_id}")
    elif acta.get('record_id'):
        clean_rid = str(acta['record_id']).replace('rec_', '').strip()
        if clean_rid and clean_rid != '0':
            equipos_list.append(f"rec_{clean_rid}")
        
    # 3. Armar ID de Encargado (system_staff)
    encargado_val = None
    target_staff = staff_id or acta.get('receptor_id')
    if target_staff:
        clean_sid = str(target_staff).replace('rec_', '').strip()
        if clean_sid.isdigit():
            encargado_val = f"rec_{clean_sid}"
            
    # Si no se tiene un ID numérico de staff, buscar en system_staff por correo o nombre
    if not encargado_val:
        rec_correo = (acta.get('receptor_correo') or '').strip().lower()
        rec_nombre = (acta.get('receptor_nombre') or '').strip().lower()
        cursor.execute("SELECT id, data_json FROM custom_module_records WHERE module_id = 'system_staff'")
        staff_rows = cursor.fetchall()
        for s_id, s_json in staff_rows:
            try:
                s_data = json.loads(s_json)
                s_vals = [str(v).lower() for v in s_data.values()]
                if rec_correo and any(rec_correo == v for v in s_vals):
                    encargado_val = f"rec_{s_id}"
                    break
                if rec_nombre and any(rec_nombre in v for v in s_vals):
                    encargado_val = f"rec_{s_id}"
                    break
            except Exception:
                pass

    # 4. Armar descripción con estado del acta
    estado = acta.get('estado', 'pendiente_firma')
    if estado == 'completada':
        estado_label = "TOTALMENTE LEGALIZADA Y FIRMADA ✓"
    elif estado == 'firmado_receptor':
        estado_label = "FIRMADA POR RECEPTOR (Falta Ingeniería) ✍️"
    elif estado == 'firmado_ingenieria':
        estado_label = "FIRMADA POR INGENIERÍA (Falta Receptor) ✍️"
    else:
        estado_label = "PENDIENTE DE FIRMAS DIGITALES ⏳"
        
    eq_nom = acta.get('equipo_nombre') or 'Equipo de Inventario'
    eq_ser = acta.get('serial') or 'S/N'
    rec_nom = acta.get('receptor_nombre') or 'Colaborador'
    desc_str = f"Acta Oficial {code} | {eq_nom} (Serial: {eq_ser}) asignado a {rec_nom}. Estado: {estado_label}"
    
    # 5. Buscar si ya existe un registro en custom_mod_1788804389 con este código/folio
    cursor.execute("SELECT id, data_json FROM custom_module_records WHERE module_id = ?", (mod_id,))
    rows = cursor.fetchall()
    record_id_existente = None
    data_dict_existente = {}
    
    for r_id, r_json in rows:
        try:
            d_parsed = json.loads(r_json)
            desc_val = str(d_parsed.get(field_desc, ''))
            if code in desc_val:
                record_id_existente = r_id
                data_dict_existente = d_parsed
                break
        except Exception:
            pass
            
    if record_id_existente:
        # Actualizar registro existente
        data_dict_existente[field_desc] = desc_str
        if equipos_list:
            data_dict_existente[field_equipo] = equipos_list
        if encargado_val:
            data_dict_existente[field_encargado] = encargado_val
            
        cursor.execute("UPDATE custom_module_records SET data_json = ? WHERE id = ?",
                       (json.dumps(data_dict_existente), record_id_existente))
        conn.commit()
        conn.close()
        return True, f"Registro de entrega {code} actualizado en 'Entrega de equipos'."
    else:
        # Crear nuevo registro archivado
        nuevo_registro = {
            field_equipo: equipos_list,
            field_encargado: encargado_val or "",
            field_desc: desc_str
        }
        cursor.execute("INSERT INTO custom_module_records (module_id, data_json) VALUES (?, ?)",
                       (mod_id, json.dumps(nuevo_registro)))
        conn.commit()
        conn.close()
        return True, f"Acta {code} archivada con éxito en la gestión de 'Entrega de equipos'."

def create_or_update_delivery_act(act_data: dict = None, force_new: bool = False, reset_firmas: bool = False, **kwargs) -> tuple[bool, str, dict]:
    """
    Crea o actualiza un acta formal de entrega de equipo con soporte para firmas virtuales.
    Si force_new=True, ignora actas previas y emite un nuevo folio limpio listo para firmar.
    Si reset_firmas=True, blanquea las firmas del acta existente y la retorna a estado pendiente.
    Archiva y sincroniza automáticamente en la gestión de 'Entrega de equipos'.
    """
    data = dict(act_data or {})
    data.update(kwargs)
    
    if data.get('emitido_por') and not data.get('emisor_nombre'):
        data['emisor_nombre'] = data['emitido_por']
        
    detalles = data.get('detalles_equipos')
    if detalles and isinstance(detalles, list) and len(detalles) > 0:
        if not data.get('equipo_nombre'):
            data['equipo_nombre'] = ", ".join([e.get('nombre', 'Equipo') for e in detalles])
        if not data.get('serial'):
            seriales = [e.get('serial') for e in detalles if e.get('serial') and e.get('serial') != 'S/N']
            data['serial'] = ", ".join(seriales) if seriales else 'S/N'

    act_data = data
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    
    code = act_data.get('code')
    record_id = act_data.get('record_id')
    module_id = act_data.get('module_id', 'system_inventory')
    
    # Buscar si ya existe por código o por record_id solo si NO estamos forzando emisión nueva
    existing = None
    if not force_new:
        if code:
            cursor.execute("SELECT * FROM equipment_delivery_acts WHERE code = ?", (code,))
            existing = cursor.fetchone()
        if not existing and record_id:
            cursor.execute("SELECT * FROM equipment_delivery_acts WHERE record_id = ? AND module_id = ? ORDER BY id DESC LIMIT 1", (record_id, module_id))
            existing = cursor.fetchone()
        
    if existing and not force_new:
        act_id = existing['id']
        if reset_firmas:
            f_rec = None
            f_rec_f = None
            f_emi = None
            f_emi_f = None
            estado = 'pendiente_firma'
        else:
            # Preservar firmas existentes si no se envían nuevas
            f_rec = act_data.get('firma_receptor_b64', existing['firma_receptor_b64'])
            f_rec_f = act_data.get('firma_receptor_fecha', existing['firma_receptor_fecha'])
            f_emi = act_data.get('firma_emisor_b64', existing['firma_emisor_b64'])
            f_emi_f = act_data.get('firma_emisor_fecha', existing['firma_emisor_fecha'])
            
            # Calcular estado
            estado = act_data.get('estado')
            if not estado:
                if f_rec and f_emi:
                    estado = 'completada'
                elif f_rec:
                    estado = 'firmado_receptor'
                elif f_emi:
                    estado = 'firmado_ingenieria'
                else:
                    estado = existing['estado'] or 'pendiente_firma'
                
        cursor.execute('''
            UPDATE equipment_delivery_acts SET
                equipo_nombre = ?,
                serial = ?,
                receptor_id = ?,
                receptor_nombre = ?,
                receptor_correo = ?,
                receptor_cargo = ?,
                emisor_usuario = ?,
                emisor_nombre = ?,
                emisor_cargo = ?,
                estado = ?,
                firma_receptor_b64 = ?,
                firma_receptor_fecha = ?,
                firma_emisor_b64 = ?,
                firma_emisor_fecha = ?,
                layout_config = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            act_data.get('equipo_nombre', existing['equipo_nombre']),
            act_data.get('serial', existing['serial']),
            act_data.get('receptor_id', existing['receptor_id']),
            act_data.get('receptor_nombre', existing['receptor_nombre']),
            act_data.get('receptor_correo', existing['receptor_correo']),
            act_data.get('receptor_cargo', existing['receptor_cargo']),
            act_data.get('emisor_usuario', existing['emisor_usuario']),
            act_data.get('emisor_nombre', existing['emisor_nombre']),
            act_data.get('emisor_cargo', existing['emisor_cargo']),
            estado,
            f_rec, f_rec_f,
            f_emi, f_emi_f,
            json.dumps(act_data.get('layout_config', {})) if isinstance(act_data.get('layout_config'), dict) else (act_data.get('layout_config') or existing['layout_config']),
            now_str,
            act_id
        ))
        conn.commit()
        cursor.execute("SELECT * FROM equipment_delivery_acts WHERE id = ?", (act_id,))
        updated_row = dict(cursor.fetchone())
        conn.close()
        
        # Archivar / sincronizar automáticamente en 'Entrega de equipos'
        det_ids = [e.get('id') for e in detalles] if (detalles and isinstance(detalles, list)) else ([record_id] if record_id else [])
        archivar_acta_en_entrega_equipos(updated_row, sel_rec_ids=det_ids, staff_id=act_data.get('receptor_id'))
        
        return True, "Acta de entrega actualizada correctamente.", updated_row
    else:
        new_code = (code if (code and not force_new) else None) or f"ACT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        f_rec = None if force_new else act_data.get('firma_receptor_b64')
        f_rec_f = None if force_new else act_data.get('firma_receptor_fecha')
        f_emi = None if force_new else act_data.get('firma_emisor_b64')
        f_emi_f = None if force_new else act_data.get('firma_emisor_fecha')
        
        estado = act_data.get('estado')
        if not estado or force_new:
            if f_rec and f_emi:
                estado = 'completada'
            elif f_rec:
                estado = 'firmado_receptor'
            elif f_emi:
                estado = 'firmado_ingenieria'
            else:
                estado = 'pendiente_firma'
                
        layout_cfg_str = json.dumps(act_data.get('layout_config', {})) if isinstance(act_data.get('layout_config'), dict) else (act_data.get('layout_config') or '{}')
        
        cursor.execute('''
            INSERT INTO equipment_delivery_acts (
                code, record_id, module_id, equipo_nombre, serial,
                receptor_id, receptor_nombre, receptor_correo, receptor_cargo,
                emisor_usuario, emisor_nombre, emisor_cargo,
                estado, firma_receptor_b64, firma_receptor_fecha,
                firma_emisor_b64, firma_emisor_fecha, layout_config,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_code,
            record_id or 0,
            module_id,
            act_data.get('equipo_nombre', 'Equipo de Inventario'),
            act_data.get('serial', ''),
            act_data.get('receptor_id', ''),
            act_data.get('receptor_nombre', 'Colaborador'),
            act_data.get('receptor_correo', ''),
            act_data.get('receptor_cargo', ''),
            act_data.get('emisor_usuario', ''),
            act_data.get('emisor_nombre', 'Departamento de Ingeniería'),
            act_data.get('emisor_cargo', 'Ingeniería y Sistemas'),
            estado,
            f_rec, f_rec_f,
            f_emi, f_emi_f,
            layout_cfg_str,
            now_str, now_str
        ))
        act_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT * FROM equipment_delivery_acts WHERE id = ?", (act_id,))
        created_row = dict(cursor.fetchone())
        conn.close()
        
        # Archivar / sincronizar automáticamente en 'Entrega de equipos'
        det_ids = [e.get('id') for e in detalles] if (detalles and isinstance(detalles, list)) else ([record_id] if record_id else [])
        archivar_acta_en_entrega_equipos(created_row, sel_rec_ids=det_ids, staff_id=act_data.get('receptor_id'))
        
        return True, "Acta virtual emitida exitosamente.", created_row

def get_delivery_act_by_code(code: str) -> dict | None:
    """Obtiene un acta de entrega por su código único oficial."""
    if not code:
        return None
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment_delivery_acts WHERE code = ?", (code.strip(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get('layout_config'):
        try:
            d['layout_config'] = json.loads(d['layout_config'])
        except Exception:
            pass
    return d

def get_delivery_act_by_record(record_id: int, module_id: str = 'system_inventory') -> dict | None:
    """Obtiene el acta de entrega más reciente asociada a un registro de equipo."""
    if not record_id:
        return None
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment_delivery_acts WHERE record_id = ? AND module_id = ? ORDER BY id DESC LIMIT 1", (record_id, module_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get('layout_config'):
        try:
            d['layout_config'] = json.loads(d['layout_config'])
        except Exception:
            pass
    return d

def sign_delivery_act(act_code: str, role: str, signature_b64: str, signer_name: str = None) -> tuple[bool, str, dict]:
    """Estampa la firma virtual (del receptor o de ingeniería) en el acta oficial y actualiza el archivo en Entrega de Equipos."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment_delivery_acts WHERE code = ?", (act_code.strip(),))
    act = cursor.fetchone()
    if not act:
        conn.close()
        return False, "Acta no encontrada.", {}
        
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if role == 'receptor':
        f_rec = signature_b64
        f_rec_f = now_str
        f_emi = act['firma_emisor_b64']
        f_emi_f = act['firma_emisor_fecha']
        nuevo_nom = signer_name or act['receptor_nombre']
        cursor.execute('''
            UPDATE equipment_delivery_acts SET
                firma_receptor_b64 = ?,
                firma_receptor_fecha = ?,
                receptor_nombre = ?,
                updated_at = ?
            WHERE id = ?
        ''', (f_rec, f_rec_f, nuevo_nom, datetime.now().isoformat(), act['id']))
    elif role == 'emisor':
        f_rec = act['firma_receptor_b64']
        f_rec_f = act['firma_receptor_fecha']
        f_emi = signature_b64
        f_emi_f = now_str
        nuevo_nom = signer_name or act['emisor_nombre']
        cursor.execute('''
            UPDATE equipment_delivery_acts SET
                firma_emisor_b64 = ?,
                firma_emisor_fecha = ?,
                emisor_nombre = ?,
                updated_at = ?
            WHERE id = ?
        ''', (f_emi, f_emi_f, nuevo_nom, datetime.now().isoformat(), act['id']))
    else:
        conn.close()
        return False, "Rol de firma inválido (debe ser 'receptor' o 'emisor').", {}
        
    # Recalcular estado
    if f_rec and f_emi:
        nuevo_estado = 'completada'
    elif f_rec:
        nuevo_estado = 'firmado_receptor'
    elif f_emi:
        nuevo_estado = 'firmado_ingenieria'
    else:
        nuevo_estado = 'pendiente_firma'
        
    cursor.execute("UPDATE equipment_delivery_acts SET estado = ? WHERE id = ?", (nuevo_estado, act['id']))
    conn.commit()
    cursor.execute("SELECT * FROM equipment_delivery_acts WHERE id = ?", (act['id'],))
    updated_act = dict(cursor.fetchone())
    conn.close()
    
    # Sincronizar automáticamente el estado en el módulo de Entrega de Equipos
    try:
        archivar_acta_en_entrega_equipos(updated_act)
    except Exception as e:
        print(f"[Acta Delivery] Error al sincronizar archivo en Entrega de Equipos: {e}")
        
    return True, f"Firma registrada correctamente.", updated_act

def get_pending_delivery_acts_for_user(user_info: dict) -> list:
    """
    Retorna la lista de actas pendientes de firma para el usuario logueado:
    - Como RECEPTOR: Si el acta está dirigida a su correo o nombre y no ha firmado.
    - Como INGENIERÍA: Si el usuario pertenece a Ingeniería/Sistemas y falta firma de Ingeniería.
    """
    if not user_info:
        return []
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    user_correo = (user_info.get('correo') or '').strip().lower()
    user_nom_comp = (user_info.get('nombre_completo') or f"{user_info.get('nombres', '')} {user_info.get('apellidos', '')}").strip().lower()
    user_nombres = (user_info.get('nombres') or '').strip().lower()
    user_usuario = (user_info.get('usuario') or '').strip().lower()
    user_area = (user_info.get('area') or user_info.get('area_encargada') or '').strip().lower()
    user_cargo = (user_info.get('cargo') or '').strip().lower()
    es_ingenieria = any(k in user_area or k in user_cargo or k in user_usuario or k in user_nom_comp for k in ['ingenieria', 'ingeniería', 'sistemas', 'admin', 'jose', 'zhayrus'])
    
    def normalizar_palabras(s):
        s = unicodedata.normalize('NFKD', str(s or '')).encode('ASCII', 'ignore').decode('utf-8').lower()
        return set(re.findall(r'[a-z0-9]+', s))

    u_tokens = normalizar_palabras(user_nom_comp)
    if user_usuario:
        u_tokens.add(user_usuario)

    actas_pendientes = []
    
    # 1. Buscar actas pendientes como receptor
    cursor.execute('''
        SELECT * FROM equipment_delivery_acts 
        WHERE (firma_receptor_b64 IS NULL OR firma_receptor_b64 = '')
        AND estado != 'completada'
        ORDER BY id DESC
    ''')
    for r in cursor.fetchall():
        d = dict(r)
        rec_correo = (d.get('receptor_correo') or '').strip().lower()
        rec_nom = (d.get('receptor_nombre') or '').strip().lower()
        
        # Coincidencia por correo, nombre completo o tokens compartidos
        coincide = False
        if user_correo and rec_correo and user_correo == rec_correo:
            coincide = True
        elif user_nom_comp and rec_nom and (user_nom_comp in rec_nom or rec_nom in user_nom_comp):
            coincide = True
        elif user_nombres and rec_nom and (user_nombres in rec_nom):
            coincide = True
        else:
            r_tokens = normalizar_palabras(rec_nom)
            comunes = u_tokens.intersection(r_tokens)
            if len(comunes) >= 2 or (len(u_tokens) == 1 and u_tokens.issubset(r_tokens)):
                coincide = True
            
        if coincide:
            d['tipo_tramite'] = 'firma_receptor'
            d['mensaje_notif'] = f"Acta de Entrega: {d['equipo_nombre']}"
            actas_pendientes.append(d)

    # 2. Si es de Ingeniería, buscar actas pendientes de firma del emisor
    if es_ingenieria:
        cursor.execute('''
            SELECT * FROM equipment_delivery_acts 
            WHERE (firma_emisor_b64 IS NULL OR firma_emisor_b64 = '')
            AND estado != 'completada'
            ORDER BY id DESC
        ''')
        for r in cursor.fetchall():
            d = dict(r)
            if not any(a['id'] == d['id'] for a in actas_pendientes):
                d['tipo_tramite'] = 'firma_ingenieria'
                d['mensaje_notif'] = f"Pendiente firma Ingeniería: {d['equipo_nombre']} ({d['receptor_nombre']})"
                actas_pendientes.append(d)

    conn.close()
    return actas_pendientes

def get_all_delivery_acts(module_id: str = 'system_inventory', limit: int = 100) -> list:
    """Retorna las actas de entrega para consulta o listado general."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if module_id:
        cursor.execute("SELECT * FROM equipment_delivery_acts WHERE module_id = ? ORDER BY id DESC LIMIT ?", (module_id, limit))
    else:
        cursor.execute("SELECT * FROM equipment_delivery_acts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
