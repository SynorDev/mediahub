import os
from nicegui import ui, app
from fastapi.responses import HTMLResponse, FileResponse
from database import init_db, get_retransmission_authorization_by_id
from components.retransmision_acta_generator import generate_acta_html
from pages.login import login_page
from pages.register import register_page
from pages.home import home_page
from pages.admin_panel import admin_page
from pages.reportes_inventario import reportes_inventario_page
from pages.herramientas import herramientas_page
from pages.retransmision_form import retransmision_page
from pages.survey_view import survey_page, survey_results_page
from pages.render_edicion import render_edicion_page
from pages.acta_entrega_virtual import render_acta_entrega_virtual_page

# Asegura que la base de datos y tablas existan antes de levantar la interfaz
init_db()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================================================================
# CONFIGURACIÓN PWA PARA MEDIAHUB (ESCRITORIO Y MÓVIL)
# =========================================================================
pwa_static_dir = os.path.join(BASE_DIR, 'static', 'pwa')
if os.path.exists(pwa_static_dir):
    app.add_static_files('/static/pwa', pwa_static_dir)

@app.get('/manifest.json')
def get_pwa_manifest():
    manifest_file = os.path.join(BASE_DIR, 'static', 'pwa', 'manifest.json')
    if os.path.exists(manifest_file):
        return FileResponse(manifest_file, media_type='application/manifest+json')
    return HTMLResponse('{}', status_code=404)

@app.get('/sw.js')
def get_pwa_service_worker():
    sw_file = os.path.join(BASE_DIR, 'static', 'pwa', 'sw.js')
    if os.path.exists(sw_file):
        return FileResponse(sw_file, media_type='application/javascript', headers={'Service-Worker-Allowed': '/'})
    return HTMLResponse('', status_code=404)

@app.get('/offline', response_class=HTMLResponse)
def get_pwa_offline_page():
    return HTMLResponse('''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MediaHub - Sin Conexión</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
    .card { background: #1e293b; padding: 32px; border-radius: 16px; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    h1 { margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
    p { color: #94a3b8; font-size: 0.95rem; }
    button { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>MediaHub Desconectado</h1>
    <p>No se pudo conectar con el servidor local de MediaHub. La conexión se restablecerá automáticamente apenas el servidor esté disponible.</p>
    <button onclick="window.location.reload()">Reintentar Conexión</button>
  </div>
</body>
</html>''')

# Inyección global de PWA Head tags y registro de Service Worker en todas las páginas de NiceGUI
ui.add_head_html('''
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#2563eb">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="MediaHub">
<link rel="apple-touch-icon" href="/static/pwa/icon-192.png">
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(reg => console.log('[PWA] MediaHub Service Worker activo:', reg.scope))
        .catch(err => console.warn('[PWA] Error al registrar Service Worker:', err));
    });
  }
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    window.deferredPWAInstallPrompt = e;
    window.dispatchEvent(new CustomEvent('pwa-ready-to-install'));
  });
</script>
''', shared=True)

@app.get('/acta/imprimir/{auth_id}', response_class=HTMLResponse)
def imprimir_acta_documento(auth_id: int, auto_print: int = 0):
    expediente = get_retransmission_authorization_by_id(auth_id)
    if not expediente:
        return HTMLResponse('<h3>Expediente de retransmisión no encontrado.</h3>', status_code=404)
    return HTMLResponse(generate_acta_html(expediente, auto_print=bool(auto_print)))

@app.get('/descargar_reporte_encuesta/{filename}')
def descargar_reporte_encuesta(filename: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'uploads', 'reportes_encuesta', filename)
    if not os.path.exists(file_path):
        return HTMLResponse('<h3>Archivo no encontrado</h3>', status_code=404)
    return FileResponse(file_path, filename=filename, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/descargar-cliente-edicion')
def descargar_cliente_edicion():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'uploads', 'clients', 'MediaHub_Cliente_Render_Edicion.zip')
    if not os.path.exists(file_path):
        return HTMLResponse('<h3>Paquete de instalación no encontrado. Contacte al área de Sistemas.</h3>', status_code=404)
    return FileResponse(file_path, filename='MediaHub_Cliente_Render_Edicion.zip', media_type='application/zip')

@ui.page('/login')
def login():
    login_page()

@ui.page('/register')
def register():
    register_page()

@ui.page('/')
def home():
    home_page()

@ui.page('/admin')
def admin():
    admin_page()

@ui.page('/herramientas')
def herramientas():
    herramientas_page()

@ui.page('/herramientas/encuesta')
def encuesta():
    survey_page()

@ui.page('/herramientas/encuesta/resultados')
def encuesta_resultados():
    survey_results_page()

@ui.page('/herramientas/retransmision')
def retransmision():
    retransmision_page()

@ui.page('/herramientas/render-edicion')
def render_edicion():
    render_edicion_page()

@ui.page('/reportes_inventario/{module_id}')
def reportes_inventario(module_id: str, record_id: str = None):
    reportes_inventario_page(module_id, initial_record_id=record_id)

@ui.page('/acta_entrega/{acta_code}')
def acta_entrega(acta_code: str):
    render_acta_entrega_virtual_page(acta_code)

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(host='0.0.0.0', port=5480, title='MediaHub', storage_secret='clave_secreta_mediahub')