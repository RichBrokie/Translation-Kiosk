"""
Translation Kiosk — Main FastAPI Application
Serves Public Kiosk GUI (/), Admin Monitoring Panel (/admin),
WebSocket Audio Streaming Hub (/ws/audio, /ws/admin), and REST APIs.
"""
import os
import sys
import time
import json
import base64
import asyncio
import logging
from typing import Set, Dict, Any, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    SERVER_HOST,
    SERVER_PORT,
    WHISPER_BASE_URL,
    VLLM_BASE_URL,
    QWEN_MODEL_NAME,
    WINDOW_SEC,
    STRIDE_SEC,
    SAMPLE_RATE,
    get_language_name
)
from telemetry import TelemetryCollector, ChunkTelemetry
from whisper_client import WhisperClient
from qwen_client import QwenClient
from audio_pipeline import AudioPipeline, PipelineResult, pack_pcm_to_wav

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("translation_kiosk")

# Global Telemetry & Clients
telemetry = TelemetryCollector()
whisper_client = WhisperClient(base_url=WHISPER_BASE_URL, telemetry_collector=telemetry)
qwen_client = QwenClient(base_url=VLLM_BASE_URL, bypass_english=True, telemetry_collector=telemetry)

# Active Admin WebSocket Connections
admin_connections: Set[WebSocket] = set()

async def broadcast_admin(payload: Dict[str, Any]):
    """Broadcasts telemetry payload to all connected admin clients."""
    if not admin_connections:
        return
    dead = set()
    msg_str = json.dumps(payload)
    for ws in list(admin_connections):
        try:
            await ws.send_text(msg_str)
        except Exception:
            dead.add(ws)
    for ws in dead:
        admin_connections.discard(ws)

# Lifespan Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] Starting Translation Kiosk Service on port %d...", SERVER_PORT)
    await whisper_client.open()
    await qwen_client.open()
    
    # Background admin heartbeat task
    async def admin_heartbeat():
        while True:
            await asyncio.sleep(2.0)
            if admin_connections:
                try:
                    payload = telemetry.get_admin_telemetry_payload()
                    await broadcast_admin(payload)
                except Exception as e:
                    logger.debug("Admin heartbeat error: %s", e)

    heartbeat_task = asyncio.create_task(admin_heartbeat())
    yield
    logger.info("[*] Shutting down Translation Kiosk Service...")
    heartbeat_task.cancel()
    await whisper_client.close()
    await qwen_client.close()

# FastAPI App Setup
app = FastAPI(title="Translation Kiosk", lifespan=lifespan)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ============================================================================
# Page Routes (Public Kiosk & Admin Monitoring)
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def get_kiosk_view(request: Request):
    """Public Kiosk Touchscreen View (Port 8080 /)."""
    return templates.TemplateResponse(request=request, name="kiosk.html")

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_view(request: Request):
    """Admin Monitoring and Diagnostics Panel (Port 8080 /admin)."""
    return templates.TemplateResponse(request=request, name="admin.html")

