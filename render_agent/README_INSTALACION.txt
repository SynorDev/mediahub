========================================================================
   MEDIAHUB - CLIENTE LOCAL DE RENDERIZADO GPU (TELEAMIGA EDICION)
========================================================================

Este agente puente permite a los editores de Teleamiga procesar videos
utilizando la potencia de la tarjeta gráfica NVIDIA (ej. Quadro P2000 o RTX)
directamente desde su estación de trabajo, comunicándose en tiempo real con
la plataforma web de MediaHub.

INSTRUCCIONES DE USO:
------------------------------------------------------------------------
1. Descomprime esta carpeta en tu estación de trabajo (ej. C:\MediaHubClient\ o en tu Escritorio).
2. Haz doble clic en "Iniciar_Agente_Render.bat".
3. Aparecerá una ventana de consola indicando que el agente está activo en:
   http://127.0.0.1:18500
4. Ve a MediaHub en tu navegador (Módulo de Herramientas -> Motor de Renderizado).
5. La página web detectará automáticamente tu equipo y verás el indicador en VERDE:
   "Conectado a la Estación de Edición Local - NVIDIA GPU NVENC Activo".
6. Carga tus videos haciendo clic en "Examinar en mi PC" (se abrirá la ventana de Windows)
   y pulsa "Iniciar Renderizado por Hardware".

REQUISITOS DEL SISTEMA:
------------------------------------------------------------------------
- Windows 10 o Windows 11 (64 bits).
- Tarjeta Gráfica NVIDIA con drivers actualizados (Quadro P2000, RTX, GTX).
- FFmpeg instalado (disponible en C:\ffmpeg\bin\ffmpeg.exe o en la variable PATH).
- Python 3.9+ instalado en la máquina (en caso de ejecutar vía .bat).

SOPORTE:
------------------------------------------------------------------------
Departamento de Sistemas & Ingeniería - Teleamiga.
