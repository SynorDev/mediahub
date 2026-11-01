@echo off
chcp 65001 >nul
title MediaHub - Agente de Renderizado GPU (Teleamiga Edicion)
color 0b

echo =====================================================================
echo       MEDIAHUB - AGENTE LOCAL DE RENDERIZADO TELEAMIGA
echo =====================================================================
echo.

:: 1. Si existe el ejecutable compilado nativo, lanzarlo inmediatamente
if exist "%~dp0MediaHubRenderAgent.exe" (
    echo Iniciando MediaHubRenderAgent.exe...
    echo Paquete autonomo: no requiere Python ni configuracion adicional.
    echo.
    "%~dp0MediaHubRenderAgent.exe"
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [AVISO] El agente se ha detenido.
        pause
    )
    exit /b
)

:: 2. Si no existe .exe compilado, intentar con Python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "%~dp0mediahub_render_agent.py"
    pause
    exit /b
)

echo [ERROR] No se encontro MediaHubRenderAgent.exe en esta carpeta.
echo Por favor vuelva a descargar el paquete completo desde MediaHub.
pause
