# -*- coding: utf-8 -*-
"""
Estructura y catálogo de preguntas para la ENCUESTA INTERNA: CONSTRUYAMOS LA NUEVA TELEAMIGA.
Extraído del documento oficial en ejemplos/ENCUESTA INTERNA canal teleamiga.docx.
"""

def get_teleamiga_survey_data():
    return {
        "code": "teleamiga_interna_2026",
        "title": "ENCUESTA INTERNA — CONSTRUYAMOS LA NUEVA TELEAMIGA",
        "description": (
            "Teleamiga está emprendiendo un proceso de revisión de su programación y queremos que todos sean "
            "protagonistas de esta conversación.\n\n"
            "Esta encuesta busca conocer cómo vemos hoy el canal, qué creemos que necesita nuestra audiencia, "
            "qué contenidos y formatos deberíamos explorar y qué oportunidades estamos dejando sobre la mesa.\n\n"
            "No buscamos respuestas correctas, solo honestidad y creatividad."
        ),
        "sections": [
            {"id": "sec_1", "title": "Diagnóstico Actual y Fortalezas", "icon": "thumb_up", "range": "Preguntas 1 a 5"},
            {"id": "sec_2", "title": "Audiencias y Horarios", "icon": "schedule", "range": "Preguntas 6 y 7"},
            {"id": "sec_3", "title": "Temáticas y Enfoques", "icon": "category", "range": "Preguntas 8 a 11"},
            {"id": "sec_4", "title": "Formatos y Franjas de Programación", "icon": "view_stream", "range": "Preguntas 12 a 18"},
            {"id": "sec_5", "title": "Nuevas Propuestas y Producción", "icon": "lightbulb", "range": "Preguntas 19 a 23"},
            {"id": "sec_6", "title": "Transformación y Visión de Futuro", "icon": "rocket_launch", "range": "Preguntas 24 a 28"}
        ],
        "questions": [
            # SECCIÓN 1
            {
                "id": "q_1",
                "number": 1,
                "section_id": "sec_1",
                "question": "¿Cuáles considera que son las principales fortalezas de Teleamiga?",
                "type": "multiple_choice",
                "max_selections": 3,
                "helper": "Seleccione máximo 3 opciones.",
                "options": [
                    "Credibilidad y confianza",
                    "Cercanía con la audiencia",
                    "Experiencia y trayectoria",
                    "Contenidos de servicio",
                    "Contenidos de fe y espiritualidad",
                    "Contenidos de salud y bienestar",
                    "Contenidos para el hogar",
                    "Talento humano",
                    "Capacidad de producción",
                    "Identidad propia"
                ],
                "has_other": True,
                "other_placeholder": "Especifique otra fortaleza..."
            },
            {
                "id": "q_2",
                "number": 2,
                "section_id": "sec_1",
                "question": "¿Qué debería conservar Teleamiga a toda costa en su programación?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta. Indique programas, valores o elementos clave.",
                "placeholder": "Escriba aquí lo que considera irrenunciable en el canal..."
            },
            {
                "id": "q_3",
                "number": 3,
                "section_id": "sec_1",
                "question": "¿Qué cree que le hace falta actualmente a Teleamiga?",
                "type": "multiple_choice",
                "max_selections": 3,
                "helper": "Seleccione máximo 3 opciones.",
                "options": [
                    "Más actualidad",
                    "Más entretenimiento",
                    "Más información",
                    "Más participación de la audiencia",
                    "Más contenidos para mujeres",
                    "Más contenidos para hombres",
                    "Más contenidos familiares",
                    "Más contenidos para públicos jóvenes",
                    "Más contenidos de servicio",
                    "Más producción propia",
                    "Más formatos novedosos",
                    "Más contenidos en exteriores",
                    "Más contenidos digitales / multiplataforma"
                ],
                "has_other": False
            },
            {
                "id": "q_4",
                "number": 4,
                "section_id": "sec_1",
                "question": "En una frase, ¿cómo describiría la Teleamiga que tenemos hoy?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "En una sola frase síntesis.",
                "placeholder": "La Teleamiga de hoy es..."
            },
            {
                "id": "q_5",
                "number": 5,
                "section_id": "sec_1",
                "question": "En una frase, ¿cómo le gustaría que fuera la Teleamiga que tendremos mañana?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "En una sola frase aspiracional.",
                "placeholder": "La Teleamiga del mañana debería ser..."
            },

            # SECCIÓN 2
            {
                "id": "q_6",
                "number": 6,
                "section_id": "sec_2",
                "question": "¿En qué momento del día cree que Teleamiga tiene mayor oportunidad de crecer o ampliar audiencia?",
                "type": "single_choice",
                "max_selections": 1,
                "helper": "Seleccione una franja horaria principal.",
                "options": [
                    "Madrugada",
                    "Mañana",
                    "Mediodía",
                    "Tarde",
                    "Noche"
                ],
                "has_other": False
            },
            {
                "id": "q_7",
                "number": 7,
                "section_id": "sec_2",
                "question": "Teniendo en cuenta que el grupo de mujeres mayores de 40 años son nuestro público principal, ¿qué otro público deberíamos atender?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Describa el perfil de audiencia al que deberíamos dirigir nuevos contenidos..."
            },

            # SECCIÓN 3
            {
                "id": "q_8",
                "number": 8,
                "section_id": "sec_3",
                "question": "¿Cuáles deberían ser los principales temas de Teleamiga durante los próximos años?",
                "type": "multiple_choice",
                "max_selections": 7,
                "helper": "Seleccione máximo 7 temas.",
                "options": [
                    "Salud y bienestar",
                    "Hogar",
                    "Familia",
                    "Fe y espiritualidad",
                    "Educación",
                    "Ciudadanía",
                    "Actualidad",
                    "Economía y finanzas personales",
                    "Emprendimiento",
                    "Trabajo",
                    "Cocina",
                    "Moda y belleza",
                    "Mascotas",
                    "Viajes y turismo",
                    "Cultura",
                    "Historias de vida",
                    "Ciencia y tecnología",
                    "Medio ambiente",
                    "Entretenimiento",
                    "Relaciones humanas",
                    "Adultos mayores",
                    "Juventud"
                ],
                "has_other": True,
                "other_placeholder": "Especifique otro tema..."
            },
            {
                "id": "q_9",
                "number": 9,
                "section_id": "sec_3",
                "question": "¿Qué tema cree que Teleamiga podría convertir en una verdadera especialidad?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Tema o nicho en el que el canal podría ser referente nacional..."
            },
            {
                "id": "q_10",
                "number": 10,
                "section_id": "sec_3",
                "question": "¿Qué tema cree que deberíamos explorar mucho más?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Tema con alto potencial poco explotado..."
            },
            {
                "id": "q_11",
                "number": 11,
                "section_id": "sec_3",
                "question": "¿Hay algún tema que hoy tenga demasiado peso en nuestra programación?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Temas o contenidos sobrecargados o repetitivos..."
            },

            # SECCIÓN 4
            {
                "id": "q_12",
                "number": 12,
                "section_id": "sec_4",
                "question": "¿Qué formatos considera que deberían tener mayor presencia en Teleamiga?",
                "type": "multiple_choice",
                "max_selections": 6,
                "helper": "Seleccione máximo 6 formatos.",
                "options": [
                    "Magazine",
                    "Entrevistas",
                    "Debate / conversación",
                    "Concurso",
                    "Historias de vida",
                    "Testimoniales",
                    "Reportajes",
                    "Documentales",
                    "Programas de servicio",
                    "Cocina",
                    "Tutoriales / aprendizaje",
                    "Consultorios",
                    "Programas de participación ciudadana",
                    "Programas de exteriores",
                    "Series documentales",
                    "Cápsulas"
                ],
                "has_other": False
            },
            {
                "id": "q_13",
                "number": 13,
                "section_id": "sec_4",
                "question": "¿Qué tipo de programa cree que podría funcionar especialmente bien en la mañana?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Propuesta o concepto para la franja de la mañana..."
            },
            {
                "id": "q_14",
                "number": 14,
                "section_id": "sec_4",
                "question": "¿Qué tipo de programa debería dominar la tarde?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Propuesta o concepto para la franja de la tarde..."
            },
            {
                "id": "q_15",
                "number": 15,
                "section_id": "sec_4",
                "question": "¿Qué debería ofrecer Teleamiga en la noche que hoy no está ofreciendo?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Contenidos nocturnos ideales..."
            },
            {
                "id": "q_16",
                "number": 16,
                "section_id": "sec_4",
                "question": "¿Qué debería conseguir principalmente la programación de la mañana?",
                "type": "multiple_choice",
                "max_selections": 3,
                "helper": "Seleccione máximo 3 objetivos.",
                "options": [
                    "Informar",
                    "Acompañar",
                    "Entretener",
                    "Enseñar",
                    "Prestar servicios",
                    "Generar participación",
                    "Inspirar",
                    "Orientar"
                ],
                "has_other": False
            },
            {
                "id": "q_17",
                "number": 17,
                "section_id": "sec_4",
                "question": "¿Qué debería conseguir principalmente la programación de la tarde?",
                "type": "multiple_choice",
                "max_selections": 3,
                "helper": "Seleccione máximo 3 objetivos.",
                "options": [
                    "Informar",
                    "Acompañar",
                    "Entretener",
                    "Enseñar",
                    "Prestar servicios",
                    "Generar participación",
                    "Inspirar",
                    "Orientar"
                ],
                "has_other": False
            },
            {
                "id": "q_18",
                "number": 18,
                "section_id": "sec_4",
                "question": "¿Qué debería conseguir principalmente la programación nocturna?",
                "type": "multiple_choice",
                "max_selections": 3,
                "helper": "Seleccione máximo 3 objetivos.",
                "options": [
                    "Informar",
                    "Acompañar",
                    "Entretener",
                    "Enseñar",
                    "Prestar servicios",
                    "Generar participación",
                    "Inspirar",
                    "Orientar"
                ],
                "has_other": False
            },

            # SECCIÓN 5
            {
                "id": "q_19",
                "number": 19,
                "section_id": "sec_5",
                "question": "Si Teleamiga pudiera estrenar mañana un programa completamente nuevo, ¿cómo sería ese programa?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Cuéntenos la idea en máximo 5 líneas.",
                "placeholder": "Describa nombre tentativo, temática, formato, tono y público objetivo..."
            },
            {
                "id": "q_20",
                "number": 20,
                "section_id": "sec_5",
                "question": "¿Qué programa que existe en otro canal, plataforma o medio cree que podría tener una versión Teleamiga?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Ej: Nombre del programa o canal de referencia y cómo se adaptaría..."
            },
            {
                "id": "q_21",
                "number": 21,
                "section_id": "sec_5",
                "question": "¿Qué programa cree que estamos en capacidad de producir y todavía no hemos intentado?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Ideas viables con el talento y recursos actuales..."
            },
            {
                "id": "q_22",
                "number": 22,
                "section_id": "sec_5",
                "question": "¿Qué tan importante considera que un programa pueda generar contenidos adicionales para otras emisiones, repeticiones o plataformas digitales?",
                "type": "single_choice",
                "max_selections": 1,
                "helper": "Seleccione el nivel de importancia.",
                "options": [
                    "Nada importante",
                    "Poco importante",
                    "Medianamente importante",
                    "Muy importante",
                    "Fundamental"
                ],
                "has_other": False
            },
            {
                "id": "q_23",
                "number": 23,
                "section_id": "sec_5",
                "question": "Ordene de mayor a menor según su importancia. Cuando imaginamos un nuevo programa, ¿qué deberíamos priorizar?",
                "type": "ranking",
                "max_selections": 7,
                "helper": "Asigne un número del 1 al 7 a cada factor (1 = Máxima prioridad, 7 = Menor prioridad).",
                "options": [
                    "Que sea atractivo para la audiencia",
                    "Que sea innovador",
                    "Que sea fácil de producir",
                    "Que pueda producirse en vivo",
                    "Que genere muchos contenidos reutilizables",
                    "Que pueda tener presencia digital",
                    "Que tenga potencial comercial"
                ],
                "has_other": False
            },

            # SECCIÓN 6
            {
                "id": "q_24",
                "number": 24,
                "section_id": "sec_6",
                "question": "Si usted pudiera cambiar UNA sola cosa de la parrilla actual, ¿qué cambiaría?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta puntual.",
                "placeholder": "El cambio principal sería..."
            },
            {
                "id": "q_25",
                "number": 25,
                "section_id": "sec_6",
                "question": "¿Qué programa o tipo de contenido cree que deberíamos transformar, reducir o dejar de hacer? ¿Por qué?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta honesta.",
                "placeholder": "Programa o contenido y justificación constructiva..."
            },
            {
                "id": "q_26",
                "number": 26,
                "section_id": "sec_6",
                "question": "¿Qué estamos haciendo hoy que deberíamos hacer MUCHO MÁS?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Prácticas o contenidos exitosos que merecen más espacio..."
            },
            {
                "id": "q_27",
                "number": 27,
                "section_id": "sec_6",
                "question": "¿Qué estamos haciendo hoy que deberíamos hacer DE OTRA MANERA?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Respuesta abierta.",
                "placeholder": "Procesos, dinámicas o enfoques a repensar..."
            },
            {
                "id": "q_28",
                "number": 28,
                "section_id": "sec_6",
                "question": "Si tuviera que proponer UNA SOLA idea para la nueva parrilla y supiera que realmente vamos a estudiarla, ¿cuál sería?",
                "type": "open_text",
                "max_selections": 1,
                "helper": "Su propuesta estrella para la nueva Teleamiga.",
                "placeholder": "Mi propuesta para la nueva parrilla es..."
            }
        ]
    }
