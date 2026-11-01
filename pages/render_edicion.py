import os
from nicegui import ui, app
from components.topbar import topbar
from components.sidebar import sidebar
from database import get_user_by_usuario

def render_edicion_page():
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    # Verificación de permisos: Exclusivo Edición, Postproducción y Administración General (Jose Rafael Cifuentes)
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
    es_edicion = any(k in user_area for k in ['edicion', 'edición', 'postproduccion', 'postproducción']) or any(k in user_cargo for k in ['editor', 'postproductor'])
    es_autorizado = es_admin or es_edicion

    if not es_autorizado:
        ui.notify('Acceso restringido: Esta herramienta es exclusiva para el área de Edición y Postproducción.', type='warning')
        ui.navigate.to('/herramientas')
        return

    ui.query('body').style('background-color: #f8fafc; margin: 0; padding: 0;')

    # Cabecera y Navegación
    topbar(user_info)
    sidebar(user_info)

    with ui.column().classes('w-full min-h-[calc(100vh-65px)] bg-slate-50 text-slate-800 p-4 sm:p-6 md:p-8 lg:p-10'):
        with ui.column().classes('w-full max-w-6xl mx-auto gap-6 sm:gap-8'):

            # --- ENCABEZADO DE PÁGINA ---
            with ui.row().classes('items-center justify-between w-full flex-wrap gap-4 border-b border-slate-200 pb-5'):
                with ui.row().classes('items-center gap-3 sm:gap-4'):
                    ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/herramientas'))\
                        .props('flat round color=grey-7').tooltip('Volver a Herramientas')
                    
                    with ui.element('div').classes('w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-200 shrink-0 text-white'):
                        ui.icon('speed', size='md')
                    
                    with ui.column().classes('gap-0.5'):
                        with ui.row().classes('items-center gap-2'):
                            ui.label('Motor de Renderizado GPU').classes('text-2xl sm:text-3xl font-black tracking-tight text-slate-900')
                            ui.badge('TELEAMIGA EDICIÓN').props('color=violet-1 text-color=violet-9').classes('text-xs font-bold px-2.5 py-1 border border-violet-200')
                        ui.label('Renderizado acelerado por hardware Nvidia NVENC • Sincronización de mosca y cortinilla de cierre.').classes('text-slate-500 text-xs sm:text-sm')

                with ui.row().classes('items-center gap-3'):
                    # Botón de Descarga del Paquete Cliente
                    ui.button('Descargar Cliente (.zip)', icon='download', on_click=lambda: ui.download('/descargar-cliente-edicion'))\
                        .classes('bg-white hover:bg-slate-100 text-indigo-700 border border-indigo-200 font-bold px-4 py-2 rounded-xl text-xs sm:text-sm shadow-xs transition-all')

            # Render HTML interactivo del módulo
            ui.html('''
            <div id="render-app-root" class="w-full flex flex-col gap-6">

                <!-- 1. BANNER DE ESTADO DE CONEXIÓN CON AGENTE LOCAL -->
                <div id="agent-status-banner" class="w-full p-4 sm:p-5 rounded-2xl border transition-all duration-300 flex items-center justify-between flex-wrap gap-4 bg-amber-50 border-amber-200 text-amber-900">
                    <div class="flex items-center gap-3.5">
                        <div id="status-icon-box" class="w-10 h-10 rounded-xl bg-amber-200/80 flex items-center justify-center shrink-0">
                            <span class="material-icons text-amber-700 text-xl" id="status-icon">sync</span>
                        </div>
                        <div>
                            <div class="flex items-center gap-2">
                                <h4 class="font-extrabold text-sm sm:text-base m-0 text-slate-900" id="status-title">Buscando Agente de Renderizado...</h4>
                                <span id="status-badge" class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-200 text-amber-900">CONECTANDO...</span>
                            </div>
                            <p class="text-xs text-slate-600 m-0 mt-0.5" id="status-desc">Comprobando puerto local 18500 en esta estación de trabajo...</p>
                        </div>
                    </div>

                    <div class="flex items-center gap-2 flex-wrap" id="agent-actions">
                        <div class="flex items-center bg-white px-2.5 py-1.5 rounded-xl border border-slate-200 text-xs text-slate-700">
                            <span class="text-slate-400 mr-1 font-semibold">Agente:</span>
                            <input type="text" id="custom-agent-url" value="http://127.0.0.1:18500" class="w-48 font-mono text-xs outline-none bg-transparent" />
                            <button onclick="reconnectWithCustomUrl()" class="ml-1 px-2 py-0.5 bg-slate-100 hover:bg-slate-200 rounded text-[11px] font-bold text-slate-700 cursor-pointer">
                                Conectar
                            </button>
                        </div>
                        <a href="/descargar-cliente-edicion" class="no-underline inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-sm transition-all" id="btn-download-banner">
                            <span class="material-icons text-sm">download</span> Descargar Cliente (.zip)
                        </a>
                    </div>
                </div>

                <!-- 2. GUÍA RÁPIDA DE ONBOARDING (VISIBLE SI ESTÁ DESCONECTADO) -->
                <div id="agent-offline-guide" class="w-full bg-white border border-slate-200 p-6 rounded-3xl shadow-xs">
                    <div class="flex items-center gap-2 mb-3">
                        <span class="material-icons text-indigo-600">info</span>
                        <h3 class="font-extrabold text-base text-slate-900 m-0">¿Cómo conectar esta estación de trabajo?</h3>
                    </div>
                    <p class="text-xs sm:text-sm text-slate-600 mb-5">
                        El renderizado se procesa con la tarjeta gráfica <strong>NVIDIA Quadro P2000</strong> de esta computadora. Para enlazarla, asegúrate de tener activo el cliente local:
                    </p>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-2">
                            <div class="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 font-black text-xs flex items-center justify-center">1</div>
                            <h5 class="font-bold text-xs sm:text-sm text-slate-900 m-0">Descarga el Paquete</h5>
                            <p class="text-xs text-slate-500 m-0">Descarga <code>MediaHub_Cliente_Render_Edicion.zip</code> con el botón superior.</p>
                            <span class="text-[10px] text-amber-700 bg-amber-50 p-1.5 rounded-lg border border-amber-200">
                                💡 Si tu navegador muestra aviso de "descarga no segura", haz clic en <strong>Conservar / Descargar de todos modos</strong> (es normal por ser red local HTTP).
                            </span>
                        </div>

                        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-2">
                            <div class="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 font-black text-xs flex items-center justify-center">2</div>
                            <h5 class="font-bold text-xs sm:text-sm text-slate-900 m-0">Descomprime en tu PC</h5>
                            <p class="text-xs text-slate-500 m-0">Extrae el ZIP en tu carpeta de trabajo o Escritorio. No requiere instalar Python ni FFmpeg.</p>
                        </div>

                        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-2">
                            <div class="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 font-black text-xs flex items-center justify-center">3</div>
                            <h5 class="font-bold text-xs sm:text-sm text-slate-900 m-0">Ejecuta el Agente</h5>
                            <p class="text-xs text-slate-500 m-0">Haz doble clic en <code>MediaHubRenderAgent.exe</code>. ¡La web se conectará automáticamente en verde!</p>
                        </div>
                    </div>
                </div>

                <!-- 3. FORMULARIO PRINCIPAL DE RENDERIZADO -->
                <div id="render-form-card" class="w-full bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 shadow-sm flex flex-col gap-6 transition-all duration-300">
                    
                    <div class="flex items-center justify-between border-b border-slate-100 pb-4 flex-wrap gap-2">
                        <div class="flex items-center gap-2">
                            <span class="material-icons text-indigo-600">movie_filter</span>
                            <h3 class="font-black text-lg text-slate-900 m-0">Materiales de Edición y Exportación</h3>
                        </div>
                        <div class="flex items-center gap-2 text-xs text-slate-500" id="gpu-chip-pill">
                            <span class="w-2.5 h-2.5 rounded-full bg-slate-400" id="gpu-dot"></span>
                            <span id="gpu-chip-name">Comprobando GPU...</span>
                        </div>
                    </div>

                    <!-- Campos de archivos con botón nativo de Windows -->
                    <div class="grid grid-cols-1 gap-5">
                        
                        <!-- 1. Video Base -->
                        <!-- 1. Video Base -->
                        <div class="flex flex-col gap-1.5">
                            <label class="font-extrabold text-xs text-slate-700 flex items-center gap-1.5">
                                <span class="material-icons text-sm text-indigo-500">videocam</span>
                                1. Video Base Principal (MP4 / MOV)
                                <span class="text-rose-500 font-black">*</span>
                            </label>
                            <div class="flex items-center gap-2">
                                <input type="text" id="input-base-path" placeholder="C:\Proyectos\Programa_Episodio_01.mp4" 
                                    class="w-full px-3.5 py-2.5 text-xs sm:text-sm rounded-xl border border-slate-300 bg-white focus:border-indigo-500 focus:outline-none transition-all font-mono text-slate-800" />
                                <button type="button" id="btn-browse-base" onclick="browseNativeFile('input-base-path', 'Seleccionar Video Base Principal')" 
                                    class="shrink-0 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl border border-slate-200 flex items-center gap-1.5 transition-all cursor-pointer">
                                    <span class="material-icons text-sm text-indigo-600">folder_open</span> Examinar en mi PC
                                </button>
                            </div>
                            <span class="text-[11px] text-slate-400">Ruta del archivo de video grabado o editado en esta estación.</span>
                        </div>

                        <!-- 2. Mosca animada con canal alfa -->
                        <div class="flex flex-col gap-1.5">
                            <label class="font-extrabold text-xs text-slate-700 flex items-center gap-1.5">
                                <span class="material-icons text-sm text-amber-500">animation</span>
                                2. Mosca Animada con Canal Alfa (Bucle con salida fija)
                                <span class="text-rose-500 font-black">*</span>
                            </label>
                            <div class="flex items-center gap-2">
                                <input type="text" id="input-mosca-path" placeholder="C:\Graficos\Mosca_Teleamiga_Animada_Alpha.mov" 
                                    class="w-full px-3.5 py-2.5 text-xs sm:text-sm rounded-xl border border-slate-300 bg-white focus:border-indigo-500 focus:outline-none transition-all font-mono text-slate-800" />
                                <button type="button" id="btn-browse-mosca" onclick="browseNativeFile('input-mosca-path', 'Seleccionar Mosca Animada con Alfa')" 
                                    class="shrink-0 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl border border-slate-200 flex items-center gap-1.5 transition-all cursor-pointer">
                                    <span class="material-icons text-sm text-amber-600">folder_open</span> Examinar en mi PC
                                </button>
                            </div>
                            <span class="text-[11px] text-slate-400">El motor calculará el desfase para que el remate final coincida exactamente con el último frame del video base.</span>
                        </div>

                        <!-- 3. Cortinilla de Cierre -->
                        <div class="flex flex-col gap-1.5">
                            <label class="font-extrabold text-xs text-slate-700 flex items-center gap-1.5">
                                <span class="material-icons text-sm text-purple-500">stop_circle</span>
                                3. Cortinilla de Cierre
                                <span class="text-rose-500 font-black">*</span>
                            </label>
                            <div class="flex items-center gap-2">
                                <input type="text" id="input-cierre-path" placeholder="C:\Graficos\Cortinilla_Cierre_Oficial.mp4" 
                                    class="w-full px-3.5 py-2.5 text-xs sm:text-sm rounded-xl border border-slate-300 bg-white focus:border-indigo-500 focus:outline-none transition-all font-mono text-slate-800" />
                                <button type="button" id="btn-browse-cierre" onclick="browseNativeFile('input-cierre-path', 'Seleccionar Cortinilla de Cierre')" 
                                    class="shrink-0 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl border border-slate-200 flex items-center gap-1.5 transition-all cursor-pointer">
                                    <span class="material-icons text-sm text-purple-600">folder_open</span> Examinar en mi PC
                                </button>
                            </div>
                            <span class="text-[11px] text-slate-400">Se concatenará automáticamente al final tras el remate de la mosca.</span>
                        </div>

                        <!-- 4. Destino de Exportación -->
                        <div class="flex flex-col gap-1.5">
                            <label class="font-extrabold text-xs text-slate-700 flex items-center gap-1.5">
                                <span class="material-icons text-sm text-emerald-500">save</span>
                                4. Archivo de Salida Renderizado
                                <span class="text-rose-500 font-black">*</span>
                            </label>
                            <div class="flex items-center gap-2">
                                <input type="text" id="input-output-path" placeholder="C:\Exportados\Programa_Episodio_01_EMISION.mp4" 
                                    class="w-full px-3.5 py-2.5 text-xs sm:text-sm rounded-xl border border-slate-300 bg-white focus:border-indigo-500 focus:outline-none transition-all font-mono text-slate-800" />
                                <button type="button" id="btn-browse-output" onclick="browseNativeSave('input-output-path', 'Guardar Video Renderizado Como...')" 
                                    class="shrink-0 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl border border-slate-200 flex items-center gap-1.5 transition-all cursor-pointer">
                                    <span class="material-icons text-sm text-emerald-600">save</span> Guardar como...
                                </button>
                            </div>
                            <span class="text-[11px] text-slate-400">Ruta y nombre del archivo MP4 final exportado.</span>
                        </div>

                    </div>

                    <!-- Parámetros avanzados colapsables -->
                    <details class="group bg-slate-50 p-4 rounded-2xl border border-slate-200/80">
                        <summary class="font-bold text-xs text-slate-700 cursor-pointer flex items-center justify-between list-none">
                            <span class="flex items-center gap-1.5">
                                <span class="material-icons text-xs text-indigo-500">tune</span>
                                Parámetros de Codificación NVIDIA (NVENC)
                            </span>
                            <span class="material-icons text-xs text-slate-400 group-open:rotate-180 transition-transform">expand_more</span>
                        </summary>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3 pt-3 border-t border-slate-200/60 text-xs">
                            <div>
                                <label class="font-bold text-slate-600">Preset NVENC:</label>
                                <select id="select-preset" class="w-full mt-1 px-3 py-2 border rounded-xl bg-white text-slate-800">
                                    <option value="p4" selected>p4 - Equilibrado Emisión (Recomendado Quadro P2000)</option>
                                    <option value="p1">p1 - Máxima Velocidad</option>
                                    <option value="p6">p6 - Alta Calidad</option>
                                    <option value="p7">p7 - Máxima Calidad</option>
                                </select>
                            </div>
                            <div>
                                <label class="font-bold text-slate-600">Bitrate Video:</label>
                                <select id="select-bitrate" class="w-full mt-1 px-3 py-2 border rounded-xl bg-white text-slate-800">
                                    <option value="15M" selected>15 Mbps (Estándar Emisión Broadcast)</option>
                                    <option value="10M">10 Mbps (Ligero Web)</option>
                                    <option value="25M">25 Mbps (Alta Fidelidad Master)</option>
                                </select>
                            </div>
                        </div>
                    </details>

                    <!-- Botón de Acción Principal -->
                    <div class="flex items-center justify-between pt-4 border-t border-slate-100 flex-wrap gap-3">
                        <div class="text-xs text-slate-500 flex items-center gap-1.5">
                            <span class="material-icons text-xs text-emerald-600">bolt</span>
                            Renderizado acelerado por hardware NVIDIA en tu estación de edición.
                        </div>
                        <div class="flex items-center gap-3">
                            <button type="button" id="btn-cancel-render" onclick="cancelRender()" class="hidden px-5 py-3 rounded-xl bg-rose-50 text-rose-700 hover:bg-rose-100 font-extrabold text-xs sm:text-sm border border-rose-200 transition-all cursor-pointer">
                                🛑 Cancelar Render
                            </button>
                            <button type="button" id="btn-start-render" onclick="startRender()" class="px-7 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-extrabold text-xs sm:text-sm shadow-md shadow-indigo-200 flex items-center gap-2 transition-all cursor-pointer active:scale-95">
                                <span class="material-icons text-base">rocket_launch</span> Iniciar Renderizado por Hardware
                            </button>
                        </div>
                    </div>

                </div>

                <!-- 4. PANEL DE PROGRESO EN TIEMPO REAL -->
                <div id="render-progress-card" class="w-full bg-white border border-indigo-100 rounded-3xl p-6 sm:p-8 shadow-md flex flex-col gap-6">
                    <div class="flex items-center justify-between flex-wrap gap-2">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                                <span class="material-icons text-lg" id="render-spinner">movie</span>
                            </div>
                            <div>
                                <h3 class="font-black text-base text-slate-900 m-0" id="render-status-title">Monitor de Procesamiento</h3>
                                <p class="text-xs text-slate-500 m-0" id="render-status-subtitle">Listo para iniciar cuando envíes la orden.</p>
                            </div>
                        </div>

                        <div class="text-right">
                            <span class="text-2xl sm:text-3xl font-black text-indigo-600 font-mono" id="progress-percent-label">0.0%</span>
                        </div>
                    </div>

                    <!-- Barra de progreso -->
                    <div class="w-full bg-slate-100 h-4 rounded-full overflow-hidden p-0.5 border border-slate-200">
                        <div id="progress-bar-fill" class="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 h-full rounded-full transition-all duration-300" style="width: 0%;"></div>
                    </div>

                    <!-- Métricas en vivo (KPIs) -->
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-1">
                            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wide">FPS Codificación</span>
                            <span class="font-extrabold text-sm sm:text-base text-slate-800 font-mono" id="metric-fps">0.0 fps</span>
                        </div>
                        <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-1">
                            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Velocidad</span>
                            <span class="font-extrabold text-sm sm:text-base text-indigo-600 font-mono" id="metric-speed">0.0x</span>
                        </div>
                        <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-1">
                            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Tiempo Procesado</span>
                            <span class="font-extrabold text-sm sm:text-base text-slate-800 font-mono" id="metric-time">00:00:00</span>
                        </div>
                        <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col gap-1">
                            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Tiempo Estimado</span>
                            <span class="font-extrabold text-sm sm:text-base text-slate-800 font-mono" id="metric-eta">En espera</span>
                        </div>
                    </div>

                    <!-- Consola de logs colapsable -->
                    <details class="bg-slate-900 rounded-2xl text-slate-200 overflow-hidden" open>
                        <summary class="px-4 py-3 bg-slate-800/80 text-xs font-mono font-bold flex items-center justify-between cursor-pointer select-none">
                            <span class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                Consola de Registro en Tiempo Real
                            </span>
                            <span class="text-[10px] text-slate-400">Clic para colapsar/expandir</span>
                        </summary>
                        <div id="render-console" class="p-4 font-mono text-xs text-slate-300 max-h-56 overflow-y-auto flex flex-col gap-1 leading-relaxed">
                            <div class="text-slate-500">Sistema listo. Selecciona tus clips e inicia el renderizado.</div>
                        </div>
                    </details>
                </div>

            </div>
            ''')

            # JAVASCRIPT DE COMUNICACIÓN CON AGENTE LOCAL
            ui.add_body_html('''
            <script>
                // Detección dinámica de URL del Agente
                let currentAgentUrl = "http://127.0.0.1:18500";
                let currentWsUrl = "ws://127.0.0.1:18500/ws";

                let isAgentOnline = false;
                let socket = null;
                let pollInterval = null;

                function getActiveAgentUrl() {
                    const input = document.getElementById("custom-agent-url");
                    if (input && input.value.trim()) {
                        return input.value.trim().replace(/\\/$/, "");
                    }
                    return currentAgentUrl;
                }

                function reconnectWithCustomUrl() {
                    currentAgentUrl = getActiveAgentUrl();
                    const wsHost = currentAgentUrl.replace(/^http/, "ws");
                    currentWsUrl = `${wsHost}/ws`;
                    appendLog(`🔄 Intentando reconectar con agente en: ${currentAgentUrl}...`, "text-indigo-300");
                    checkAgentHealth();
                }

                function appendLog(msg, colorClass = "text-slate-300") {
                    const consoleEl = document.getElementById("render-console");
                    if (!consoleEl) return;
                    const line = document.createElement("div");
                    line.className = colorClass;
                    line.innerText = msg;
                    consoleEl.appendChild(line);
                    consoleEl.scrollTop = consoleEl.scrollHeight;
                }

                async function checkAgentHealth() {
                    const url = getActiveAgentUrl();
                    const candidates = [
                        url,
                        "http://127.0.0.1:18500",
                        `http://${window.location.hostname}:18500`
                    ];
                    // Eliminar duplicados
                    const uniqueCandidates = [...new Set(candidates)];

                    let connectedData = null;
                    let workingUrl = null;

                    for (const cand of uniqueCandidates) {
                        try {
                            const controller = new AbortController();
                            const timeoutId = setTimeout(() => controller.abort(), 1200);
                            const res = await fetch(`${cand}/health`, { signal: controller.signal });
                            clearTimeout(timeoutId);
                            if (res.ok) {
                                connectedData = await res.json();
                                workingUrl = cand;
                                break;
                            }
                        } catch (e) {
                            // Siguiente candidato
                        }
                    }

                    if (connectedData && workingUrl) {
                        currentAgentUrl = workingUrl;
                        currentWsUrl = workingUrl.replace(/^http/, "ws") + "/ws";
                        const input = document.getElementById("custom-agent-url");
                        if (input && input.value !== workingUrl) {
                            input.value = workingUrl;
                        }
                        setAgentOnline(connectedData);
                        if (connectedData.is_rendering && connectedData.progress) {
                            updateProgressUI(connectedData.progress);
                        }
                    } else {
                        setAgentOffline();
                    }
                }

                function setAgentOnline(data) {
                    isAgentOnline = true;

                    const banner = document.getElementById("agent-status-banner");
                    if (banner) banner.className = "w-full p-4 sm:p-5 rounded-2xl border transition-all duration-300 flex items-center justify-between flex-wrap gap-4 bg-emerald-50 border-emerald-200 text-emerald-900";
                    
                    const iconBox = document.getElementById("status-icon-box");
                    if (iconBox) iconBox.className = "w-10 h-10 rounded-xl bg-emerald-200/80 flex items-center justify-center shrink-0";
                    
                    const icon = document.getElementById("status-icon");
                    if (icon) { icon.className = "material-icons text-emerald-700 text-xl"; icon.innerText = "check_circle"; }

                    const gpuInfo = data.gpu || {};
                    const gpuName = gpuInfo.gpu_name || "NVIDIA GPU";
                    const isNvenc = gpuInfo.nvenc_available;

                    const title = document.getElementById("status-title");
                    if (title) title.innerText = "Conectado a la Estación de Edición";
                    
                    const badge = document.getElementById("status-badge");
                    if (badge) {
                        badge.className = "text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-200 text-emerald-950 border border-emerald-300";
                        badge.innerText = isNvenc ? "NVENC HARDWARE ACTIVO" : "CONECTADO (CPU FALLBACK)";
                    }

                    const desc = document.getElementById("status-desc");
                    if (desc) desc.innerText = `Agente activo en ${currentAgentUrl} | GPU: ${gpuName}`;

                    const offlineGuide = document.getElementById("agent-offline-guide");
                    if (offlineGuide) offlineGuide.classList.add("hidden");

                    const gpuChipName = document.getElementById("gpu-chip-name");
                    if (gpuChipName) gpuChipName.innerText = `${gpuName} • ${isNvenc ? 'Aceleración NVENC' : 'Software'}`;
                    
                    const gpuDot = document.getElementById("gpu-dot");
                    if (gpuDot) gpuDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse";

                    connectWebSocket();
                }

                function setAgentOffline() {
                    isAgentOnline = false;

                    const banner = document.getElementById("agent-status-banner");
                    if (banner) banner.className = "w-full p-4 sm:p-5 rounded-2xl border transition-all duration-300 flex items-center justify-between flex-wrap gap-4 bg-amber-50 border-amber-200 text-amber-900";
                    
                    const iconBox = document.getElementById("status-icon-box");
                    if (iconBox) iconBox.className = "w-10 h-10 rounded-xl bg-amber-200/80 flex items-center justify-center shrink-0";
                    
                    const icon = document.getElementById("status-icon");
                    if (icon) { icon.className = "material-icons text-amber-700 text-xl"; icon.innerText = "power_off"; }

                    const title = document.getElementById("status-title");
                    if (title) title.innerText = "Cliente de Edición no detectado";
                    
                    const badge = document.getElementById("status-badge");
                    if (badge) {
                        badge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200";
                        badge.innerText = "DESCONECTADO";
                    }

                    const desc = document.getElementById("status-desc");
                    if (desc) desc.innerText = `No se detecta servicio en ${currentAgentUrl}. Ejecuta MediaHubRenderAgent.exe`;

                    const offlineGuide = document.getElementById("agent-offline-guide");
                    if (offlineGuide) offlineGuide.classList.remove("hidden");

                    const gpuChipName = document.getElementById("gpu-chip-name");
                    if (gpuChipName) gpuChipName.innerText = "Agente no detectado";
                    
                    const gpuDot = document.getElementById("gpu-dot");
                    if (gpuDot) gpuDot.className = "w-2.5 h-2.5 rounded-full bg-slate-400";

                    if (socket) {
                        try { socket.close(); } catch(e){}
                        socket = null;
                    }
                }

                function connectWebSocket() {
                    if (socket) return;
                    try {
                        socket = new WebSocket(currentWsUrl);
                        socket.onopen = () => {
                            console.log("WebSocket con Agente Local conectado.");
                        };
                        socket.onmessage = (event) => {
                            try {
                                const msg = JSON.parse(event.data);
                                handleWsMessage(msg);
                            } catch(e) {}
                        };
                        socket.onclose = () => {
                            socket = null;
                        };
                    } catch(e) {}
                }

                function handleWsMessage(msg) {
                    if (msg.type === "log") {
                        appendLog(msg.message);
                    } else if (msg.type === "progress") {
                        updateProgressUI(msg);
                    } else if (msg.type === "complete") {
                        renderCompletedUI(msg);
                    } else if (msg.type === "error") {
                        renderErrorUI(msg);
                    }
                }

                function updateProgressUI(data) {
                    const btnStart = document.getElementById("btn-start-render");
                    const btnCancel = document.getElementById("btn-cancel-render");
                    if (btnStart) btnStart.classList.add("hidden");
                    if (btnCancel) btnCancel.classList.remove("hidden");

                    const spinner = document.getElementById("render-spinner");
                    if (spinner) { spinner.className = "material-icons text-lg animate-spin text-indigo-600"; spinner.innerText = "autorenew"; }

                    const statusTitle = document.getElementById("render-status-title");
                    if (statusTitle) statusTitle.innerText = "Renderizando Video...";

                    const percent = data.percent || 0.0;
                    const pLabel = document.getElementById("progress-percent-label");
                    if (pLabel) pLabel.innerText = `${percent.toFixed(1)}%`;
                    
                    const pBar = document.getElementById("progress-bar-fill");
                    if (pBar) pBar.style.width = `${percent}%`;

                    const mFps = document.getElementById("metric-fps");
                    if (mFps) mFps.innerText = `${(data.fps || 0).toFixed(1)} fps`;
                    
                    const mSpeed = document.getElementById("metric-speed");
                    if (mSpeed) mSpeed.innerText = data.speed || "0x";
                    
                    const mTime = document.getElementById("metric-time");
                    if (mTime) mTime.innerText = data.time || "00:00:00";

                    const eta = data.eta_seconds || 0;
                    const mEta = document.getElementById("metric-eta");
                    if (mEta) {
                        if (eta > 0) {
                            const m = Math.floor(eta / 60);
                            const s = eta % 60;
                            mEta.innerText = `${m}m ${s}s`;
                        } else {
                            mEta.innerText = "Finalizando...";
                        }
                    }
                }

                function renderCompletedUI(data) {
                    const statusTitle = document.getElementById("render-status-title");
                    if (statusTitle) statusTitle.innerText = "¡Renderizado Exitoso!";
                    
                    const statusSub = document.getElementById("render-status-subtitle");
                    if (statusSub) statusSub.innerText = `Exportado: ${data.output_path} (${data.size_mb} MB)`;
                    
                    const pLabel = document.getElementById("progress-percent-label");
                    if (pLabel) pLabel.innerText = "100%";
                    
                    const pBar = document.getElementById("progress-bar-fill");
                    if (pBar) pBar.style.width = "100%";
                    
                    const mEta = document.getElementById("metric-eta");
                    if (mEta) mEta.innerText = "Completado";

                    const spinner = document.getElementById("render-spinner");
                    if (spinner) { spinner.className = "material-icons text-lg text-emerald-600"; spinner.innerText = "check_circle"; }

                    const btnStart = document.getElementById("btn-start-render");
                    const btnCancel = document.getElementById("btn-cancel-render");
                    if (btnStart) btnStart.classList.remove("hidden");
                    if (btnCancel) btnCancel.classList.add("hidden");

                    appendLog(`🎉 Archivo finalizado exitosamente: ${data.output_path}`, "text-emerald-400 font-bold");
                }

                function renderErrorUI(msg) {
                    const statusTitle = document.getElementById("render-status-title");
                    if (statusTitle) statusTitle.innerText = "Error en el Renderizado";
                    
                    const statusSub = document.getElementById("render-status-subtitle");
                    if (statusSub) statusSub.innerText = msg.message || "Fallo en el proceso";

                    const btnStart = document.getElementById("btn-start-render");
                    const btnCancel = document.getElementById("btn-cancel-render");
                    if (btnStart) btnStart.classList.remove("hidden");
                    if (btnCancel) btnCancel.classList.add("hidden");

                    const spinner = document.getElementById("render-spinner");
                    if (spinner) { spinner.className = "material-icons text-lg text-rose-600"; spinner.innerText = "error"; }

                    appendLog(`❌ ERROR: ${msg.message}`, "text-rose-400 font-bold");
                }

                async function browseNativeFile(targetInputId, title) {
                    const agentUrl = getActiveAgentUrl();
                    if (!isAgentOnline) {
                        appendLog(`⚠️ No se puede abrir el explorador para '${title}': El Agente Local no está conectado.`, "text-amber-400 font-bold");
                        appendLog("👉 Por favor inicia 'MediaHubRenderAgent.exe' en esta estación de edición para habilitar el explorador de Windows.", "text-slate-300");
                        return;
                    }

                    appendLog(`📂 Abriendo explorador de Windows para: ${title}...`, "text-indigo-300");
                    try {
                        const res = await fetch(`${agentUrl}/browse-file`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ title: title, mode: "open" })
                        });
                        const data = await res.json();
                        if (data.filepath) {
                            const inputEl = document.getElementById(targetInputId);
                            if (inputEl) {
                                inputEl.value = data.filepath;
                                inputEl.classList.remove("border-rose-500", "bg-rose-50");
                            }
                            appendLog(`✓ Seleccionado: ${data.filepath}`, "text-emerald-400 font-bold");
                        } else {
                            appendLog("ℹ️ Selección cancelada en Windows.", "text-slate-400");
                        }
                    } catch(e) {
                        appendLog(`❌ Error al conectar con el agente: ${e}`, "text-rose-400 font-bold");
                    }
                }

                async function browseNativeSave(targetInputId, title) {
                    const agentUrl = getActiveAgentUrl();
                    if (!isAgentOnline) {
                        appendLog(`⚠️ No se puede abrir el explorador para '${title}': El Agente Local no está conectado.`, "text-amber-400 font-bold");
                        appendLog("👉 Por favor inicia 'MediaHubRenderAgent.exe' en esta estación de edición.", "text-slate-300");
                        return;
                    }

                    appendLog(`💾 Abriendo explorador de guardado para: ${title}...`, "text-indigo-300");
                    try {
                        const res = await fetch(`${agentUrl}/browse-save`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ title: title, mode: "save", defaultextension: ".mp4" })
                        });
                        const data = await res.json();
                        if (data.filepath) {
                            const inputEl = document.getElementById(targetInputId);
                            if (inputEl) {
                                inputEl.value = data.filepath;
                                inputEl.classList.remove("border-rose-500", "bg-rose-50");
                            }
                            appendLog(`✓ Destino: ${data.filepath}`, "text-emerald-400 font-bold");
                        } else {
                            appendLog("ℹ️ Guardado cancelado en Windows.", "text-slate-400");
                        }
                    } catch(e) {
                        appendLog(`❌ Error al conectar con el agente: ${e}`, "text-rose-400 font-bold");
                    }
                }

                async function startRender() {
                    const agentUrl = getActiveAgentUrl();

                    const baseEl = document.getElementById("input-base-path");
                    const moscaEl = document.getElementById("input-mosca-path");
                    const cierreEl = document.getElementById("input-cierre-path");
                    const outputEl = document.getElementById("input-output-path");

                    const basePath = (baseEl ? baseEl.value : "").trim().replace(/^["']|["']$/g, '');
                    const moscaPath = (moscaEl ? moscaEl.value : "").trim().replace(/^["']|["']$/g, '');
                    const cierrePath = (cierreEl ? cierreEl.value : "").trim().replace(/^["']|["']$/g, '');
                    const outputPath = (outputEl ? outputEl.value : "").trim().replace(/^["']|["']$/g, '');

                    const presetEl = document.getElementById("select-preset");
                    const bitrateEl = document.getElementById("select-bitrate");
                    const preset = presetEl ? presetEl.value : "p4";
                    const bitrate = bitrateEl ? bitrateEl.value : "15M";

                    // Validación visual clara
                    let hasErrors = false;
                    if (!basePath) {
                        if (baseEl) baseEl.classList.add("border-rose-500", "bg-rose-50");
                        hasErrors = true;
                    }
                    if (!moscaPath) {
                        if (moscaEl) moscaEl.classList.add("border-rose-500", "bg-rose-50");
                        hasErrors = true;
                    }
                    if (!cierrePath) {
                        if (cierreEl) cierreEl.classList.add("border-rose-500", "bg-rose-50");
                        hasErrors = true;
                    }
                    if (!outputPath) {
                        if (outputEl) outputEl.classList.add("border-rose-500", "bg-rose-50");
                        hasErrors = true;
                    }

                    if (hasErrors) {
                        appendLog("==================================================", "text-slate-600");
                        appendLog("⚠️ ATENCIÓN: Faltan archivos requeridos para renderizar.", "text-amber-400 font-bold");
                        if (!basePath) appendLog("  ❌ Falta el Video Base Principal (1)", "text-rose-400");
                        if (!moscaPath) appendLog("  ❌ Falta la Mosca Animada con Alfa (2)", "text-rose-400");
                        if (!cierrePath) appendLog("  ❌ Falta la Cortinilla de Cierre (3)", "text-rose-400");
                        if (!outputPath) appendLog("  ❌ Falta la Ruta de Archivo de Salida (4)", "text-rose-400");
                        appendLog("💡 Usa los botones 'Examinar en mi PC' o escribe las rutas completas.", "text-indigo-300");
                        appendLog("==================================================", "text-slate-600");
                        return;
                    }

                    if (!isAgentOnline) {
                        appendLog("==================================================", "text-slate-600");
                        appendLog("❌ NO SE PUEDE INICIAR: El Agente Local está desconectado.", "text-rose-400 font-bold");
                        appendLog(`   El sistema no detecta respuesta en: ${agentUrl}`, "text-rose-300");
                        appendLog("👉 Ejecuta 'MediaHubRenderAgent.exe' en este PC para activar la GPU y comenzar.", "text-amber-300 font-bold");
                        appendLog("==================================================", "text-slate-600");
                        return;
                    }

                    // Actualizar inputs limpios en pantalla
                    if (baseEl) baseEl.value = basePath;
                    if (moscaEl) moscaEl.value = moscaPath;
                    if (cierreEl) cierreEl.value = cierrePath;
                    if (outputEl) outputEl.value = outputPath;

                    // Limpiar y preparar consola
                    appendLog("==================================================", "text-slate-600");
                    appendLog("🚀 ENVIANDO ORDEN DE RENDER AL AGENTE LOCAL", "text-indigo-300 font-bold");
                    appendLog(`* Video Base:  ${basePath}`, "text-slate-300");
                    appendLog(`* Mosca Alpha: ${moscaPath}`, "text-slate-300");
                    appendLog(`* Cierre:      ${cierrePath}`, "text-slate-300");
                    appendLog(`* Salida:      ${outputPath}`, "text-slate-300");
                    appendLog(`* NVENC:       Preset ${preset} • Bitrate ${bitrate}`, "text-slate-400");
                    appendLog("==================================================", "text-slate-600");

                    const statusTitle = document.getElementById("render-status-title");
                    if (statusTitle) statusTitle.innerText = "Iniciando Renderizado...";

                    try {
                        const res = await fetch(`${agentUrl}/render`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                base_path: basePath,
                                mosca_path: moscaPath,
                                cierre_path: cierrePath,
                                output_path: outputPath,
                                preset: preset,
                                bitrate: bitrate,
                                use_nvenc: true
                            })
                        });

                        const data = await res.json();
                        if (!res.ok) {
                            const errDetail = data.detail || JSON.stringify(data);
                            appendLog(`❌ ERROR DEL AGENTE: ${errDetail}`, "text-rose-400 font-bold");
                        } else {
                            appendLog("✓ Orden aceptada por el agente. Esperando análisis de FFprobe...", "text-emerald-400 font-bold");
                        }
                    } catch(e) {
                        appendLog(`❌ Error de comunicación con el agente: ${e}`, "text-rose-400 font-bold");
                    }
                }

                async function cancelRender() {
                    if (!confirm("¿Deseas cancelar el renderizado en curso?")) return;
                    const agentUrl = getActiveAgentUrl();
                    try {
                        await fetch(`${agentUrl}/cancel`, { method: "POST" });
                        appendLog("🛑 Solicitud de cancelación enviada.", "text-amber-400 font-bold");
                    } catch(e) {
                        appendLog(`❌ Error al enviar cancelación: ${e}`, "text-rose-400");
                    }
                }

                // Enlace de eventos y exposición en window
                function setupEventListeners() {
                    ['input-base-path', 'input-mosca-path', 'input-cierre-path', 'input-output-path'].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) {
                            el.addEventListener('input', () => {
                                el.classList.remove('border-rose-500', 'bg-rose-50');
                            });
                        }
                    });

                    const btnStart = document.getElementById('btn-start-render');
                    if (btnStart) btnStart.onclick = startRender;

                    const btnCancel = document.getElementById('btn-cancel-render');
                    if (btnCancel) btnCancel.onclick = cancelRender;

                    const btnBase = document.getElementById('btn-browse-base');
                    if (btnBase) btnBase.onclick = () => browseNativeFile('input-base-path', 'Seleccionar Video Base Principal');

                    const btnMosca = document.getElementById('btn-browse-mosca');
                    if (btnMosca) btnMosca.onclick = () => browseNativeFile('input-mosca-path', 'Seleccionar Mosca Animada con Alfa');

                    const btnCierre = document.getElementById('btn-browse-cierre');
                    if (btnCierre) btnCierre.onclick = () => browseNativeFile('input-cierre-path', 'Seleccionar Cortinilla de Cierre');

                    const btnOut = document.getElementById('btn-browse-output');
                    if (btnOut) btnOut.onclick = () => browseNativeSave('input-output-path', 'Guardar Video Renderizado Como...');
                }

                window.startRender = startRender;
                window.cancelRender = cancelRender;
                window.browseNativeFile = browseNativeFile;
                window.browseNativeSave = browseNativeSave;
                window.reconnectWithCustomUrl = reconnectWithCustomUrl;
                window.checkAgentHealth = checkAgentHealth;

                // Iniciar comprobación periódica y enlace de eventos
                setTimeout(() => {
                    setupEventListeners();
                    checkAgentHealth();
                }, 300);

                setTimeout(setupEventListeners, 1200);

                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(checkAgentHealth, 3000);
            </script>
            ''')
