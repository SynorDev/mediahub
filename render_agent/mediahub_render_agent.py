"""
MediaHub - Agente Local de Renderizado GPU (Teleamiga Edición)
Servidor de renderizado asíncrono con aceleración por hardware Nvidia (NVENC)
y sincronización de mosca en cola con cortinilla de cierre.
"""

import os
import sys
import json
import asyncio
import shutil
import subprocess
import re
from typing import Optional, Dict, Any, List

# Reconfigurar stdout/stderr en Windows a UTF-8 seguro para evitar UnicodeEncodeError con emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Inicialización de la aplicación FastAPI
app = FastAPI(title="MediaHub Render Agent", version="1.0.0")

# Configuración CORS permisiva para comunicación local con MediaHub Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para navegadores basados en Chromium (Private Network Access)
@app.middleware("http")
async def add_private_network_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


# ==============================================================================
# GESTOR DE CONEXIONES WEBSOCKET
# ==============================================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()


# ==============================================================================
# ESTADO GLOBAL DEL RENDERIZADOR
# ==============================================================================
class RenderState:
    def __init__(self):
        self.is_rendering: bool = False
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.progress_data: Dict[str, Any] = {
            "percent": 0.0,
            "fps": 0.0,
            "frame": 0,
            "speed": "0x",
            "time": "00:00:00",
            "eta_seconds": 0,
            "status": "idle"
        }
        self.last_log: str = ""
        self.cancel_requested: bool = False

render_state = RenderState()


