from database import get_events_by_month
from nicegui import ui
import calendar
from datetime import datetime
from components.timeline_panel import render_timeline
from components.parrilla_excel_importer import open_parrilla_importer_dialog

class CalendarView:
    def __init__(self, user_info):
        self.user_info = user_info
        self.now = datetime.now()
        self.year = self.now.year
        self.month = self.now.month
        self.selected_day = None
        
        with ui.right_drawer(value=False).props('width=460 bordered').classes('bg-white max-w-full') as self.right_panel:
            self.panel_content = ui.column().classes('w-full h-full p-2 sm:p-4 wrap-none')
            
        self.container = ui.column().classes('w-full p-3 sm:p-6 transition-all duration-300')
        self.render()

    def change_month(self, delta):
        self.month += delta
        if self.month > 12:
            self.month = 1; self.year += 1
        elif self.month < 1:
            self.month = 12; self.year -= 1
        
        self.selected_day = None
        self.right_panel.value = False
        self.render()

    def navigate_to_date(self, fecha_str):
        try:
            dt = datetime.strptime(fecha_str, '%Y-%m-%d')
            self.year = dt.year
            self.month = dt.month
            self.selected_day = dt.day
            self.right_panel.value = True
            render_timeline(self.panel_content, self.selected_day, self.month, self.year, self.user_info, on_import_success=self.navigate_to_date)
            self.render()
        except Exception:
            self.render()

    def select_day(self, day):
        if self.selected_day == day:
            self.selected_day = None
            self.right_panel.value = False
        else:
            self.selected_day = day
            self.right_panel.value = True
            render_timeline(self.panel_content, self.selected_day, self.month, self.year, self.user_info, on_import_success=self.navigate_to_date)
            
        self.render()

    def render(self):
        self.container.clear()
        
        # 1. Filtramos los eventos de este mes pasándole el Área del usuario actual
        area = self.user_info.get('area', '').lower()
        eventos_del_mes = get_events_by_month(self.year, self.month, area)
        
        with self.container:
            with ui.row().classes('w-full justify-between items-center mb-6 flex-wrap gap-3'):
                mes_nombre = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                
                with ui.row().classes('items-center gap-3'):
                    ui.label(f"{mes_nombre[self.month-1]} {self.year}").classes('text-2xl sm:text-3xl font-bold text-gray-800 tracking-tight')
                    with ui.row().classes('items-center bg-white rounded-lg shadow-sm border border-gray-200 p-0.5'):
                        ui.button(icon='chevron_left', on_click=lambda: self.change_month(-1)).props('flat dense round size=sm color=grey-8')
                        ui.button('Hoy', on_click=lambda: self.go_to_today()).props('flat dense size=sm color=primary').classes('text-xs font-bold px-2')
                        ui.button(icon='chevron_right', on_click=lambda: self.change_month(1)).props('flat dense round size=sm color=grey-8')

                # Botón de Importar Parrilla/Cronograma Excel dinámico por área (Multitenant)
                btn_import_txt = 'Importar Cronograma (Excel)' if area == 'produccion' else ('Importar Parrilla (Excel)' if area == 'programacion' else f'Importar Cronograma ({area.capitalize()})')
                with ui.row().classes('items-center gap-2'):
                    ui.button(
                        btn_import_txt,
                        icon='upload_file',
                        on_click=lambda: open_parrilla_importer_dialog(self.user_info, on_success_callback=self.navigate_to_date)
                    ).classes('bg-indigo-600 text-white font-bold text-xs px-3.5 py-2 rounded-lg shadow-sm hover:bg-indigo-700 transition-all')

            with ui.grid(columns=7).classes('w-full gap-2 text-center'):
                for d in ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']:
                    ui.label(d).classes('font-bold text-gray-400 py-1 text-sm')

                cal = calendar.monthcalendar(self.year, self.month)
                
                def create_click_handler(d):
                    return lambda e: self.select_day(d)

                for week in cal:
                    for day in week:
                        if day == 0:
                            ui.label('')
                        else:
                            es_hoy = (day == self.now.day and self.month == self.now.month and self.year == self.now.year)
                            es_seleccionado = (day == self.selected_day)
                            day_events = eventos_del_mes.get(day, [])
                            total_ev = len(day_events)
                            
                            if es_seleccionado:
                                estilo = 'bg-blue-50 border-2 border-blue-500 text-blue-900 shadow-md ring-2 ring-blue-200/50'
                            elif es_hoy:
                                estilo = 'bg-blue-600 text-white shadow-md border border-blue-700 hover:bg-blue-700'
                            else:
                                estilo = 'bg-white text-gray-700 hover:bg-slate-50 border border-slate-200/80 shadow-sm'
                            
                            with ui.card().classes(f'relative p-1.5 sm:p-2.5 min-h-[76px] sm:h-28 items-stretch justify-between {estilo} cursor-pointer transition-all duration-150 flex flex-col overflow-hidden rounded-xl') \
                                         .on('click', create_click_handler(day)):
                                
                                # Fila superior del día (Número + Indicador técnico)
                                with ui.row().classes('w-full justify-between items-center shrink-0'):
                                    ui.label(str(day)).classes(f'text-base font-bold {"text-white" if es_hoy else ("text-blue-700 font-extrabold" if es_seleccionado else "text-gray-800")}')
                                    
                                    if total_ev > 0:
                                        hay_pendientes = any(
                                            ev.get('detalles', {}).get('requiere_tecnica', False) and 
                                            ev.get('detalles', {}).get('estado_tecnica', 'pendiente') == 'pendiente' 
                                            for ev in day_events
                                        )
                                        if hay_pendientes:
                                            ui.html('<div class="w-2.5 h-2.5 rounded-full bg-amber-500 ring-2 ring-white shadow-sm" title="Técnica pendiente"></div>')

                                # CUERPO DE LA TARJETA DEL DÍA: Manejo anti-saturación
                                with ui.column().classes('w-full flex-grow justify-end gap-1 overflow-hidden'):
                                    if total_ev >= 5:
                                        # CASO 1: Alta densidad (Parrilla de Emisión TV / Gran volumen)
                                        # Se muestra un resumen ultra limpio y elegante sin saturar el calendario
                                        vivos = sum(1 for ev in day_events if ev.get('detalles', {}).get('modalidad') == 'En Vivo')
                                        
                                        if es_hoy:
                                            badge_tv = 'bg-white/25 text-white border-white/40'
                                            badge_vivo = 'bg-red-500 text-white border-red-300'
                                        else:
                                            badge_tv = 'bg-indigo-50 text-indigo-700 border-indigo-200'
                                            badge_vivo = 'bg-red-50 text-red-700 border-red-200'
                                            
                                        with ui.row().classes('w-full items-center justify-between gap-1 flex-nowrap'):
                                            ui.label(f"📺 {total_ev} progs").classes(f'text-[10px] font-bold px-1.5 py-0.5 rounded border {badge_tv} truncate flex-grow text-center')
                                            if vivos > 0:
                                                ui.label(f"🔴 {vivos} vivo").classes(f'text-[9px] font-extrabold px-1 py-0.5 rounded border {badge_vivo} shrink-0')
                                    
                                    elif total_ev > 0:
                                        # CASO 2: 1 a 4 eventos (Eventos individuales con título legible)
                                        for ev in day_events[:2]:
                                            color_pill = 'bg-white/20 text-white' if es_hoy else 'bg-slate-100 text-slate-800 border border-slate-200'
                                            ui.label(f"{ev['hora_inicio']} {ev['nombre_programa']}").classes(f'text-[10px] font-medium px-1 rounded truncate w-full {color_pill} leading-tight')
                                        if total_ev > 2:
                                            ui.label(f"+ {total_ev - 2} más").classes(f'text-[9px] font-bold {"text-white/80" if es_hoy else "text-slate-400"} text-right w-full')

    def go_to_today(self):
        self.year = self.now.year
        self.month = self.now.month
        self.selected_day = self.now.day
        self.right_panel.value = True
        render_timeline(self.panel_content, self.selected_day, self.month, self.year, self.user_info)
        self.render()