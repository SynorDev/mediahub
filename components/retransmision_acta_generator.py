import re
from nicegui import ui
from datetime import datetime
from database import get_system_logo, get_acta_retransmision_template, get_all_users

DIAS_LETRAS = {
    1: 'un (01)', 2: 'dos (02)', 3: 'tres (03)', 4: 'cuatro (04)', 5: 'cinco (05)',
    6: 'seis (06)', 7: 'siete (07)', 8: 'ocho (08)', 9: 'nueve (09)', 10: 'diez (10)',
    11: 'once (11)', 12: 'doce (12)', 13: 'trece (13)', 14: 'catorce (14)', 15: 'quince (15)',
    16: 'dieciséis (16)', 17: 'diecisiete (17)', 18: 'dieciocho (18)', 19: 'diecinueve (19)',
    20: 'veinte (20)', 21: 'veintiún (21)', 22: 'veintidós (22)', 23: 'veintitrés (23)',
    24: 'veinticuatro (24)', 25: 'veinticinco (25)', 26: 'veintiséis (26)', 27: 'veintisiete (27)',
    28: 'veintiocho (28)', 29: 'veintinueve (29)', 30: 'treinta (30)', 31: 'treinta y un (31)'
}

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

YEARS_ES = {
    2024: "dos mil veinticuatro (2024)",
    2025: "dos mil veinticinco (2025)",
    2026: "dos mil veintiséis (2026)",
    2027: "dos mil veintisiete (2027)",
    2028: "dos mil veintiocho (2028)",
    2029: "dos mil veintinueve (2029)",
    2030: "dos mil treinta (2030)",
}

def obtener_fecha_legal_acta(fecha_iso: str = None) -> str:
    """
    Genera la fecha en el formato legal exacto estipulado en las actas de Teleamiga:
    Ejemplo: 'veintinueve (29) días del mes de septiembre del año dos mil veintiséis (2026)'
    """
    try:
        dt = datetime.fromisoformat(fecha_iso) if fecha_iso else datetime.now()
    except Exception:
        dt = datetime.now()

    d_txt = DIAS_LETRAS.get(dt.day, f"({dt.day})")
    m_txt = MESES_ES[dt.month - 1]
    y_txt = YEARS_ES.get(dt.year, f"{dt.year}")
    return f"{d_txt} días del mes de {m_txt} del año {y_txt}"


def formatear_texto_plantilla(texto: str, variables: dict) -> str:
    """Reemplaza de forma segura las variables {clave} sin fallar si hay llaves extra."""
    if not texto:
        return ""
    res = str(texto)
    for k, v in variables.items():
        if isinstance(v, (str, int, float)):
            res = res.replace(f"{{{k}}}", str(v))
    return res


def markdown_inline_to_html(texto: str) -> str:
    """Convierte marcas básicas de Markdown (**negrita**) a etiquetas HTML para impresión."""
    if not texto:
        return ""
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', str(texto))


