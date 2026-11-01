"""
Fachada unificadora para la vista previa y maquetación de reportes PDF en MediaHub.
Re-exporta las funciones especializadas de:
- components.report_table_renderer (tablas CSS Grid y estimación de alturas)
- components.report_header_footer (encabezados, firmas, cláusulas y pie de página)
- components.report_page_canvas (unificador de hojas Carta/A4 y motor de paginación)
"""

from components.report_table_renderer import (
    estimar_altura_registro,
    render_report_table
)

from components.report_header_footer import (
    resolver_texto_con_variables,
    estimar_altura_texto,
    render_report_header,
    render_report_apertura,
    render_report_cierre,
    render_report_firmas,
    render_report_footer
)

from components.report_page_canvas import (
    obtener_especificacion_papel,
    calcular_paginacion_reporte,
    render_custom_a4_paper
)

__all__ = [
    'render_custom_a4_paper',
    'estimar_altura_registro',
    'estimar_altura_texto',
    'resolver_texto_con_variables',
    'render_report_table',
    'render_report_header',
    'render_report_apertura',
    'render_report_cierre',
    'render_report_firmas',
    'render_report_footer',
    'obtener_especificacion_papel',
    'calcular_paginacion_reporte'
]