# ==============================================================================
# UTILIDADES DE HARDWARE & FFMPEG
# ==============================================================================
def find_binary(name: str) -> Optional[str]:
    """Busca un binario en la carpeta del ejecutable, PATH o ubicaciones típicas de Windows."""
    dirs_to_check = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        dirs_to_check.append(exe_dir)
        dirs_to_check.append(os.path.join(exe_dir, "bin"))
        if hasattr(sys, '_MEIPASS'):
            dirs_to_check.append(sys._MEIPASS)
            dirs_to_check.append(os.path.join(sys._MEIPASS, "bin"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dirs_to_check.append(script_dir)
    dirs_to_check.append(os.path.join(script_dir, "bin"))
    
    for d in dirs_to_check:
        candidate = os.path.join(d, f"{name}.exe")
        if os.path.isfile(candidate):
            return candidate

    found = shutil.which(name)
    if found:
        return found

    common_paths = [
        f"C:\\ffmpeg\\bin\\{name}.exe",
        f"C:\\ffmpeg\\{name}.exe",
        f"C:\\Program Files\\ffmpeg\\bin\\{name}.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None

FFMPEG_PATH = find_binary("ffmpeg") or "ffmpeg"
FFPROBE_PATH = find_binary("ffprobe") or "ffprobe"

def get_gpu_info() -> Dict[str, Any]:
    """Detecta la GPU Nvidia y soporte de NVENC."""
    gpu_name = "No detectada"
    driver_version = ""
    nvenc_available = False

    # 1. Detectar modelo de GPU vía nvidia-smi
    smi = shutil.which("nvidia-smi") or "C:\\WINDOWS\\system32\\nvidia-smi.exe"
    if os.path.isfile(smi):
        try:
            res = subprocess.run(
                [smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                gpu_name = parts[0]
                if len(parts) > 1:
                    driver_version = parts[1]
        except Exception:
            pass

    # 2. Verificar encoder h264_nvenc en FFmpeg
    try:
        res = subprocess.run([FFMPEG_PATH, "-encoders"], capture_output=True, text=True, timeout=5)
        if "h264_nvenc" in res.stdout:
            nvenc_available = True
    except Exception:
        nvenc_available = False

    return {
        "gpu_name": gpu_name,
        "driver_version": driver_version,
        "nvenc_available": nvenc_available,
        "ffmpeg_path": FFMPEG_PATH,
        "ffprobe_path": FFPROBE_PATH
    }


def probe_media(filepath: str) -> Dict[str, Any]:
    """Obtiene metadata precisa de duración, resolución y audio usando ffprobe."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate,duration",
        "-of", "json",
        filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error al analizar archivo con ffprobe: {res.stderr}")

    data = json.loads(res.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    duration = float(fmt.get("duration") or 0.0)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(s.get("codec_type") == "video" for s in streams)

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    width = int(video_stream.get("width") or 1920)
    height = int(video_stream.get("height") or 1080)

    # Si la duración del formato es 0, buscar en el stream de video
    if duration <= 0 and video_stream.get("duration"):
        try:
            duration = float(video_stream["duration"])
        except ValueError:
            duration = 0.0

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
        "has_video": has_video,
        "filepath": filepath
    }


# ==============================================================================
# EXPLORADOR DE ARCHIVOS NATIVO DE WINDOWS (WIN32 COMDLG32 - CTYPES)
# ==============================================================================
import ctypes
from ctypes import wintypes

class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", wintypes.LPVOID),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", wintypes.LPVOID),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]

def _native_browse_file(title: str, filetypes: Any = None) -> str:
    """Abre el diálogo nativo de Windows (comdlg32) para seleccionar archivo."""
    OFN_EXPLORER = 0x00080000
    OFN_FILEMUSTEXIST = 0x00001000
    OFN_PATHMUSTEXIST = 0x00000800

    buffer = ctypes.create_unicode_buffer(4096)
    filter_str = "Archivos de Video (*.mp4;*.mov;*.mkv;*.avi;*.mxf)\0*.mp4;*.mov;*.mkv;*.avi;*.mxf\0Todos los archivos (*.*)\0*.*\0\0"

    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    try:
        ofn.hwndOwner = ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        ofn.hwndOwner = 0
    ofn.lpstrFilter = filter_str
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = 4096
    ofn.lpstrTitle = title or "Seleccionar archivo"
    ofn.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST

    try:
        success = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn))
        if success:
            path = buffer.value.strip()
            print(f" [EXPLORADOR] Archivo seleccionado: {path}")
            return path
    except Exception as e:
        print(f" [ERROR EXPLORADOR]: {e}")
    return ""

def _native_browse_save(title: str, defaultextension: str = ".mp4", filetypes: Any = None) -> str:
    """Abre el diálogo nativo de Windows (comdlg32) para guardar archivo."""
    OFN_EXPLORER = 0x00080000
    OFN_PATHMUSTEXIST = 0x00000800
    OFN_OVERWRITEPROMPT = 0x00000002

    buffer = ctypes.create_unicode_buffer(4096)
    filter_str = "Video MP4 (*.mp4)\0*.mp4\0Video QuickTime (*.mov)\0*.mov\0Todos los archivos (*.*)\0*.*\0\0"

    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    try:
        ofn.hwndOwner = ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        ofn.hwndOwner = 0
    ofn.lpstrFilter = filter_str
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = 4096
    ofn.lpstrTitle = title or "Guardar como..."
    ofn.Flags = OFN_EXPLORER | OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT
    ofn.lpstrDefExt = (defaultextension or ".mp4").lstrip(".")

    try:
        success = ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn))
        if success:
            path = buffer.value.strip()
            print(f" [EXPLORADOR] Destino seleccionado: {path}")
            return path
    except Exception as e:
        print(f" [ERROR EXPLORADOR]: {e}")
    return ""


# ==============================================================================
# MODELOS DE PETICIÓN
# ==============================================================================
class BrowseRequest(BaseModel):
    title: Optional[str] = "Seleccionar archivo"
    mode: Optional[str] = "open" # "open" o "save"
    defaultextension: Optional[str] = ".mp4"

class RenderRequest(BaseModel):
    base_path: str
    mosca_path: str
    cierre_path: str
    output_path: str
    preset: Optional[str] = "p4"       # Preset NVENC (p1..p7 o hq/medium)
    bitrate: Optional[str] = "15M"     # Bitrate de salida
    use_nvenc: Optional[bool] = True   # Usar NVENC si está disponible


# ==============================================================================
# ENDPOINTS REST
# ==============================================================================
@app.get("/health")
async def health():
    """Reporta el estado del agente y los detalles del hardware local."""
    gpu = get_gpu_info()
    return {
        "status": "online",
        "agent": "MediaHub Local Render Agent",
        "version": "1.0.0",
        "gpu": gpu,
        "is_rendering": render_state.is_rendering,
        "progress": render_state.progress_data
    }


@app.post("/browse-file")
async def browse_file_endpoint(req: BrowseRequest):
    """Abre el explorador nativo de Windows en la estación de edición."""
    filetypes = [
        ("Videos soportados (*.mp4, *.mov, *.mkv, *.avi)", "*.mp4;*.mov;*.mkv;*.avi"),
        ("Todos los archivos", "*.*")
    ]
    try:
        path = await asyncio.to_thread(_native_browse_file, req.title or "Seleccionar archivo", filetypes)
        return {"filepath": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/browse-save")
async def browse_save_endpoint(req: BrowseRequest):
    """Abre el explorador nativo de Windows para definir el archivo de salida."""
    filetypes = [
        ("Video MP4 (*.mp4)", "*.mp4"),
        ("Video QuickTime (*.mov)", "*.mov"),
        ("Todos los archivos", "*.*")
    ]
    try:
        path = await asyncio.to_thread(_native_browse_save, req.title or "Guardar como...", req.defaultextension or ".mp4", filetypes)
        return {"filepath": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cancel")
async def cancel_render():
    """Cancela el proceso de renderizado actual."""
    if not render_state.is_rendering or not render_state.current_process:
        return {"status": "no_render_active"}
    
    render_state.cancel_requested = True
    try:
        render_state.current_process.terminate()
        await manager.broadcast({
            "type": "log",
            "message": "⚠️ Solicitud de cancelación enviada al proceso FFmpeg."
        })
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "cancelling"}


# ==============================================================================
# MOTOR ASÍNCRONO DE RENDERIZADO CON FFMPEG
# ==============================================================================
async def execute_render_pipeline(req: RenderRequest):
    """Ejecuta el procesamiento de video con sincronización de cola y aceleración NVENC."""
    render_state.is_rendering = True
    render_state.cancel_requested = False
    render_state.progress_data = {
        "percent": 0.0,
        "fps": 0.0,
        "frame": 0,
        "speed": "0x",
        "time": "00:00:00",
        "eta_seconds": 0,
        "status": "starting"
    }

    await manager.broadcast({"type": "status", "data": render_state.progress_data})
    await manager.broadcast({"type": "log", "message": "🚀 Iniciando pipeline de renderizado MediaHub..."})

    try:
        # Limpieza de rutas (remover comillas que el usuario pueda pegar)
        req.base_path = req.base_path.strip().strip('"').strip("'")
        req.mosca_path = req.mosca_path.strip().strip('"').strip("'")
        req.cierre_path = req.cierre_path.strip().strip('"').strip("'")
        req.output_path = req.output_path.strip().strip('"').strip("'")

        print("\n" + "=" * 65)
        print(" [MEDIAHUB] >> NUEVA ORDEN DE RENDERIZADO RECIBIDA")
        print(f" * Video Base:   {req.base_path}")
        print(f" * Mosca Alpha:  {req.mosca_path}")
        print(f" * Cortinilla:   {req.cierre_path}")
        print(f" * Exportar en:  {req.output_path}")
        print("=" * 65)

        # 1. Validar existencia de archivos
        for label, p in [("Video Base", req.base_path), ("Mosca", req.mosca_path), ("Cierre", req.cierre_path)]:
            if not os.path.isfile(p):
                err_msg = f"{label} no encontrado en la ruta: {p}"
                print(f" ❌ ERROR: {err_msg}")
                raise FileNotFoundError(err_msg)

        # Asegurar directorio de salida
        out_dir = os.path.dirname(os.path.abspath(req.output_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # 2. Análisis con ffprobe
        print(" 🔍 Analizando metadatos con FFprobe...")
        await manager.broadcast({"type": "log", "message": "🔍 Analizando metadatos de los clips con FFprobe..."})
        info_base = await asyncio.to_thread(probe_media, req.base_path)
        info_mosca = await asyncio.to_thread(probe_media, req.mosca_path)
        info_cierre = await asyncio.to_thread(probe_media, req.cierre_path)

        d_base = info_base["duration"]
        d_mosca = info_mosca["duration"]
        d_cierre = info_cierre["duration"]

        if d_base <= 0:
            raise ValueError("No se pudo determinar la duración del video base.")
        if d_mosca <= 0:
            raise ValueError("No se pudo determinar la duración del clip de la mosca.")
        if d_cierre <= 0:
            raise ValueError("No se pudo determinar la duración de la cortinilla de cierre.")

        total_duration = d_base + d_cierre

        # 3. Cálculo matemático de Sincronización de Cola (Tail Alignment)
        # Para que el último frame de la mosca coincida exactamente con el último frame del video base:
        # offset = (D_m - (D_b % D_m)) % D_m
        rem = d_base % d_mosca
        offset = (d_mosca - rem) % d_mosca

        print(f" ⏱️ Duraciones: Base={d_base:.2f}s | Mosca={d_mosca:.2f}s | Cierre={d_cierre:.2f}s | Total={total_duration:.2f}s")
        print(f" 🎯 Offset calculado para sincronización de mosca: {offset:.3f}s")

        await manager.broadcast({
            "type": "log",
            "message": f"⏱️ Duraciones calculadas: Base={d_base:.2f}s | Mosca={d_mosca:.2f}s | Cierre={d_cierre:.2f}s | Total={total_duration:.2f}s"
        })
        await manager.broadcast({
            "type": "log",
            "message": f"🎯 Offset de alineación de cola para la mosca: {offset:.3f}s"
        })

        # 4. Construcción del -filter_complex
        # Input 0: base_path
        # Input 1: mosca_path (bucle continuo con -stream_loop -1)
        # Input 2: cierre_path
        #
        # Alinear mosca: aplicamos trim=start=offset:duration=d_base,setpts=PTS-STARTPTS
        # Overlay: base + mosca
        # Normalización: video a 1920x1080 30fps yuv420p, audio stereo 48kHz
        # Concat: base_con_mosca + cierre
        
        has_base_audio = info_base["has_audio"]
        has_cierre_audio = info_cierre["has_audio"]

        filter_parts = []

        # Recorte y alineación de la mosca
        filter_parts.append(f"[1:v] trim=start={offset:.4f}:duration={d_base:.4f},setpts=PTS-STARTPTS [mosca_aligned]")
        filter_parts.append("[0:v][mosca_aligned] overlay=0:0:shortest=1 [v_base_raw]")

        # Normalización video base
        filter_parts.append("[v_base_raw] scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p [v0]")

        # Normalización video cierre
        filter_parts.append("[2:v] scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p [v1]")

        # Normalización de audios
        if has_base_audio:
            filter_parts.append("[0:a] aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo [a0]")
        else:
            filter_parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d_base:.4f} [a0]")

        if has_cierre_audio:
            filter_parts.append("[2:a] aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo [a1]")
        else:
            filter_parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d_cierre:.4f} [a1]")

        # Concatenación final
        filter_parts.append("[v0][a0][v1][a1] concat=n=2:v=1:a=1 [vout][aout]")

        filter_complex_str = "; ".join(filter_parts)

        # 5. Comprobación de Aceleración por Hardware (Quadro P2000 / NVENC)
        gpu = get_gpu_info()
        use_nvenc = req.use_nvenc and gpu["nvenc_available"]

        codec_args = []
        if use_nvenc:
            await manager.broadcast({
                "type": "log",
                "message": f"⚡ Utilizando codificación por hardware NVIDIA NVENC ({gpu['gpu_name']})."
            })
            codec_args = [
                "-c:v", "h264_nvenc",
                "-preset", req.preset or "p4",
                "-rc", "vbr",
                "-cq", "19",
                "-b:v", req.bitrate or "15M",
                "-maxrate", "25M",
                "-bufsize", "30M",
                "-pix_fmt", "yuv420p"
            ]
        else:
            await manager.broadcast({
                "type": "log",
                "message": "⚠️ NVENC no disponible o desactivado. Empleando codificador por software libx264."
            })
            codec_args = [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "19",
                "-pix_fmt", "yuv420p"
            ]

        audio_codec_args = [
            "-c:a", "aac",
            "-b:a", "192k"
        ]

        # 6. Ensamblaje del comando FFmpeg completo
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", req.base_path,
            "-stream_loop", "-1",
            "-i", req.mosca_path,
            "-i", req.cierre_path,
            "-filter_complex", filter_complex_str,
            "-map", "[vout]",
            "-map", "[aout]",
            *codec_args,
            *audio_codec_args,
            "-progress", "pipe:1",
            req.output_path
        ]

        await manager.broadcast({
            "type": "log",
            "message": f"🎬 Comando FFmpeg generado. Lanzando subproceso..."
        })
        print(f" 🎬 Lanzando FFmpeg con encoder: {'h264_nvenc (NVIDIA)' if use_nvenc else 'libx264 (CPU)'}...")

        # 7. Ejecutar proceso asíncrono y monitorizar progreso
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        render_state.current_process = proc
        render_state.progress_data["status"] = "rendering"

        # Tarea en paralelo para capturar stderr (mensajes informativos de ffmpeg)
        async def read_stderr(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="ignore").strip()
                if decoded and not decoded.startswith("frame="):
                    # Solo emitir líneas significativas
                    if any(k in decoded.lower() for k in ["error", "warning", "opening", "input", "output", "stream"]):
                        await manager.broadcast({"type": "log", "message": f"[FFmpeg] {decoded}"})

        stderr_task = asyncio.create_task(read_stderr(proc.stderr))

        # Lectura de stdout (-progress pipe:1) para métricas en tiempo real
        current_metrics = {
            "frame": 0,
            "fps": 0.0,
            "speed": "0x",
            "out_time_ms": 0,
            "out_time": "00:00:00"
        }

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            if "=" in text:
                k, v = text.split("=", 1)
                k = k.strip()
                v = v.strip()

                if k == "frame":
                    try: current_metrics["frame"] = int(v)
                    except ValueError: pass
                elif k == "fps":
                    try: current_metrics["fps"] = float(v)
                    except ValueError: pass
                elif k == "speed":
                    current_metrics["speed"] = v
                elif k == "out_time":
                    current_metrics["out_time"] = v.split(".")[0]
                elif k == "out_time_ms":
                    try:
                        ms = int(v)
                        current_metrics["out_time_ms"] = ms
                    except ValueError: pass
                elif k == "progress":
                    # Calcular porcentaje y ETA
                    current_seconds = current_metrics["out_time_ms"] / 1000000.0
                    percent = min(100.0, max(0.0, (current_seconds / total_duration) * 100.0))

                    speed_num = 1.0
                    if "x" in current_metrics["speed"]:
                        try: speed_num = float(current_metrics["speed"].replace("x", ""))
                        except ValueError: speed_num = 1.0

                    eta_sec = int(max(0.0, (total_duration - current_seconds) / max(0.1, speed_num)))

                    render_state.progress_data.update({
                        "percent": round(percent, 1),
                        "fps": current_metrics["fps"],
                        "frame": current_metrics["frame"],
                        "speed": current_metrics["speed"],
                        "time": current_metrics["out_time"],
                        "eta_seconds": eta_sec,
                        "status": "rendering"
                    })

                    print(f"\r >> RENDERIZANDO: {percent:.1f}% | FPS: {current_metrics['fps']:.1f} | Speed: {current_metrics['speed']} | Tiempo: {current_metrics['out_time']}", end="", flush=True)

                    await manager.broadcast({
                        "type": "progress",
                        **render_state.progress_data
                    })

                    if v == "end":
                        break

        await proc.wait()
        await stderr_task

        if render_state.cancel_requested:
            render_state.progress_data["status"] = "cancelled"
            print("\n 🛑 Renderizado cancelado por el usuario.\n")
            await manager.broadcast({"type": "log", "message": "🛑 Renderizado cancelado por el usuario."})
            await manager.broadcast({"type": "status", "data": render_state.progress_data})
            if os.path.exists(req.output_path):
                try: os.remove(req.output_path)
                except Exception: pass
            return

        if proc.returncode != 0:
            err_msg = f"FFmpeg finalizó con código de error {proc.returncode}."
            print(f"\n ❌ ERROR: {err_msg}\n")
            render_state.progress_data["status"] = "error"
            await manager.broadcast({"type": "error", "message": err_msg})
            await manager.broadcast({"type": "status", "data": render_state.progress_data})
            return

        # Render completado exitosamente
        render_state.progress_data.update({
            "percent": 100.0,
            "status": "completed",
            "eta_seconds": 0
        })

        file_size_mb = 0.0
        if os.path.exists(req.output_path):
            file_size_mb = round(os.path.getsize(req.output_path) / (1024 * 1024), 2)

        print(f"\n\n 🎉 ¡RENDERIZADO COMPLETADO CON ÉXITO!")
        print(f" * Archivo final: {req.output_path} ({file_size_mb} MB)\n")

        await manager.broadcast({
            "type": "complete",
            "output_path": req.output_path,
            "duration": total_duration,
            "size_mb": file_size_mb
        })
        await manager.broadcast({
            "type": "log",
            "message": f"🎉 ¡Renderizado completado con éxito! Archivo exportado: {req.output_path} ({file_size_mb} MB)"
        })

    except Exception as e:
        print(f"\n ❌ ERROR EN RENDER: {str(e)}\n")
        render_state.progress_data["status"] = "error"
        await manager.broadcast({"type": "error", "message": str(e)})
        await manager.broadcast({"type": "log", "message": f"❌ Error: {str(e)}"})
    finally:
        render_state.is_rendering = False
        render_state.current_process = None


@app.post("/render")
async def start_render_endpoint(req: RenderRequest):
    """Inicia el pipeline de renderizado en segundo plano."""
    if render_state.is_rendering:
        raise HTTPException(status_code=400, detail="Ya hay un renderizado en curso en esta estación.")
    
    # Lanzar pipeline asíncrono
    asyncio.create_task(execute_render_pipeline(req))
    return {"status": "started", "message": "Renderizado iniciado."}


# ==============================================================================
# WEBSOCKET ENDPOINT
# ==============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Enviar estado actual al conectarse
    await websocket.send_json({
        "type": "init",
        "gpu": get_gpu_info(),
        "is_rendering": render_state.is_rendering,
        "progress": render_state.progress_data
    })
    try:
        while True:
            data = await websocket.receive_text()
            # Si el cliente web envía 'ping', respondemos 'pong'
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ==============================================================================
# INICIO DEL SERVICIO
# ==============================================================================
def main():
    print("=" * 70)
    print(" MEDIAHUB - AGENTE LOCAL DE RENDERIZADO GPU (TELEAMIGA)")
    print("=" * 70)
    gpu = get_gpu_info()
    print(f" * GPU Detectada: {gpu['gpu_name']}")
    if gpu['driver_version']:
        print(f" * Driver NVIDIA: {gpu['driver_version']}")
    print(f" * Aceleración NVENC: {'DISPONIBLE (Óptimo)' if gpu['nvenc_available'] else 'NO DETECTADA (Software Fallback)'}")
    print(f" * Servidor escuchando en: http://127.0.0.1:18500 (y red local)")
    print("=" * 70)
    print("Mantenga esta ventana abierta durante sus sesiones de renderizado.")
    print("Para cerrar el agente presione Ctrl + C.")
    print("-" * 70)

    uvicorn.run(app, host="0.0.0.0", port=18500, log_level="warning")

if __name__ == "__main__":
    main()