def obtener_datos_acta(expediente: dict, user_info: dict = None) -> dict:
    """
    Consolida y normaliza todos los campos requeridos para la visualización e impresión
    del Acta Oficial de Autorización de Retransmisión a partir de la plantilla configurable.
    """
    tpl = get_acta_retransmision_template()
    fecha_emision_legal = obtener_fecha_legal_acta(expediente.get('approved_at') or expediente.get('created_at'))
    logo_actual = get_system_logo()
    
    op_name = (expediente.get('operator_name') or 'OPERADOR DE TELECOMUNICACIONES').upper()
    op_nit = expediente.get('nit') or 'N/A'
    op_address = expediente.get('address') or 'CR 73 BIS 49 A 29'
    municipio = (expediente.get('municipality') or 'BOGOTÁ D.C.').upper()
    departamento = (expediente.get('department') or 'BOGOTÁ D.C.').upper()
    rep_name = (expediente.get('rep_name') or 'REPRESENTANTE LEGAL').upper()
    rep_doc = expediente.get('rep_doc') or 'N/A'
    notif_email = expediente.get('notification_email') or f"notificaciones@{op_name.lower().replace(' ', '')[:8]}.com.co"
    codigo_acta = expediente.get('code') or 'AUT-RET-OFICIAL'
    firma_b64 = expediente.get('signature_img_b64')
    esta_aprobado = expediente.get('status') == 'aprobado_gerencia'

    # Determinación dinámica del usuario autorizado de la categoría Gerencia
    aprobado_por = expediente.get('approved_by')
    u_gerencia = None
    try:
        all_users = get_all_users()
        # 1. Si el expediente ya fue aprobado, buscar el registro del usuario que aprobó
        if aprobado_por:
            aprob_clean = aprobado_por.strip().lower()
            for u in all_users:
                if (u.get('nombre_completo') or '').strip().lower() == aprob_clean or \
                   (u.get('usuario') or '').strip().lower() == aprob_clean:
                    u_gerencia = u
                    break
        
        # 2. Si el usuario actual en sesión pertenece a Gerencia / Dirección / Admin
        if not u_gerencia and user_info:
            area_u = (user_info.get('area') or '').lower()
            cargo_u = (user_info.get('cargo') or '').lower()
            if any(k in area_u or k in cargo_u for k in ['gerencia', 'gerente', 'director']):
                u_gerencia = user_info
        
        # 3. Si aún no se identifica, buscar cualquier usuario activo en categoría/área Gerencia
        if not u_gerencia:
            for u in all_users:
                area_u = (u.get('area_encargada') or '').lower()
                cargo_u = (u.get('cargo') or '').lower()
                if 'gerencia' in area_u or 'gerente' in cargo_u:
                    u_gerencia = u
                    break
    except Exception:
        pass

    if u_gerencia:
        nom = u_gerencia.get('nombre_completo') or f"{u_gerencia.get('nombres', '')} {u_gerencia.get('apellidos', '')}".strip() or u_gerencia.get('usuario', '')
        gerente_nombre = nom or aprobado_por or 'Claudia Garzon'
        gerente_cargo = u_gerencia.get('cargo') or tpl.get('cargo_firmante') or 'Gerente del Canal'
        cel = u_gerencia.get('celular')
        gerente_cel = cel if cel and cel != '00000000000' else (tpl.get('celular_firmante') or '3138932021')
    elif aprobado_por:
        gerente_nombre = aprobado_por.strip()
        gerente_cargo = tpl.get('cargo_firmante') or 'Gerente del Canal'
        gerente_cel = tpl.get('celular_firmante') or '3138932021'
    else:
        gerente_nombre = tpl.get('nombre_firmante') or 'Claudia Garzon'
        if '{gerente_nombre}' in gerente_nombre or '{usuario_autorizado}' in gerente_nombre:
            gerente_nombre = 'Claudia Garzon'
        gerente_cargo = tpl.get('cargo_firmante') or 'Gerente del Canal'
        gerente_cel = tpl.get('celular_firmante') or '3138932021'

    periodo_vigencia = tpl.get('periodo_vigencia') or 'un (1) año'

    d = {
        'auth_id': expediente.get('id'),
        'fecha_emision_legal': fecha_emision_legal,
        'fecha_legal': fecha_emision_legal,
        'periodo_vigencia': periodo_vigencia,
        'logo_actual': logo_actual,
        'op_name': op_name,
        'op_nit': op_nit,
        'op_address': op_address,
        'municipio': municipio,
        'departamento': departamento,
        'rep_name': rep_name,
        'rep_doc': rep_doc,
        'notif_email': notif_email,
        'codigo_acta': codigo_acta,
        'firma_b64': firma_b64,
        'esta_aprobado': esta_aprobado,
        'gerente_nombre': gerente_nombre,
        'gerente_nombre_upper': gerente_nombre.upper(),
        'usuario_autorizado': gerente_nombre,
        'usuario_gerencia': gerente_nombre,
        'gerente_cargo': gerente_cargo,
        'cargo_gerencia': gerente_cargo,
        'gerente_cel': gerente_cel,
        'tpl': tpl,
    }

    # Renderizado dinámico de los textos configurados con variables
    d['rendered_titulo'] = formatear_texto_plantilla(tpl.get('titulo', ''), d)
    d['rendered_entidad'] = formatear_texto_plantilla(tpl.get('entidad', ''), d)
    d['rendered_nit_entidad'] = formatear_texto_plantilla(tpl.get('nit_entidad', ''), d)
    d['rendered_texto_apertura'] = formatear_texto_plantilla(tpl.get('texto_apertura', ''), d)
    d['rendered_clausula_cabeceras'] = formatear_texto_plantilla(tpl.get('clausula_cabeceras', ''), d)
    d['rendered_clausula_vigencia'] = formatear_texto_plantilla(tpl.get('clausula_vigencia', ''), d)
    d['rendered_clausula_tecnica'] = formatear_texto_plantilla(tpl.get('clausula_tecnica', ''), d)
    d['rendered_despedida'] = formatear_texto_plantilla(tpl.get('despedida', ''), d)
    d['rendered_pie_pagina'] = formatear_texto_plantilla(tpl.get('pie_pagina', ''), d)

    return d


