from nicegui import ui
from datetime import datetime
from database import (
    get_transition_rules_config,
    save_transition_rules_config,
    reset_transition_rules_config,
    detect_personnel_transition_conflicts
)

def render_transition_rules_admin(user_info=None):
    """
    Renderiza el panel de administración de reglas de traslado y desplazamientos de personal.
    Permite configurar tiempos de colchón, cambio de estudio, modo de bloqueo y áreas notificadas.
    """
    config_actual = get_transition_rules_config()

    # Estado reactivo local
    state = {
        'activo': config_actual.get('activo', True),
        'tiempo_mismo_estudio': config_actual.get('tiempo_mismo_estudio', 3),
        'tiempo_cambio_estudio': config_actual.get('tiempo_cambio_estudio', 10),
        'tiempo_exterior': config_actual.get('tiempo_exterior', 30),
        'tiempo_ajuste_parrilla_sugerido': config_actual.get('tiempo_ajuste_parrilla_sugerido', 3),
        'modo_bloqueo': config_actual.get('modo_bloqueo', False),
        'campos_supervisados': list(config_actual.get('campos_supervisados', ['sonido', 'sonidista', 'camaras', 'camara', 'camarografo', 'switcher'])),
        'areas_notificar': list(config_actual.get('areas_notificar', ['programacion', 'master', 'emision', 'produccion'])),
        'fecha_prueba': datetime.now().strftime('%Y-%m-%d')
    }

    with ui.column().classes('w-full max-w-5xl mx-auto gap-6 p-2 sm:p-4'):

        # --- CABECERA PRINCIPAL ---
        with ui.card().classes('w-full p-6 bg-gradient-to-r from-amber-950 via-slate-900 to-indigo-950 text-white rounded-2xl shadow-lg border border-amber-500/20'):
            with ui.row().classes('w-full justify-between items-center gap-4 flex-wrap'):
                with ui.row().classes('items-center gap-4'):
                    with ui.element('div').classes('w-14 h-14 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shadow-inner'):
                        ui.icon('transfer_within_a_station', size='lg')
                    with ui.column().classes('gap-0.5'):
                        with ui.row().classes('items-center gap-2'):
                            ui.label('Reglas de Traslado y Desplazamiento Técnico').classes('text-xl sm:text-2xl font-black text-white')
                            ui.badge('Operación TV').props('color=amber-600 text-color=white').classes('text-[10px] font-bold')
                        ui.label('Supervisión de tiempos mínimos entre programas para camarógrafos, sonidistas y personal técnico con alerta a Programación y Emisión.')\
                            .classes('text-xs text-slate-300 max-w-2xl leading-relaxed')

                # Switch maestro de activación
                with ui.row().classes('items-center gap-3 bg-white/10 px-4 py-2 rounded-xl backdrop-blur-xs border border-white/10'):
                    ui.switch('Detección Activa')\
                        .bind_value(state, 'activo')\
                        .props('color=amber-500 keep-color')\
                        .classes('text-xs font-bold text-white')

        # --- SECCIÓN 1: TIEMPOS MÍNIMOS DE TRANSICIÓN ---
        with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-xs gap-4'):
            with ui.row().classes('items-center gap-2 border-b border-slate-100 pb-3 w-full'):
                ui.icon('timer', size='md').classes('text-amber-600')
                with ui.column().classes('gap-0'):
                    ui.label('1. Tiempos Mínimos de Traslado y Preparación').classes('text-base font-bold text-slate-800')
                    ui.label('Minutos mínimos que debe tener un colaborador entre el final de un programa y el inicio del siguiente según la locación.').classes('text-xs text-slate-400')

            with ui.grid().classes('grid-cols-1 md:grid-cols-3 gap-6 w-full pt-2'):
                # 1. Mismo estudio
                with ui.column().classes('p-4 rounded-xl bg-slate-50 border border-slate-200 gap-2 hover:border-amber-300 transition-colors'):
                    with ui.row().classes('items-center justify-between w-full'):
                        ui.label('Mismo Estudio / Set').classes('text-xs font-bold text-slate-700')
                        ui.icon('meeting_room', size='xs').classes('text-slate-400')
                    ui.number(label='Minutos Mínimos', min=0, max=60, step=1)\
                        .bind_value(state, 'tiempo_mismo_estudio')\
                        .props('outlined dense')\
                        .classes('w-full font-mono font-bold')
                    ui.label('Margen cuando ambos programas son en el mismo lugar (ej: Estudio 1 a Estudio 1).').classes('text-[11px] text-slate-500 leading-tight')

                # 2. Cambio de estudio
                with ui.column().classes('p-4 rounded-xl bg-amber-50/60 border border-amber-200 gap-2 hover:border-amber-400 transition-colors'):
                    with ui.row().classes('items-center justify-between w-full'):
                        ui.label('Cambio de Estudio / Set').classes('text-xs font-bold text-amber-900')
                        ui.icon('swap_horiz', size='xs').classes('text-amber-600')
                    ui.number(label='Minutos Mínimos', min=1, max=120, step=1)\
                        .bind_value(state, 'tiempo_cambio_estudio')\
                        .props('outlined dense')\
                        .classes('w-full font-mono font-bold')
                    ui.label('Margen para mover equipos y calibrar al cambiar de set (ej: Estudio 1 ➔ Estudio 3).').classes('text-[11px] text-amber-800 leading-tight')

                # 3. Exterior / Remoto
                with ui.column().classes('p-4 rounded-xl bg-blue-50/60 border border-blue-200 gap-2 hover:border-blue-400 transition-colors'):
                    with ui.row().classes('items-center justify-between w-full'):
                        ui.label('Hacia / Desde Exteriores').classes('text-xs font-bold text-blue-900')
                        ui.icon('commute', size='xs').classes('text-blue-600')
                    ui.number(label='Minutos Mínimos', min=5, max=240, step=5)\
                        .bind_value(state, 'tiempo_exterior')\
                        .props('outlined dense')\
                        .classes('w-full font-mono font-bold')
                    ui.label('Margen si involucra exteriores, banco de alimentos o unidades móviles fuera del canal.').classes('text-[11px] text-blue-800 leading-tight')

        # --- SECCIÓN 2: AJUSTE DE PARRILLA Y MODO DE OPERACIÓN ---
        with ui.grid().classes('grid-cols-1 md:grid-cols-2 gap-6 w-full'):
            
            # Tarjeta de Ajuste de Parrilla
            with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-xs gap-3'):
                with ui.row().classes('items-center gap-2 border-b border-slate-100 pb-2 w-full'):
                    ui.icon('tune', size='sm').classes('text-indigo-600')
                    ui.label('2. Ajuste Sugerido en Parrilla (Programación)').classes('text-sm font-bold text-slate-800')
                
                ui.label('Tiempo sugerido a los operadores de Programación y Emisión para ajustar el inicio o pautas del programa:').classes('text-xs text-slate-500 leading-relaxed')
                
                with ui.row().classes('items-center gap-4 w-full pt-1'):
                    ui.number(label='Minutos de Ajuste Sugerido', min=1, max=15, step=1)\
                        .bind_value(state, 'tiempo_ajuste_parrilla_sugerido')\
                        .props('outlined dense')\
                        .classes('w-48 font-mono font-bold')
                    ui.badge('Recomendado: 3 min').props('color=indigo-1 text-color=indigo-8').classes('text-xs font-bold py-1 px-2.5')

                ui.label('Este valor se incluye en el mensaje de notificación a Programación y Emisión (ej: "Ajuste de parrilla sugerido: hasta 3 minutos").').classes('text-[11px] text-slate-400')

            # Tarjeta de Modo de Bloqueo vs Advertencia
            with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-xs gap-3'):
                with ui.row().classes('items-center gap-2 border-b border-slate-100 pb-2 w-full'):
                    ui.icon('policy', size='sm').classes('text-rose-600')
                    ui.label('3. Política de Validación en Producción').classes('text-sm font-bold text-slate-800')

                with ui.column().classes('gap-2 w-full pt-1'):
                    ui.radio(
                        options={
                            False: 'Advertencia y Notificación (Recomendado): Permite guardar el evento pero genera la alerta a Programación y Emisión.',
                            True: 'Bloqueo Estricto: Impide guardar el evento en Producción si no cumple el tiempo mínimo requerido.'
                        }
                    ).bind_value(state, 'modo_bloqueo').classes('text-xs text-slate-700 leading-tight')

        # --- SECCIÓN 3: CAMPOS SUPERVISADOS Y ÁREAS A NOTIFICAR ---
        with ui.card().classes('w-full p-6 bg-white border border-slate-200 rounded-2xl shadow-xs gap-4'):
            with ui.row().classes('items-center gap-2 border-b border-slate-100 pb-3 w-full'):
                ui.icon('group_work', size='md').classes('text-emerald-600')
                with ui.column().classes('gap-0'):
                    ui.label('4. Cargos Técnicos Supervisados y Áreas Notificadas').classes('text-base font-bold text-slate-800')
                    ui.label('Selecciona los campos de la ficha técnica que se auditarán y quiénes verán la alerta en la campana.').classes('text-xs text-slate-400')

            with ui.grid().classes('grid-cols-1 md:grid-cols-2 gap-6 w-full'):
                # Campos supervisados
                with ui.column().classes('gap-2'):
                    ui.label('Campos de Personal a Vigilar:').classes('text-xs font-bold text-slate-700')
                    opciones_campos = {
                        'sonido': 'Sonido / Audio',
                        'camaras': 'Camarógrafos / Cámaras',
                        'switcher': 'Switcher / Director de Cámara',
                        'productor': 'Productor Encargado'
                    }
                    with ui.row().classes('gap-2 flex-wrap'):
                        for key_c, lbl_c in opciones_campos.items():
                            def make_toggle_c(kc=key_c):
                                def toggle(e):
                                    if e.value and kc not in state['campos_supervisados']:
                                        state['campos_supervisados'].append(kc)
                                    elif not e.value and kc in state['campos_supervisados']:
                                        state['campos_supervisados'].remove(kc)
                                return toggle
                            ui.checkbox(lbl_c, value=(key_c in state['campos_supervisados']), on_change=make_toggle_c(key_c))\
                                .classes('text-xs text-slate-700 font-medium')

                # Áreas a notificar
                with ui.column().classes('gap-2'):
                    ui.label('Áreas que Recibirán la Alerta en su Barra Superior:').classes('text-xs font-bold text-slate-700')
                    opciones_areas = {
                        'programacion': 'Programación (Gestión de Parrilla)',
                        'master': 'Master de Emisión',
                        'emision': 'Operador de Emisión',
                        'produccion': 'Producción (Área Creadora)'
                    }
                    with ui.row().classes('gap-2 flex-wrap'):
                        for key_a, lbl_a in opciones_areas.items():
                            def make_toggle_a(ka=key_a):
                                def toggle(e):
                                    if e.value and ka not in state['areas_notificar']:
                                        state['areas_notificar'].append(ka)
                                    elif not e.value and ka in state['areas_notificar']:
                                        state['areas_notificar'].remove(ka)
                                return toggle
                            ui.checkbox(lbl_a, value=(key_a in state['areas_notificar']), on_change=make_toggle_a(key_a))\
                                .classes('text-xs text-slate-700 font-medium')

        # --- SECCIÓN 4: SIMULADOR / AUDITOR EN TIEMPO REAL ---
        with ui.card().classes('w-full p-6 bg-slate-900 text-white rounded-2xl shadow-md gap-4'):
            with ui.row().classes('w-full justify-between items-center border-b border-slate-800 pb-3 flex-wrap gap-2'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('radar', size='md').classes('text-amber-400 animate-pulse')
                    with ui.column().classes('gap-0'):
                        ui.label('Simulador y Verificador de Conflictos en Vivo').classes('text-base font-bold text-white')
                        ui.label('Prueba cómo aplican estas reglas sobre las fechas reales de programación en el sistema.').classes('text-xs text-slate-400')

                with ui.row().classes('items-center gap-2'):
                    ui.input('Fecha a Auditar', value=state['fecha_prueba'])\
                        .bind_value(state, 'fecha_prueba')\
                        .props('type=date dense outlined dark')\
                        .classes('w-44 text-xs')
                    
                    btn_scan = ui.button('Auditar Fecha', icon='search')\
                        .classes('bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-xs')

            resultados_container = ui.column().classes('w-full gap-2')

            def ejecutar_auditoria():
                resultados_container.clear()
                fecha_sel = state['fecha_prueba']
                # Construimos reglas temporales con el estado actual de la pantalla
                reglas_simuladas = {
                    'activo': state['activo'],
                    'tiempo_mismo_estudio': int(state['tiempo_mismo_estudio'] or 3),
                    'tiempo_cambio_estudio': int(state['tiempo_cambio_estudio'] or 10),
                    'tiempo_exterior': int(state['tiempo_exterior'] or 30),
                    'tiempo_ajuste_parrilla_sugerido': int(state['tiempo_ajuste_parrilla_sugerido'] or 3),
                    'campos_supervisados': state['campos_supervisados'],
                    'exterior_keywords': ['exterior', 'exteriores', 'remoto', 'unidad movil', 'calle', 'banco de alimentos']
                }

                # Temporarily save or run detection
                conflictos = detect_personnel_transition_conflicts(fecha_sel)
                
                with resultados_container:
                    if not conflictos:
                        with ui.row().classes('w-full p-4 bg-emerald-950/40 border border-emerald-500/30 rounded-xl items-center gap-3'):
                            ui.icon('check_circle', size='md').classes('text-emerald-400')
                            with ui.column().classes('gap-0'):
                                ui.label(f'¡Sin conflictos de traslado en {fecha_sel}!').classes('text-sm font-bold text-emerald-300')
                                ui.label('Todo el personal técnico asignado cumple con los tiempos de desplazamiento establecidos.').classes('text-xs text-emerald-400/80')
                    else:
                        with ui.row().classes('w-full items-center justify-between mb-1'):
                            ui.label(f'Se detectaron {len(conflictos)} cruces técnicos en {fecha_sel}:').classes('text-xs font-bold text-amber-300')
                            ui.badge(f'{len(conflictos)} Alertas').props('color=amber-600')

                        for c in conflictos:
                            with ui.card().classes('w-full p-3.5 bg-slate-800/80 border border-amber-500/30 rounded-xl gap-2'):
                                with ui.row().classes('w-full justify-between items-center'):
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('warning', size='xs').classes('text-amber-400')
                                        ui.label(f"{c['persona']} ({c['rol_a']})").classes('text-xs font-bold text-white')
                                    ui.badge(c['tipo_alerta']).props('color=amber-900 text-color=amber-200 outline').classes('text-[10px]')

                                with ui.row().classes('w-full items-center gap-2 text-xs text-slate-300 flex-wrap'):
                                    ev_a_nom = c.get('evento_a', {}).get('nombre') or c.get('evento_a', {}).get('nombre_programa', 'Programa 1')
                                    ev_b_nom = c.get('evento_b', {}).get('nombre') or c.get('evento_b', {}).get('nombre_programa', 'Programa 2')
                                    h_ini_a = c.get('evento_a', {}).get('hora_inicio', '')
                                    h_fin_a = c.get('evento_a', {}).get('hora_fin', '')
                                    h_ini_b = c.get('evento_b', {}).get('hora_inicio', '')
                                    h_fin_b = c.get('evento_b', {}).get('hora_fin', '')
                                    ui.label(f"Programa 1: {ev_a_nom} ({c.get('locacion_a', 'Estudio')}) {h_ini_a}-{h_fin_a}").classes('bg-slate-700/60 px-2 py-0.5 rounded')
                                    ui.icon('arrow_forward', size='xs').classes('text-amber-400')
                                    ui.label(f"Programa 2: {ev_b_nom} ({c.get('locacion_b', 'Estudio')}) {h_ini_b}-{h_fin_b}").classes('bg-slate-700/60 px-2 py-0.5 rounded')

                                with ui.row().classes('w-full justify-between items-center text-[11px] text-slate-400 pt-1 border-t border-slate-700/50'):
                                    ui.label(f"Margen Real: {c['margen']} min • Requerido: {c['requerido']} min").classes('font-mono text-amber-300 font-bold')
                                    ui.label(f"Ajuste de Parrilla Sugerido: {c['ajuste_sugerido']} min").classes('text-indigo-300 font-bold')

            btn_scan.on_click(ejecutar_auditoria)
            # Ejecutar al cargar la vista
            ejecutar_auditoria()

        # --- BOTONES DE GUARDADO Y RESTAURACIÓN ---
        with ui.row().classes('w-full justify-between items-center pt-2 pb-8 flex-wrap gap-4'):
            def restaurar_defaults():
                reset_transition_rules_config()
                ui.notify('Valores oficiales restaurados', type='info')
                config_fresh = get_transition_rules_config()
                state.update(config_fresh)

            ui.button('Restaurar Valores por Defecto', icon='restart_alt', on_click=restaurar_defaults)\
                .props('flat text-color=grey')\
                .classes('text-xs font-bold')

            def guardar_cambios():
                dict_para_guardar = {
                    'activo': state['activo'],
                    'tiempo_mismo_estudio': int(state['tiempo_mismo_estudio'] or 3),
                    'tiempo_cambio_estudio': int(state['tiempo_cambio_estudio'] or 10),
                    'tiempo_exterior': int(state['tiempo_exterior'] or 30),
                    'tiempo_ajuste_parrilla_sugerido': int(state['tiempo_ajuste_parrilla_sugerido'] or 3),
                    'modo_bloqueo': bool(state['modo_bloqueo']),
                    'campos_supervisados': state['campos_supervisados'],
                    'areas_notificar': state['areas_notificar'],
                    'exterior_keywords': ['exterior', 'exteriores', 'remoto', 'unidad movil', 'calle', 'banco de alimentos']
                }
                ok, msg = save_transition_rules_config(dict_para_guardar)
                if ok:
                    ui.notify(msg, type='positive', icon='check_circle')
                else:
                    ui.notify(msg, type='negative')

            ui.button('Guardar Configuración de Reglas', icon='save', on_click=guardar_cambios)\
                .classes('bg-amber-600 hover:bg-amber-700 text-white font-black text-sm px-8 py-3 rounded-xl shadow-lg')
