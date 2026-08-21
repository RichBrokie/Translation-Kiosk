"""
Integration and regression test suite for Translation Kiosk FastAPI server (main.py).
Tests REST routes, static file delivery, template rendering, simulation endpoints, and WebSockets.
"""
import io
import wave
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app, whisper_client, qwen_client, telemetry
from whisper_client import TranscriptionResult
from qwen_client import TranslationResult

client = TestClient(app)

def create_dummy_wav(duration_s: float = 4.0, sample_rate: int = 16000) -> bytes:
    """Creates in-memory valid PCM WAV audio."""
    num_samples = int(duration_s * sample_rate)
    pcm = b"\x00\x00" * num_samples
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return bio.getvalue()

def test_kiosk_public_view_html():
    """GET / renders kiosk.html with 200 OK and expected HTML elements."""
    response = client.get("/")
    assert response.status_code == 200
    assert "TRANSLATION KIOSK" in response.text
    assert "btn-master" in response.text
    assert "/static/css/kiosk.css" in response.text
    assert "/static/js/kiosk.js" in response.text

def test_admin_monitoring_view_html():
    """GET /admin renders admin.html with 200 OK and diagnostic gauges."""
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Translation Kiosk Diagnostics" in response.text
    assert "gauge-whisper-bar" in response.text
    assert "gauge-qwen-bar" in response.text
    assert "/static/css/admin.css" in response.text
    assert "/static/js/admin.js" in response.text

def test_health_endpoints():
    """GET /health and GET /api/health return healthy status and telemetry."""
    for path in ["/health", "/api/health"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "translation_kiosk"
        assert "uptime_seconds" in data

def test_config_endpoints():
    """GET /api/config and POST /api/config get and update parameters."""
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["sample_rate"] == 16000
    assert data["bypass_english"] is True

    update_res = client.post("/api/config", json={"bypass_english": False})
    assert update_res.status_code == 200
    assert qwen_client.bypass_english is False

    # Restore
    client.post("/api/config", json={"bypass_english": True})
    assert qwen_client.bypass_english is True

def test_api_logs_endpoint():
    """GET /api/logs returns list of recent API interactions."""
    telemetry.log_api_call(
        endpoint="http://localhost:8001/transcribe",
        method="POST",
        status_code=200,
        latency_ms=120.0,
        payload_summary="test wav",
        response_summary="[es] hola"
    )
    res = client.get("/api/logs?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "logs" in data
    assert len(data["logs"]) >= 1

def test_audio_simulation_endpoint():
    """POST /api/test/audio_file processes uploaded WAV audio."""
    wav_bytes = create_dummy_wav(duration_s=4.0)

    with patch.object(whisper_client, "transcribe_wav", new_callable=AsyncMock) as mock_w, \
         patch.object(qwen_client, "post_correct_and_translate", new_callable=AsyncMock) as mock_q:
        
        mock_w.return_value = TranscriptionResult(
            text="Buenos dias amigos",
            language="es",
            latency_ms=150.0
        )
        mock_q.return_value = TranslationResult(
            corrected_text="Buenos días, amigos.",
            english_translation="Good morning, friends.",
            source_language="es",
            latency_ms=450.0
        )

        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        res = client.post("/api/test/audio_file", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "Buenos" in data["transcription"]
        assert "Good morning" in data["translation"]
        assert data["language"] == "es"

def test_websocket_admin_telemetry():
    """WebSocket /ws/admin connects and receives telemetry snapshot."""
    with client.websocket_connect("/ws/admin") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "admin_telemetry"
        assert "stats" in msg
        assert "recent_logs" in msg

def test_websocket_audio_session_streaming():
    """WebSocket /ws/audio accepts audio chunks and yields real-time updates."""
    with patch.object(whisper_client, "transcribe_wav", new_callable=AsyncMock) as mock_w, \
         patch.object(qwen_client, "post_correct_and_translate", new_callable=AsyncMock) as mock_q:
        
        mock_w.return_value = TranscriptionResult(
            text="Hola mundo",
            language="es",
            latency_ms=100.0
        )
        mock_q.return_value = TranslationResult(
            corrected_text="Hola, mundo.",
            english_translation="Hello, world.",
            source_language="es",
            latency_ms=300.0
        )

        with client.websocket_connect("/ws/audio") as ws:
            # 1. Start session
            ws.send_json({"type": "session_start"})
            res1 = ws.receive_json()
            assert res1["type"] == "status_update"
            assert res1["status"] == "recording"

            # 2. Send 4.0s of PCM audio in 2x 2.0s binary frames (64,000 bytes each)
            pcm_chunk = b"\x00\x00" * 32000 # 2.0s
            ws.send_bytes(pcm_chunk)
            ws.send_bytes(pcm_chunk) # Total 4.0s -> triggers window

            # Receive language_detected, transcription_update, translation_update
            msg1 = ws.receive_json()
            assert msg1["type"] == "language_detected"
            assert msg1["language_code"] == "es"

            msg2 = ws.receive_json()
            assert msg2["type"] == "transcription_update"
            assert "Hola" in msg2["text"]

            msg3 = ws.receive_json()
            assert msg3["type"] == "translation_update"
            assert "Hello, world." in msg3["translation"]

            # 3. Stop session
            ws.send_json({"type": "session_stop"})
            
            # Read messages until status_update idle
            received_types = []
            for _ in range(5):
                m = ws.receive_json()
                received_types.append(m.get("type"))
                if m.get("type") == "status_update" and m.get("status") == "idle":
                    break

            assert "status_update" in received_types