def generate_acta_html(expediente: dict, user_info: dict = None, auto_print: bool = False) -> str:
    """
    Genera el HTML puro, autónomo e impecable para exportación e impresión de la
    Autorización de Retransmisión exactamente en tamaño Carta físico (Letter).
    """
    d = obtener_datos_acta(expediente, user_info)
    
    logo_tag = f'<img src="{d["logo_actual"]}" class="logo-img" alt="Canal Teleamiga" />' if d["logo_actual"] else \
               '<div style="font-weight:900; font-size:18px; color:#0f172a; margin-bottom:15px;">CANAL TELEAMIGA</div>'

    firma_tag = f'<img src="{d["firma_b64"]}" class="sig-img" alt="Firma Digital" />' if d["firma_b64"] else \
                '<div class="sig-placeholder">PENDIENTE FIRMA DIGITAL</div>'

    auto_print_js = """
    <script>
        window.addEventListener('load', function() {
            setTimeout(function() {
                window.print();
            }, 300);
        });
    </script>
    """ if auto_print else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acta Oficial de Autorización - {d['codigo_acta']}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: letter portrait;
            margin: 14mm 18mm 14mm 18mm;
        }}
        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f1f5f9;
            color: #0f172a;
            font-size: 12px;
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
        }}
        .screen-nav {{
            position: sticky;
            top: 0;
            left: 0;
            right: 0;
            background: #ffffff;
            border-bottom: 1px solid #cbd5e1;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            z-index: 1000;
        }}
        .screen-nav .nav-info {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .screen-nav .badge {{
            background: #eef2ff;
            color: #4338ca;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 9999px;
            border: 1px solid #c7d2fe;
        }}
        .screen-nav .actions {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .screen-nav .btn-print {{
            background: #4f46e5;
            color: #ffffff;
            border: none;
            padding: 8px 18px;
            border-radius: 10px;
            font-size: 12.5px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(79, 70, 229, 0.25);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .screen-nav .btn-print:hover {{
            background: #4338ca;
        }}
        .sheet-wrapper {{
            padding: 24px 16px 48px 16px;
            display: flex;
            justify-content: center;
        }}
        .letter-page {{
            width: 100%;
            max-width: 816px;
            min-height: 1056px;
            background: #ffffff;
            padding: 44px 60px 32px 60px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .logo-img {{
            max-width: 175px;
            max-height: 60px;
            object-fit: contain;
            margin-bottom: 18px;
        }}
        .title-block {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .title-block h1 {{
            font-size: 14.5px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 0 0 3px 0;
            color: #0f172a;
        }}
        .title-block h2 {{
            font-size: 13px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 0 0 2px 0;
            color: #0f172a;
        }}
        .title-block h3 {{
            font-size: 11.5px;
            font-weight: 700;
            margin: 0;
            color: #334155;
            letter-spacing: 0.3px;
        }}
        .p-legal {{
            text-align: justify;
            margin: 0 0 16px 0;
            color: #1e293b;
            font-size: 12px;
            line-height: 1.6;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0 0 18px 20px;
            font-size: 12px;
        }}
        .data-table td {{
            padding: 2px 0;
            vertical-align: top;
        }}
        .data-table td.lbl {{
            width: 275px;
            font-weight: 700;
            color: #1e293b;
        }}
        .data-table td.val {{
            font-weight: 600;
            color: #0f172a;
        }}
        .data-table td.val-mono {{
            font-family: 'Courier New', Courier, monospace;
            font-weight: 600;
        }}
        .p-term {{
            text-align: justify;
            margin: 0 0 13px 0;
            color: #1e293b;
            font-size: 12px;
            line-height: 1.6;
        }}
        .signature-block {{
            margin-top: 20px;
            width: 260px;
        }}
        .sig-img {{
            max-height: 70px;
            max-width: 250px;
            object-fit: contain;
            object-position: left bottom;
            margin-bottom: 2px;
            display: block;
        }}
        .sig-line {{
            width: 220px;
            border-bottom: 1px solid #1e293b;
            margin-bottom: 6px;
        }}
        .sig-placeholder {{
            height: 48px;
            width: 220px;
            border-bottom: 1px dashed #94a3b8;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            font-family: monospace;
            color: #94a3b8;
            letter-spacing: 1px;
            margin-bottom: 6px;
        }}
        .sig-name {{
            font-size: 12px;
            font-weight: 900;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .sig-cargo {{
            font-size: 11px;
            color: #334155;
            font-weight: 500;
        }}
        .sig-cel {{
            font-size: 10px;
            color: #64748b;
            font-family: monospace;
            margin-top: 1px;
        }}
        .footer-block {{
            margin-top: auto;
            padding-top: 12px;
            border-top: 1px solid #cbd5e1;
            font-size: 9px;
            color: #94a3b8;
            font-family: monospace;
            display: flex;
            justify-content: space-between;
        }}
        @media print {{
            body {{
                background: #ffffff !important;
            }}
            .screen-nav {{
                display: none !important;
            }}
            .sheet-wrapper {{
                padding: 0 !important;
                margin: 0 !important;
                display: block !important;
            }}
            .letter-page {{
                width: 100% !important;
                max-width: 100% !important;
                min-height: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                box-shadow: none !important;
                border: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="screen-nav">
        <div class="nav-info">
            <span style="font-weight:800; font-size:14px; color:#1e1b4b;">MediaHub</span>
            <span style="color:#94a3b8;">•</span>
            <span style="font-weight:600; font-size:13px; color:#334155;">Acta Oficial de Autorización</span>
            <span class="badge">{d['codigo_acta']}</span>
        </div>
        <div class="actions">
            <button class="btn-print" onclick="window.print()">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                Imprimir / Guardar como PDF
            </button>
        </div>
    </div>

    <div class="sheet-wrapper">
        <div class="letter-page">
            <div>
                {logo_tag}

                <div class="title-block">
                    <h1>{d['rendered_titulo']}</h1>
                    <h2>{d['rendered_entidad']}</h2>
                    <h3>{d['rendered_nit_entidad']}</h3>
                </div>

                <p class="p-legal">
                    {markdown_inline_to_html(d['rendered_texto_apertura'])}
                </p>

                <table class="data-table">
                    <tr><td class="lbl">Nombre o Razón Social:</td><td class="val">{d['op_name']}</td></tr>
                    <tr><td class="lbl">NIT-Número Identificación Tributaria:</td><td class="val val-mono">{d['op_nit']}</td></tr>
                    <tr><td class="lbl">Dirección:</td><td class="val">{d['op_address']}</td></tr>
                    <tr><td class="lbl">Municipio:</td><td class="val">{d['municipio']}</td></tr>
                    <tr><td class="lbl">Departamento:</td><td class="val">{d['departamento']}</td></tr>
                    <tr><td class="lbl">País:</td><td class="val">COLOMBIA</td></tr>
                    <tr><td class="lbl">Representante Legal:</td><td class="val">{d['rep_name']}</td></tr>
                    <tr><td class="lbl">Documento de Identidad No:</td><td class="val val-mono">{d['rep_doc']}</td></tr>
                    <tr><td class="lbl">Datos de Notificación:</td><td class="val">{d['notif_email']}</td></tr>
                </table>

                <p class="p-term">{markdown_inline_to_html(d['rendered_clausula_cabeceras'])}</p>
                <p class="p-term">{markdown_inline_to_html(d['rendered_clausula_vigencia'])}</p>
                <p class="p-term">{markdown_inline_to_html(d['rendered_clausula_tecnica'])}</p>
                <p style="margin: 0 0 16px 0; color: #1e293b; font-size: 12px;">{d['rendered_despedida']}</p>

                <div class="signature-block">
                    {firma_tag}
                    <div class="sig-line"></div>
                    <div class="sig-name">{d['gerente_nombre_upper']}</div>
                    <div class="sig-cargo">{d['gerente_cargo']}</div>
                    <div class="sig-cel">CEL: {d['gerente_cel']}</div>
                </div>
            </div>

            <div class="footer-block">
                <span>{d['rendered_pie_pagina']}</span>
                <span>Página 1 de 1</span>
            </div>
        </div>
    </div>

    {auto_print_js}
</body>
</html>"""


def render_acta_retransmision_preview(container, expediente: dict, user_info: dict = None, on_download_pdf=None):
    """
    Renderiza el Acta Formal de Autorización de Retransmisión idéntica a la plantilla
    oficial de FUNDACIÓN ICTUS / CANAL TELEAMIGA ('AUTORIZACION DE RETRANSMISION CABLEMAS SAS vf.pdf'),
    optimizada para hoja Carta física (Letter max 816px x 1056px), responsiva verticalmente y con firma de Gerencia.
    """
    container.clear()
    d = obtener_datos_acta(expediente, user_info)
    auth_id = d['auth_id']

    with container:
        with ui.column().classes('w-full flex flex-col items-center py-4 px-2 sm:px-4 bg-slate-100 overflow-x-hidden'):
            
            # 1. Barra de Herramientas de la Hoja
            with ui.row().classes('w-full max-w-[816px] justify-between items-center bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 mb-6 shrink-0 flex-wrap gap-3'):
                with ui.row().classes('items-center gap-2.5'):
                    with ui.element('div').classes('w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600'):
                        ui.icon('verified', size='xs')
                    with ui.column().classes('gap-0'):
                        ui.label(f"Acta Oficial de Autorización ({d['codigo_acta']})").classes('font-bold text-slate-800 text-sm')
                        ui.label(f"Operador: {d['op_name']} • {'FIRMADA POR GERENCIA' if d['esta_aprobado'] else 'PENDIENTE DE FIRMA'}").classes('text-[11px] text-slate-500')
                
                with ui.row().classes('items-center gap-2'):
                    def ejecutar_impresion_limpia():
                        ui.run_javascript(f"""
                            (function() {{
                                let old = document.getElementById('acta_print_iframe');
                                if (old) old.remove();
                                const iframe = document.createElement('iframe');
                                iframe.id = 'acta_print_iframe';
                                iframe.style.position = 'fixed';
                                iframe.style.right = '0';
                                iframe.style.bottom = '0';
                                iframe.style.width = '0';
                                iframe.style.height = '0';
                                iframe.style.border = '0';
                                iframe.src = '/acta/imprimir/{auth_id}?auto_print=1';
                                document.body.appendChild(iframe);
                            }})();
                        """)

                    ui.button('Imprimir Documento', icon='print', on_click=ejecutar_impresion_limpia)\
                        .classes('bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded-xl text-xs shadow-sm transition-all')

                    ui.button('Abrir en Pestaña Nueva', icon='open_in_new', on_click=lambda: ui.navigate.to(f'/acta/imprimir/{auth_id}', new_tab=True))\
                        .props('outline color=indigo-7 size=sm').classes('px-3 rounded-xl text-xs font-semibold')

            # 2. HOJA CARTA FÍSICA INSTITUCIONAL (Letter: max 816px x 1056px)
            with ui.column().classes('bg-white shadow-xl w-full max-w-[816px] min-h-[1056px] px-8 sm:px-16 pt-12 pb-12 relative flex flex-col justify-between box-border border border-slate-300 text-slate-900 mx-auto'):
                
                with ui.column().classes('w-full flex-grow flex flex-col justify-start min-h-0'):
                    
                    # LOGOTIPO SUPERIOR TELEAMIGA / ICTUS
                    with ui.row().classes('w-full justify-start items-center mb-6'):
                        if d['logo_actual']:
                            ui.image(d['logo_actual']).props('fit=contain').classes('w-44 h-16 object-contain')
                        else:
                            with ui.row().classes('items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-300 bg-slate-50'):
                                ui.icon('tv', size='md').classes('text-indigo-600')
                                with ui.column().classes('gap-0'):
                                    ui.label('CANAL TELEAMIGA').classes('text-base font-black tracking-wider text-slate-900')
                                    ui.label('TELEVISIÓN CON VALORES').classes('text-[8px] font-bold text-slate-500 tracking-widest uppercase')

                    # TÍTULO FORMAL DEL ACTA
                    with ui.column().classes('w-full items-center text-center gap-0.5 mb-8'):
                        ui.label(d['rendered_titulo']).classes('text-base font-black tracking-wide text-slate-900 uppercase')
                        ui.label(d['rendered_entidad']).classes('text-sm font-black tracking-wide text-slate-900 uppercase')
                        ui.label(d['rendered_nit_entidad']).classes('text-xs font-bold text-slate-800 tracking-wider')

                    # PÁRRAFO DE PERSONERÍA JURÍDICA Y APERTURA LEGAL
                    ui.markdown(d['rendered_texto_apertura']).classes('text-[12px] text-justify leading-relaxed text-slate-800 mb-6')

                    # BLOQUE CON LOS DATOS FORMALES DEL OPERADOR AUTORIZADO
                    with ui.column().classes('w-full pl-6 pr-4 gap-2 mb-6 text-[12px] text-slate-900 leading-normal'):
                        with ui.row().classes('gap-1'):
                            ui.label('Nombre o Razón Social:').classes('font-bold text-slate-800')
                            ui.label(d['op_name']).classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('NIT-Número Identificación Tributaria:').classes('font-bold text-slate-800')
                            ui.label(d['op_nit']).classes('font-mono font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Dirección:').classes('font-bold text-slate-800')
                            ui.label(d['op_address']).classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Municipio:').classes('font-bold text-slate-800')
                            ui.label(d['municipio']).classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Departamento:').classes('font-bold text-slate-800')
                            ui.label(d['departamento']).classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('País:').classes('font-bold text-slate-800')
                            ui.label('COLOMBIA').classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Representante Legal:').classes('font-bold text-slate-800')
                            ui.label(d['rep_name']).classes('font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Documento de Identidad No:').classes('font-bold text-slate-800')
                            ui.label(d['rep_doc']).classes('font-mono font-semibold')
                        
                        with ui.row().classes('gap-1'):
                            ui.label('Datos de Notificación:').classes('font-bold text-slate-800')
                            ui.label(d['notif_email']).classes('font-semibold text-slate-700')

                    # TÉRMINOS Y CONDICIONES CONFIGURABLES
                    ui.markdown(d['rendered_clausula_cabeceras'])\
                        .classes('text-[12px] text-justify leading-relaxed text-slate-800 mb-4')

                    ui.markdown(d['rendered_clausula_vigencia'])\
                        .classes('text-[12px] text-justify leading-relaxed text-slate-800 mb-4')

                    ui.markdown(d['rendered_clausula_tecnica'])\
                        .classes('text-[12px] text-justify leading-relaxed text-slate-800 mb-8')

                    ui.label(d['rendered_despedida']).classes('text-[12px] text-slate-800 mb-2')

                    # ESPACIO DE FIRMA DIGITAL DE GERENCIA
                    with ui.column().classes('mt-2 w-72 items-start'):
                        if d['firma_b64']:
                            ui.image(d['firma_b64']).props('fit=contain position="left"').classes('h-20 w-64 object-contain mb-1')
                        else:
                            with ui.element('div').classes('h-16 w-60 border-b border-dashed border-slate-400 flex items-center justify-center mb-1'):
                                ui.label('PENDIENTE FIRMA DIGITAL').classes('text-[9px] font-mono text-slate-400 tracking-wider')

                        ui.label(d['gerente_nombre_upper']).classes('text-[12px] font-black text-slate-900 tracking-wide')
                        ui.label(d['gerente_cargo']).classes('text-[11px] text-slate-700 font-medium')
                        if d['gerente_cel']:
                            ui.label(f"CEL: {d['gerente_cel']}").classes('text-[10px] text-slate-600 font-mono')

                # PIE DE PÁGINA DISCRETO DE SEGURIDAD
                with ui.row().classes('w-full justify-between items-center border-t border-slate-200 pt-3 text-[9px] text-slate-400 shrink-0 font-mono'):
                    ui.label(d['rendered_pie_pagina'])
                    ui.label('Página 1 de 1')
