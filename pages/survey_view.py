# -*- coding: utf-8 -*-
import json
import os
from nicegui import ui, app
from components.topbar import topbar
from components.sidebar import sidebar
from database import (
    get_user_by_usuario,
    get_active_survey,
    get_user_survey_response,
    save_survey_response,
    get_survey_stats,
    export_survey_to_excel
)

def survey_page():
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    ui.query('body').style('background-color: #f8fafc; margin: 0; padding: 0;')

    topbar(user_info)
    sidebar(user_info)

    survey = get_active_survey('teleamiga_interna_2026')
    if not survey:
        with ui.column().classes('w-full items-center justify-center p-12 text-center'):
            ui.icon('sentiment_dissatisfied', size='xl').classes('text-slate-400')
            ui.label('No hay una encuesta activa en este momento.').classes('text-xl font-bold text-slate-700 mt-2')
            ui.button('Volver a Herramientas', on_click=lambda: ui.navigate.to('/herramientas')).classes('mt-4 bg-indigo-600 text-white')
        return

    # Cargar respuesta previa o borrador si existe
    user_response_record = get_user_survey_response(survey['id'], user_info['id'])
    saved_answers = user_response_record.get('responses', {}) if user_response_record else {}
    is_completed = user_response_record and (user_response_record.get('is_draft') == 0)
    submitted_date = user_response_record.get('submitted_at', '') if user_response_record else ''

    # Estado reactivo local para los valores de respuesta
    form_values = dict(saved_answers)
    form_controls = {} # id -> control reference or state

    questions = survey.get('questions', [])
    sections = survey.get('sections', [])

    # Permisos de administración/gerencia para ver métricas
    area = (user_info.get('area') or user_info.get('area_encargada') or '').lower()
    cargo = (user_info.get('cargo') or '').lower()
    es_admin = any(k in area or k in cargo for k in ['gerencia', 'gerente', 'director', 'sistemas', 'admin', 'ingenieria'])

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 sm:p-6 md:p-8 gap-6'):
        
        # --- ENCABEZADO PRINCIPAL (HERO) ---
        with ui.card().classes('w-full bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-900 text-white p-6 sm:p-8 rounded-3xl shadow-xl border border-slate-800 relative overflow-hidden'):
            with ui.row().classes('items-center justify-between w-full flex-wrap gap-4 z-10 relative'):
                with ui.row().classes('items-center gap-3'):
                    with ui.element('div').classes('w-12 h-12 rounded-2xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center text-blue-300 shrink-0'):
                        ui.icon('quiz', size='md')
                    with ui.column().classes('gap-0.5'):
                        with ui.row().classes('items-center gap-2'):
                            ui.badge('TELEAMIGA INTERNACIONAL').props('color=blue-5 text-color=white').classes('text-[10px] font-black tracking-widest')
                            if is_completed:
                                ui.badge('COMPLETADA').props('color=emerald-5 text-color=white').classes('text-[10px] font-bold')
                            elif user_response_record:
                                ui.badge('BORRADOR GUARDADO').props('color=amber-5 text-color=slate-900').classes('text-[10px] font-bold')
                            else:
                                ui.badge('NUEVA ENCUESTA').props('color=rose-5 text-color=white').classes('text-[10px] font-bold')
                                
                        ui.label(survey['title']).classes('text-xl sm:text-2xl md:text-3xl font-black tracking-tight')

                # Botones superiores de navegación / métricas
                with ui.row().classes('items-center gap-2'):
                    ui.button('Volver', icon='arrow_back', on_click=lambda: ui.navigate.to('/herramientas'))\
                        .props('flat dense')\
                        .classes('text-white/80 hover:text-white text-xs')
                    if es_admin:
                        ui.button('Ver Resultados y Estadísticas', icon='insights', on_click=lambda: ui.navigate.to('/herramientas/encuesta/resultados'))\
                            .classes('bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs px-3.5 py-2 rounded-xl shadow-sm')

            ui.separator().classes('my-4 bg-white/10')

            ui.markdown(survey['description']).classes('text-slate-200 text-xs sm:text-sm leading-relaxed max-w-3xl')

            # Banner de estado del colaborador
            with ui.row().classes('w-full items-center justify-between mt-4 pt-3 border-t border-white/10 text-xs text-blue-200/80 flex-wrap gap-2'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('person', size='xs')
                    ui.label(f"Respondiendo como: {user_info['nombres']} {user_info['apellidos']} ({user_info.get('cargo', 'Colaborador')} • {user_info.get('area', '')})").classes('font-medium')
                
                if is_completed and submitted_date:
                    with ui.row().classes('items-center gap-1.5 text-emerald-300 font-bold'):
                        ui.icon('check_circle', size='xs')
                        ui.label(f"Enviada el: {submitted_date}")

        # --- NAVEGACIÓN RÁPIDA ENTRE SECCIONES ---
        with ui.card().classes('w-full bg-white border border-slate-200 p-4 rounded-2xl shadow-xs'):
            ui.label('Secciones de la Encuesta (28 Preguntas)').classes('text-xs font-black tracking-wider text-slate-400 uppercase mb-2')
            with ui.row().classes('w-full gap-2 flex-wrap items-center'):
                for s in sections:
                    with ui.element('a').classes('flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 text-xs font-semibold transition-all border border-slate-200/70 cursor-pointer')\
                         .props(f'href=#{s["id"]}'):
                        ui.icon(s['icon'], size='xs')
                        ui.label(s['title'])
                        ui.label(f"({s['range']})").classes('text-[10px] text-slate-400 font-normal')

        # --- FORMULARIO AGRUPADO POR SECCIONES ---
        for sec in sections:
            sec_questions = [q for q in questions if q.get('section_id') == sec['id']]
            if not sec_questions:
                continue

            with ui.card().classes('w-full bg-white border border-slate-200/80 p-6 sm:p-8 rounded-3xl shadow-sm gap-6').props(f'id={sec["id"]}'):
                # Cabecera de la sección
                with ui.row().classes('items-center gap-3 border-b border-slate-100 pb-4 w-full'):
                    with ui.element('div').classes('w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0 shadow-xs'):
                        ui.icon(sec['icon'], size='sm')
                    with ui.column().classes('gap-0'):
                        ui.label(sec['title']).classes('text-lg sm:text-xl font-black text-slate-900')
                        ui.label(f"{sec['range']} • Evaluación constructiva").classes('text-xs font-medium text-slate-400')

                # Preguntas de la sección
                for q in sec_questions:
                    q_id = q['id']
                    curr_val = form_values.get(q_id)
                    q_type = q['type']

                    with ui.column().classes('w-full gap-2.5 p-4 sm:p-5 rounded-2xl bg-slate-50/70 border border-slate-200/60'):
                        with ui.row().classes('items-start justify-between w-full gap-2'):
                            with ui.row().classes('items-start gap-2 max-w-2xl'):
                                ui.badge(f"P{q['number']}").props('color=indigo-1 text-color=indigo-9').classes('text-xs font-black px-2.5 py-1 rounded-lg shrink-0 mt-0.5')
                                ui.label(q['question']).classes('text-sm sm:text-base font-bold text-slate-800 leading-snug')
                            
                            if q.get('helper'):
                                ui.badge(q['helper']).props('outline color=slate-4').classes('text-[10px] text-slate-500 font-medium')

                        # 1. TIPO: SELECCIÓN MÚLTIPLE
                        if q_type == 'multiple_choice':
                            max_sel = q.get('max_selections', 3)
                            selected_items = curr_val if isinstance(curr_val, list) else []
                            
                            # Contenedor reactivo
                            counter_label = ui.label(f"Seleccionados: {len(selected_items)} de máximo {max_sel}")\
                                .classes('text-xs font-bold text-indigo-600')

                            def make_cb_handler(qid, max_s, c_label, other_inp=None):
                                def on_change(e):
                                    cur = form_values.get(qid, [])
                                    if not isinstance(cur, list):
                                        cur = []
                                    opt_val = e.sender.text
                                    if e.value:
                                        if len(cur) >= max_s and opt_val not in cur:
                                            e.sender.value = False
                                            ui.notify(f"Solo puedes seleccionar hasta {max_s} opciones para esta pregunta.", type='warning')
                                            return
                                        if opt_val not in cur:
                                            cur.append(opt_val)
                                    else:
                                        if opt_val in cur:
                                            cur.remove(opt_val)
                                    form_values[qid] = cur
                                    c_label.set_text(f"Seleccionados: {len(cur)} de máximo {max_s}")
                                return on_change

                            with ui.grid().classes('grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-1'):
                                for opt in q.get('options', []):
                                    is_chk = opt in selected_items
                                    cb = ui.checkbox(opt, value=is_chk).classes('text-xs text-slate-700')
                                    cb.on('change', make_cb_handler(q_id, max_sel, counter_label))

                            # Campo opcional "Otro/Otra"
                            if q.get('has_other'):
                                other_key = f"{q_id}_other"
                                other_val = form_values.get(other_key, '')
                                with ui.row().classes('items-center gap-2 w-full pt-2'):
                                    ui.icon('add_circle_outline', size='xs').classes('text-slate-400')
                                    ui.label('Otra opción:').classes('text-xs font-semibold text-slate-600 shrink-0')
                                    txt_other = ui.input(placeholder=q.get('other_placeholder', 'Especifique cuál...'), value=other_val)\
                                        .classes('grow text-xs bg-white rounded-lg px-2')
                                    def update_other(e, k=other_key):
                                        form_values[k] = e.value
                                    txt_other.on('change', update_other)

                        # 2. TIPO: SELECCIÓN ÚNICA (RADIO O CHIPS)
                        elif q_type == 'single_choice':
                            options = q.get('options', [])
                            def make_radio_handler(qid):
                                def on_radio_change(e):
                                    form_values[qid] = e.value
                                return on_radio_change

                            with ui.row().classes('gap-3 flex-wrap pt-1'):
                                radio = ui.radio(options, value=curr_val).props('inline').classes('text-xs text-slate-700')
                                radio.on('change', make_radio_handler(q_id))

                        # 3. TIPO: RANKING / PRIORIZACIÓN (ORDENAR 1 A 7)
                        elif q_type == 'ranking':
                            options = q.get('options', [])
                            ranking_dict = curr_val if isinstance(curr_val, dict) else {}
                            ui.label('Asigna la prioridad de 1 (más relevante) a 7 (menos relevante) para cada criterio:')\
                                .classes('text-xs text-slate-500 font-medium')
                            
                            with ui.column().classes('w-full gap-2 pt-1'):
                                for idx, opt in enumerate(options, start=1):
                                    with ui.row().classes('items-center justify-between w-full bg-white p-2.5 rounded-xl border border-slate-200/80'):
                                        ui.label(opt).classes('text-xs font-semibold text-slate-700 grow')
                                        cur_rank = ranking_dict.get(opt, idx)
                                        sel = ui.select(
                                            options=[1, 2, 3, 4, 5, 6, 7],
                                            value=cur_rank
                                        ).props('dense outlined').classes('w-28 text-xs')
                                        
                                        def make_rank_handler(qid, option_text):
                                            def on_rank_change(e):
                                                rd = form_values.get(qid, {})
                                                if not isinstance(rd, dict):
                                                    rd = {}
                                                rd[option_text] = int(e.value)
                                                form_values[qid] = rd
                                            return on_rank_change
                                            
                                        sel.on('change', make_rank_handler(q_id, opt))

                        # 4. TIPO: RESPUESTA ABIERTA (TEXTAREA O INPUT)
                        else:
                            placeholder = q.get('placeholder', 'Escriba su respuesta...')
                            is_long = q.get('number') in [2, 7, 9, 10, 11, 13, 14, 15, 19, 20, 21, 24, 25, 26, 27, 28]
                            
                            def make_text_handler(qid):
                                def on_text_change(e):
                                    form_values[qid] = e.value
                                return on_text_change

                            if is_long:
                                txt = ui.textarea(placeholder=placeholder, value=str(curr_val or ''))\
                                    .classes('w-full bg-white rounded-xl text-xs sm:text-sm p-1')\
                                    .props('rows=3 outlined counter')
                                txt.on('change', make_text_handler(q_id))
                            else:
                                txt = ui.input(placeholder=placeholder, value=str(curr_val or ''))\
                                    .classes('w-full bg-white rounded-xl text-xs sm:text-sm')\
                                    .props('outlined')
                                txt.on('change', make_text_handler(q_id))

        # --- BARRA FLOTANTE DE ACCIONES (GUARDAR BORRADOR / ENVIAR) ---
        with ui.card().classes('w-full bg-white border border-slate-200 p-5 rounded-3xl shadow-lg sticky bottom-4 z-40'):
            with ui.row().classes('items-center justify-between w-full flex-wrap gap-4'):
                with ui.column().classes('gap-0'):
                    ui.label('Finalización de la Encuesta').classes('font-black text-slate-900 text-sm sm:text-base')
                    ui.label('Puedes guardar un borrador para continuar luego o enviar tus respuestas definitivas.').classes('text-xs text-slate-500')

                with ui.row().classes('items-center gap-3'):
                    def handle_save_draft():
                        ok = save_survey_response(survey['id'], user_info, form_values, is_draft=True)
                        if ok:
                            ui.notify('Borrador guardado exitosamente. Podrás continuar en cualquier momento.', type='positive', icon='save')
                        else:
                            ui.notify('Hubo un error al guardar el borrador.', type='negative')

                    def handle_submit_survey():
                        # Validar que al menos haya respondido algunas preguntas clave
                        answered_count = len([k for k, v in form_values.items() if v and not k.endswith('_other')])
                        if answered_count < 5:
                            ui.notify(f'Has respondido {answered_count} preguntas. Te invitamos a diligenciar más secciones para enviar la encuesta.', type='warning')
                            return

                        # Diálogo de confirmación
                        with ui.dialog() as confirm_dialog, ui.card().classes('p-6 rounded-2xl max-w-md gap-4'):
                            with ui.row().classes('items-center gap-3 text-slate-900'):
                                ui.icon('send', size='md').classes('text-blue-600')
                                ui.label('¿Enviar Encuesta Definitiva?').classes('text-lg font-black')
                            ui.label('Tus respuestas serán enviadas a la Dirección y Gerencia de Teleamiga para la formulación de la nueva parrilla y programación.')\
                                .classes('text-xs text-slate-600 leading-relaxed')

                            with ui.row().classes('w-full justify-end gap-2 pt-2'):
                                ui.button('Revisar más', on_click=confirm_dialog.close).props('flat dense').classes('text-xs text-slate-500 font-semibold')
                                
                                def do_final_send():
                                    confirm_dialog.close()
                                    ok = save_survey_response(survey['id'], user_info, form_values, is_draft=False)
                                    if ok:
                                        # Mostrar diálogo de felicitación y agradecimiento
                                        with ui.dialog() as success_dialog, ui.card().classes('p-8 rounded-3xl max-w-md items-center text-center gap-4'):
                                            with ui.element('div').classes('w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600'):
                                                ui.icon('check_circle', size='lg')
                                            ui.label('¡Encuesta Enviada con Éxito!').classes('text-xl font-black text-slate-900')
                                            ui.label('Gracias por ser protagonista en la construcción de la nueva Teleamiga. Tu opinión es muy valiosa.')\
                                                .classes('text-xs text-slate-600 leading-relaxed')
                                            ui.button('Volver a Herramientas', on_click=lambda: ui.navigate.to('/herramientas'))\
                                                .classes('w-full bg-blue-600 text-white font-bold py-2 rounded-xl shadow-md')
                                        success_dialog.open()
                                    else:
                                        ui.notify('Error al enviar la encuesta. Inténtalo de nuevo.', type='negative')

                                ui.button('Confirmar y Enviar', on_click=do_final_send)\
                                    .classes('bg-blue-600 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-sm')

                        confirm_dialog.open()

                    ui.button('Guardar Borrador', icon='save', on_click=handle_save_draft)\
                        .classes('bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs sm:text-sm px-4 py-2.5 rounded-xl transition-all')

                    ui.button('Enviar Encuesta', icon='send', on_click=handle_submit_survey)\
                        .classes('bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs sm:text-sm px-6 py-2.5 rounded-xl shadow-md transition-all')


# ==============================================================================
# VISTA DE RESULTADOS Y ESTADÍSTICAS (GERENCIA / SISTEMAS / INGENIERÍA)
# ==============================================================================

def survey_results_page():
    username = app.storage.user.get('username')
    if not username:
        ui.navigate.to('/login')
        return

    user_info = get_user_by_usuario(username)
    if not user_info:
        app.storage.user.clear()
        ui.navigate.to('/login')
        return

    area = (user_info.get('area') or user_info.get('area_encargada') or '').lower()
    cargo = (user_info.get('cargo') or '').lower()
    es_admin = any(k in area or k in cargo for k in ['gerencia', 'gerente', 'director', 'sistemas', 'admin', 'ingenieria'])

    if not es_admin:
        ui.notify('No tienes permisos para ver el consolidado de resultados.', type='warning')
        ui.navigate.to('/herramientas/encuesta')
        return

    ui.query('body').style('background-color: #f8fafc; margin: 0; padding: 0;')
    topbar(user_info)
    sidebar(user_info)

    survey = get_active_survey('teleamiga_interna_2026')
    stats = get_survey_stats(survey['id']) if survey else {'total_responses': 0}
    questions = survey.get('questions', []) if survey else []

    with ui.column().classes('w-full max-w-6xl mx-auto p-4 sm:p-6 md:p-8 gap-6'):
        
        # Cabecera de Estadísticas
        with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-8 rounded-3xl shadow-sm'):
            with ui.row().classes('items-center justify-between w-full flex-wrap gap-4'):
                with ui.row().classes('items-center gap-4'):
                    with ui.element('div').classes('w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0'):
                        ui.icon('insights', size='md')
                    with ui.column().classes('gap-0.5'):
                        ui.badge('CONSOLIDADO EJECUTIVO').props('color=indigo-1 text-color=indigo-9').classes('text-[10px] font-black')
                        ui.label('Resultados & Métricas: Encuesta Interna Teleamiga').classes('text-2xl font-black text-slate-900')
                        ui.label(f"Total de respuestas completadas: {stats['total_responses']} colaboradores").classes('text-xs text-slate-500 font-semibold')

                with ui.row().classes('items-center gap-2'):
                    ui.button('Volver a Encuesta', icon='arrow_back', on_click=lambda: ui.navigate.to('/herramientas/encuesta'))\
                        .classes('bg-white border border-slate-300 text-slate-700 text-xs font-bold px-4 py-2 rounded-xl')
                    
                    def download_excel():
                        if stats['total_responses'] == 0:
                            ui.notify('Aún no hay respuestas registradas para exportar.', type='warning')
                            return
                        file_path = export_survey_to_excel(survey['id'])
                        filename = os.path.basename(file_path)
                        ui.download(f"/descargar_reporte_encuesta/{filename}")
                        ui.notify('Reporte generado exitosamente', type='positive', icon='download')

                    ui.button('Exportar a Excel (.xlsx)', icon='table_view', on_click=download_excel)\
                        .classes('bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-sm')

        # Tarjetas de Participación por Área
        with ui.row().classes('w-full gap-4 flex-wrap items-stretch'):
            with ui.card().classes('grow bg-white border border-slate-200 p-5 rounded-2xl shadow-xs'):
                ui.label('Participación por Departamentos').classes('text-xs font-black text-slate-400 uppercase mb-3')
                if not stats.get('by_area'):
                    ui.label('Sin respuestas aún.').classes('text-xs text-slate-400 italic')
                else:
                    for ar, cnt in stats['by_area'].items():
                        pct = (cnt / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
                        with ui.column().classes('w-full gap-1 mb-2'):
                            with ui.row().classes('justify-between text-xs font-bold text-slate-700'):
                                ui.label(ar.upper())
                                ui.label(f"{cnt} ({pct:.0f}%)")
                            ui.linear_progress(value=pct/100, show_value=False).props('color=indigo').classes('h-2 rounded-full')

            with ui.card().classes('w-full sm:w-80 bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-100 p-5 rounded-2xl shadow-xs justify-between'):
                ui.label('Estatus del Proceso').classes('text-xs font-black text-indigo-900 uppercase')
                with ui.column().classes('items-center justify-center my-4 text-center'):
                    ui.label(str(stats['total_responses'])).classes('text-5xl font-black text-indigo-700')
                    ui.label('Colaboradores Han Respondido').classes('text-xs font-bold text-indigo-950')
                ui.label('Los resultados se actualizan en tiempo real a medida que cada colaborador envía su formulario.').classes('text-[11px] text-slate-500 leading-tight')

        # Desglose de preguntas clave
        with ui.card().classes('w-full bg-white border border-slate-200 p-6 sm:p-8 rounded-3xl shadow-sm gap-6'):
            ui.label('Desglose de Preguntas Cuantitativas').classes('text-lg font-black text-slate-900')

            for q in questions:
                q_id = q['id']
                q_type = q['type']
                if q_type not in ('multiple_choice', 'single_choice', 'ranking'):
                    continue

                q_stat = stats['questions'].get(q_id, {})
                with ui.column().classes('w-full gap-2 p-4 rounded-2xl bg-slate-50 border border-slate-200/70'):
                    with ui.row().classes('items-center gap-2'):
                        ui.badge(f"P{q['number']}").props('color=indigo-1 text-color=indigo-9').classes('text-xs font-black')
                        ui.label(q['question']).classes('text-sm font-bold text-slate-800')

                    if q_type in ('multiple_choice', 'single_choice'):
                        counts = q_stat.get('counts', {})
                        sorted_opts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                        with ui.grid().classes('grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-1'):
                            for opt, cnt in sorted_opts:
                                pct = (cnt / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
                                with ui.row().classes('items-center justify-between bg-white p-2.5 rounded-xl border border-slate-200/80'):
                                    ui.label(opt).classes('text-xs font-medium text-slate-700 grow')
                                    with ui.row().classes('items-center gap-1.5 shrink-0'):
                                        ui.badge(f"{cnt} votos").props('outline color=slate-6').classes('text-[10px] font-bold')
                                        ui.label(f"{pct:.0f}%").classes('text-xs font-black text-indigo-600 w-9 text-right')

                    elif q_type == 'ranking':
                        avg_ranks = q_stat.get('avg_ranks', {})
                        sorted_ranks = sorted(avg_ranks.items(), key=lambda x: x[1])
                        ui.label('Prioridad promedio asignada (Menor puntaje = Mayor prioridad):').classes('text-xs text-slate-500 font-medium')
                        with ui.column().classes('w-full gap-1.5 pt-1'):
                            for place, (opt, avg) in enumerate(sorted_ranks, start=1):
                                with ui.row().classes('items-center justify-between bg-white p-2.5 rounded-xl border border-slate-200/80'):
                                    with ui.row().classes('items-center gap-2'):
                                        ui.badge(f"#{place}").props('color=amber-6 text-color=white').classes('text-xs font-black')
                                        ui.label(opt).classes('text-xs font-semibold text-slate-800')
                                    ui.label(f"Promedio: {avg}").classes('text-xs font-bold text-slate-500')