# ============================================================================
# REST API Endpoints
# ============================================================================
@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint querying subsystem statuses."""
    stats = telemetry.get_summary_stats()
    return JSONResponse({
        "status": "healthy",
        "service": "translation_kiosk",
        "uptime_seconds": stats.get("uptime_seconds", 0),
        "whisper_status": "ok",
        "qwen_status": "ok",
        "total_chunks_processed": stats.get("total_chunks_processed", 0)
    })

@app.get("/api/config")
async def get_config():
    """Retrieves current runtime configuration."""
    return JSONResponse({
        "sample_rate": SAMPLE_RATE,
        "window_sec": WINDOW_SEC,
        "stride_sec": STRIDE_SEC,
        "whisper_url": whisper_client.transcribe_url,
        "qwen_url": qwen_client.completions_url,
        "qwen_model": qwen_client.model,
        "bypass_english": qwen_client.bypass_english
    })

@app.post("/api/config")
async def update_config(request: Request):
    """Updates runtime configuration settings."""
    try:
        body = await request.json()
        if "bypass_english" in body:
            qwen_client.bypass_english = bool(body["bypass_english"])
        return JSONResponse({"status": "updated", "config": body})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.get("/api/logs")
async def get_api_logs(limit: int = 50):
    """Fetches recent API interaction audit logs."""
    logs = [log.__dict__ for log in list(telemetry.api_logs)[-limit:]]
    return JSONResponse({"logs": logs})

@app.post("/api/test/audio_file")
@app.post("/api/simulate")
async def simulate_audio_file(file: UploadFile = File(...)):
    """
    Simulation / verification endpoint that processes an uploaded WAV file
    through the complete AudioPipeline and returns full transcription, translation, and latencies.
    """
    try:
        content = await file.read()
        # Parse WAV: if valid RIFF WAV, extract raw PCM (skip 44-byte header)
        if content.startswith(b"RIFF") and len(content) > 44:
            pcm_bytes = content[44:]
        else:
            pcm_bytes = content

        pipeline = AudioPipeline(
            whisper_client=whisper_client,
            qwen_client=qwen_client,
            telemetry_collector=telemetry
        )

        results = []
        chunk_size = 32000 * 2  # 2.0s chunks
        
        for i in range(0, len(pcm_bytes), chunk_size):
            slice_pcm = pcm_bytes[i:i + chunk_size]
            res = await pipeline.process_chunk(slice_pcm)
            if res:
                results.append(res)
                await broadcast_admin({
                    "type": "chunk_metrics",
                    "chunk_id": len(results),
                    "whisper_latency_ms": res.whisper_latency_ms,
                    "qwen_latency_ms": res.qwen_latency_ms,
                    "e2e_latency_ms": res.e2e_latency_ms,
                    "source_language": res.language,
                    "raw_text": res.raw_text,
                    "stitched_text": res.stitched_text,
                    "corrected_text": res.corrected_text,
                    "translated_text": res.translated_text
                })

        # Flush residual
        final_res = await pipeline.flush()
        if final_res:
            results.append(final_res)

        last_res = results[-1] if results else None

        return JSONResponse({
            "status": "success",
            "chunks_processed": len(results),
            "transcription": last_res.stitched_text if last_res else "",
            "translation": last_res.translated_text if last_res else "",
            "language": last_res.language if last_res else "en",
            "language_name": last_res.language_name if last_res else "English",
            "is_english": last_res.is_english if last_res else False,
            "whisper_latency_ms": last_res.whisper_latency_ms if last_res else 0.0,
            "qwen_latency_ms": last_res.qwen_latency_ms if last_res else 0.0,
            "e2e_latency_ms": last_res.e2e_latency_ms if last_res else 0.0
        })
    except Exception as e:
        logger.exception("Error during audio simulation: %s", e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ============================================================================
# WebSocket Hub: /ws/audio (Client Microphone Stream)
# ============================================================================
@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """
    Bi-directional streaming WebSocket for Kiosk clients.
    Ingests 16kHz PCM audio frames, executes pipeline, and returns real-time transcription and translation updates.
    """
    await websocket.accept()
    logger.info("[WS/Audio] New client connected from %s", websocket.client)

    pipeline = AudioPipeline(
        whisper_client=whisper_client,
        qwen_client=qwen_client,
        telemetry_collector=telemetry
    )
    chunk_counter = 0

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            pcm_bytes = b""

            if "bytes" in message and message["bytes"]:
                pcm_bytes = message["bytes"]
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")
                    
                    if msg_type == "session_start":
                        pipeline.reset()
                        chunk_counter = 0
                        await websocket.send_json({
                            "type": "status_update",
                            "status": "recording",
                            "message": "Session started. Listening..."
                        })
                        continue
                    elif msg_type == "session_stop":
                        # Flush pipeline on stop
                        final_res = await pipeline.flush()
                        if final_res and (final_res.stitched_text or final_res.translated_text):
                            chunk_counter += 1
                            await websocket.send_json({
                                "type": "transcription_update",
                                "chunk_id": chunk_counter,
                                "text": final_res.stitched_text,
                                "is_final": True
                            })
                            await websocket.send_json({
                                "type": "translation_update",
                                "chunk_id": chunk_counter,
                                "source_text": final_res.stitched_text,
                                "translation": final_res.translated_text,
                                "latency_ms": final_res.qwen_latency_ms,
                                "whisper_latency_ms": final_res.whisper_latency_ms,
                                "e2e_latency_ms": final_res.e2e_latency_ms,
                                "bypass_llm": final_res.is_english,
                                "is_final": True
                            })
                        await websocket.send_json({
                            "type": "status_update",
                            "status": "idle",
                            "message": "Session finalized."
                        })
                        continue
                    elif msg_type == "reset":
                        pipeline.reset()
                        chunk_counter = 0
                        continue
                    elif msg_type == "audio_chunk":
                        raw_b64 = payload.get("audio_data", "")
                        if raw_b64:
                            pcm_bytes = base64.b64decode(raw_b64)
                except json.JSONDecodeError:
                    pass

            if not pcm_bytes:
                continue

            # Process PCM audio through sliding window pipeline
            res = await pipeline.process_chunk(pcm_bytes)
            if res:
                chunk_counter += 1
                
                # 1. Language detection notification
                await websocket.send_json({
                    "type": "language_detected",
                    "language_code": res.language,
                    "language_name": res.language_name
                })

                # 2. Live transcription update
                await websocket.send_json({
                    "type": "transcription_update",
                    "chunk_id": chunk_counter,
                    "text": res.stitched_text or res.window_text,
                    "raw_chunk_text": res.raw_text,
                    "corrected_text": res.corrected_text,
                    "is_final": res.is_final
                })

                # 3. English translation update
                await websocket.send_json({
                    "type": "translation_update",
                    "chunk_id": chunk_counter,
                    "source_text": res.stitched_text or res.window_text,
                    "translation": res.translated_text,
                    "latency_ms": res.qwen_latency_ms,
                    "whisper_latency_ms": res.whisper_latency_ms,
                    "e2e_latency_ms": res.e2e_latency_ms,
                    "bypass_llm": res.is_english,
                    "is_final": res.is_final
                })

                # 4. Broadcast live telemetry to admin dashboards
                await broadcast_admin({
                    "type": "chunk_metrics",
                    "chunk_id": chunk_counter,
                    "whisper_latency_ms": res.whisper_latency_ms,
                    "qwen_latency_ms": res.qwen_latency_ms,
                    "e2e_latency_ms": res.e2e_latency_ms,
                    "source_language": res.language,
                    "naive_text": res.raw_text,
                    "sliding_window_text": res.stitched_text or res.window_text,
                    "corrected_text": res.corrected_text,
                    "translated_text": res.translated_text,
                    "repairs_count": res.repairs_detected
                })

    except (WebSocketDisconnect, RuntimeError):
        logger.info("[WS/Audio] Client disconnected.")
    except Exception as e:
        logger.exception("[WS/Audio] Error in audio websocket: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

# ============================================================================
# WebSocket Hub: /ws/admin (Telemetry Diagnostics Stream)
# ============================================================================
@app.websocket("/ws/admin")
async def websocket_admin_endpoint(websocket: WebSocket):
    """
    Real-time telemetry and diagnostics stream for the Admin Dashboard.
    """
    await websocket.accept()
    admin_connections.add(websocket)
    logger.info("[WS/Admin] New admin connected. Total active: %d", len(admin_connections))

    try:
        # Immediately send current state snapshot
        initial_payload = telemetry.get_admin_telemetry_payload()
        await websocket.send_json(initial_payload)

        while True:
            # Keep connection open and receive admin commands
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("type") == "reset":
                    telemetry.reset()
                    await websocket.send_json(telemetry.get_admin_telemetry_payload())
            except Exception:
                pass
    except (WebSocketDisconnect, RuntimeError):
        admin_connections.discard(websocket)
        logger.info("[WS/Admin] Admin disconnected. Remaining: %d", len(admin_connections))
    except Exception as e:
        admin_connections.discard(websocket)
        logger.exception("[WS/Admin] Error: %s", e)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info",
        access_log=True
    )