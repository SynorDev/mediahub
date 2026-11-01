@echo off
chcp 65001 >nul
title Compilador a .EXE - MediaHub Render Agent
color 0a

echo =====================================================================
echo    COMPILANDO AGENTE LOCAL DE RENDERIZADO A EJECUTABLE AUTONOMO
echo =====================================================================
echo.

where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

echo Generando MediaHubRenderAgent.exe (Standalone)...
pyinstaller --noconfirm --onedir --windowed --name "MediaHubRenderAgent" ^
    --add-data "mediahub_render_agent.py;." ^
    --hidden-import "uvicorn" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.filedialog" ^
    "%~dp0mediahub_render_agent.py"

echo.
echo Compilación terminada. Revisa la carpeta dist/
pause
