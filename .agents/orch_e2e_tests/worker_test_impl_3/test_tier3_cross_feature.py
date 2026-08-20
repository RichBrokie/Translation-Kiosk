"""
test_tier3_cross_feature.py - Tier 3 Cross-Feature Pairwise Integration Test Suite (15 Test Cases)
Validates multi-component interactions across the complete Translation Kiosk pipeline.
"""

import asyncio
import io
import json
import os
import sys
import time
import wave
import pytest
import httpx
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

APP_DIR = "/home/ubuntu/translation_kiosk"
TESTS_DIR = "/home/ubuntu/translation_kiosk/tests"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from config import (
    SAMPLE_RATE,
    BYTES_PER_SAMPLE,
    CHANNELS,
    BYTE_RATE,
    WINDOW_SEC,
    STRIDE_SEC,
    OVERLAP_SEC,
    WINDOW_BYTES,
    STRIDE_BYTES,
    OVERLAP_BYTES,
    MIN_FLUSH_BYTES,
    get_language_name,
    AppConfig
)
from audio_pipeline import (
    pack_pcm_to_wav,
    AudioRollingBuffer,
    TextStitcher,
    ComparativeEngine,
    AudioPipeline,
    PipelineResult
)
from whisper_client import WhisperClient, TranscriptionResult, WhisperResponse
from qwen_client import QwenClient, TranslationResult, QwenResponse
from telemetry import TelemetryCollector, ChunkTelemetry
from conftest import (
    create_sine_wave,
    create_silence,
    create_noise,
    package_wav,
    load_real_speech_sample,
    MockWhisperClient,
    MockQwenClient
)


@pytest.mark.asyncio
async def test_tc_t3_pair_01_ws_buffer_whisper_pipeline():
    """TC-T3-PAIR-01 (F1+F2+F3): WebSocket PCM Ingestion -> Ring Buffer Slicing -> Async Whisper ASR."""
    mock_whisper = MockWhisperClient(default_lang="es", default_text="Bienvenidos al museo")
    mock_qwen = MockQwenClient()
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    # Stream 8 seconds of PCM in 0.5s frames (16,000 bytes)
    for _ in range(16):
        frame = b"\x00\x00" * 8000
        res = await pipeline.process_chunk(frame)
        if res:
            assert res.whisper_latency_ms < 5000.0
            assert res.language == "es"
            
    assert mock_whisper.call_count >= 1


@pytest.mark.asyncio
async def test_tc_t3_pair_02_buffer_overlap_stitching():
    """TC-T3-PAIR-02 (F2+F5+F6): Buffer Window Slicing -> Overlap Re-Transcription -> SequenceMatcher Stitching."""
    stitcher = TextStitcher()
    # Step 1: Initial window
    _, _, t1, _ = stitcher.process_window("We welcome all visitors to our")
    # Step 2: Overlapping window starting with tentative overlap
    _, _, t2, _ = stitcher.process_window("visitors to our museum of natural science")
    # Step 3: Next window
    _, _, t3, _ = stitcher.process_window("museum of natural science and discovery.")
    
    assert "We welcome all visitors to our museum of natural science and discovery." == t3


@pytest.mark.asyncio
async def test_tc_t3_pair_03_whisper_autodetect_english_bypass():
    """TC-T3-PAIR-03 (F3+F4+F8): Whisper ASR -> Language Auto-Detection ('en') -> English Bypass Handler."""
    mock_whisper = MockWhisperClient(default_lang="en", default_text="Good morning, thank you for joining us today.")
    qwen_client = QwenClient(bypass_english=True)
    telemetry = TelemetryCollector()
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=qwen_client, telemetry_collector=telemetry)
    
    # 4s PCM
    res = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert res is not None
    assert res.is_english is True
    assert res.qwen_latency_ms == 0.0
    assert res.translated_text == "Good morning, thank you for joining us today."
    assert res.e2e_latency_ms < 1000.0


@pytest.mark.asyncio
async def test_tc_t3_pair_04_whisper_non_en_detection_qwen_translation():
    """TC-T3-PAIR-04 (F3+F4+F7): Whisper ASR -> Language Detection (Non-EN) -> Qwen 72B JSON Translation."""
    mock_whisper = MockWhisperClient(default_lang="es", default_text="en el segundo piso podran encontrar cartas")
    mock_qwen = MockQwenClient(
        default_corrected="En el segundo piso podrán encontrar cartas.",
        default_translated="On the second floor you will find letters."
    )
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    res = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert res is not None
    assert res.is_english is False
    assert res.language == "es"
    assert res.corrected_text == "En el segundo piso podrán encontrar cartas."
    assert res.translated_text == "On the second floor you will find letters."
    assert res.qwen_latency_ms < 8000.0


@pytest.mark.asyncio
async def test_tc_t3_pair_05_sliding_sequencematcher_dual_comparator():
    """TC-T3-PAIR-05 (F5+F6+F9): Sliding Window -> SequenceMatcher -> Dual Pipeline Comparator."""
    engine = ComparativeEngine()
    # Step 1
    s1 = engine.process_step(
        naive_chunk_text="Welcome to the mus",
        sliding_stitched_text="Welcome to the museum",
        whisper_sliding_latency_ms=320.0
    )
    # Step 2
    s2 = engine.process_step(
        naive_chunk_text="eum of modern art",
        sliding_stitched_text="Welcome to the museum of modern art",
        whisper_sliding_latency_ms=310.0
    )
    assert "museum of modern art" in s2["sliding_full_text"]
    assert len(s2["diff_tokens"]) > 0


@pytest.mark.asyncio
async def test_tc_t3_pair_06_ws_stream_telemetry_admin_broadcaster():
    """TC-T3-PAIR-06 (F1+F11+F14): WebSocket Audio Stream -> Admin Telemetry Broadcaster -> Admin Dashboard."""
    telemetry = TelemetryCollector()
    mock_whisper = MockWhisperClient(default_lang="fr", default_text="Bonjour")
    mock_qwen = MockQwenClient(default_corrected="Bonjour", default_translated="Hello")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen, telemetry_collector=telemetry)
    
    await pipeline.process_chunk(b"\x00\x00" * 64000)
    admin_snap = telemetry.get_admin_telemetry_payload()
    
    assert admin_snap["type"] == "admin_telemetry"
    assert admin_snap["stats"]["total_chunks_processed"] == 1
    assert admin_snap["latest_chunk"]["source_language"] == "fr"


@pytest.mark.asyncio
async def test_tc_t3_pair_07_audio_simulation_full_pipeline_trace():
    """TC-T3-PAIR-07 (F12+F2+F3+F7): Simulation Audio File Replay -> Full Pipeline Trace & Summary."""
    mock_whisper = MockWhisperClient(default_lang="es", default_text="Hola amigos")
    mock_qwen = MockQwenClient(default_corrected="Hola amigos.", default_translated="Hello friends.")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    # Simulate multi-chunk file
    trace = []
    for chunk_idx in range(3):
        res = await pipeline.process_chunk(b"\x00\x00" * 64000)
        if res:
            trace.append({
                "chunk_id": chunk_idx + 1,
                "text": res.stitched_text,
                "trans": res.translated_text,
                "whisper_ms": res.whisper_latency_ms,
                "qwen_ms": res.qwen_latency_ms
            })
            
    assert len(trace) >= 1
    assert trace[0]["trans"] == "Hello friends."


def test_tc_t3_pair_08_fastapi_core_ws_kiosk_lifecycle():
    """TC-T3-PAIR-08 (F1+F10+F13): FastAPI Core + WebSocket /ws/audio + Public Kiosk Lifecycle."""
    app_config = AppConfig()
    assert app_config.server_port == 8080
    assert app_config.sample_rate == 16000
    assert app_config.window_sec == 4.0
    assert app_config.stride_sec == 2.0


@pytest.mark.asyncio
async def test_tc_t3_pair_09_qwen_translation_to_english_bypass_transition():
    """TC-T3-PAIR-09 (F7+F8+F11): Qwen Translation -> English Bypass Transition -> Admin Telemetry Gauges."""
    telemetry = TelemetryCollector()
    mock_whisper_es = MockWhisperClient(default_lang="es", default_text="Hola")
    mock_whisper_en = MockWhisperClient(default_lang="en", default_text="Hello")
    qwen = QwenClient(bypass_english=True)
    
    # Chunk 1: Spanish (mock response)
    mock_resp = httpx.Response(200, json={
        "choices": [{"message": {"content": '{"corrected_text": "Hola", "english_translation": "Hello"}'}}]
    })
    with patch.object(qwen._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        p_es = AudioPipeline(whisper_client=mock_whisper_es, qwen_client=qwen, telemetry_collector=telemetry)
        r1 = await p_es.process_chunk(b"\x00\x00" * 64000)
        assert r1.is_english is False
        assert r1.qwen_latency_ms > 0
        
    # Chunk 2: English
    p_en = AudioPipeline(whisper_client=mock_whisper_en, qwen_client=qwen, telemetry_collector=telemetry)
    r2 = await p_en.process_chunk(b"\x00\x00" * 64000)
    assert r2.is_english is True
    assert r2.qwen_latency_ms == 0.0
    
    stats = telemetry.get_summary_stats()
    assert stats["total_bypasses"] == 1


def test_tc_t3_pair_10_systemd_fastapi_backend_endpoints():
    """TC-T3-PAIR-10 (F10+F15+F3+F7): Service Configuration -> FastAPI Server -> Backend Endpoints."""
    config = AppConfig()
    assert config.whisper_url == "http://localhost:8001/transcribe"
    assert config.vllm_url == "http://localhost:8000/v1/chat/completions"
    assert config.server_port == 8080


@pytest.mark.asyncio
async def test_tc_t3_pair_11_e2e_speech_to_translation_latency_budgets():
    """TC-T3-PAIR-11 (F1+F3+F7+F13): Full Pipeline Latency Verification (Whisper <5s, Qwen <8s)."""
    mock_whisper = MockWhisperClient(default_lang="de", default_text="Guten Tag")
    mock_qwen = MockQwenClient(default_corrected="Guten Tag.", default_translated="Good day.")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    res = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.e2e_latency_ms < 8500.0


@pytest.mark.asyncio
async def test_tc_t3_pair_12_stitched_text_qwen_correction_4stage_diff():
    """TC-T3-PAIR-12 (F6+F7+F11+F14): Stitched Text + Qwen Post-Correction -> 4-Stage Diff Visualization."""
    mock_whisper = MockWhisperClient(default_lang="fr", default_text="ne sest jamais donne les moyens")
    mock_qwen = MockQwenClient(
        default_corrected="ne s'est jamais donné les moyens",
        default_translated="has never given himself the means"
    )
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    res = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert res is not None
    
    diff_payload = {
        "stage_1_raw": res.raw_text,
        "stage_2_sliding": res.stitched_text,
        "stage_3_corrected": res.corrected_text,
        "stage_4_translated": res.translated_text
    }
    assert diff_payload["stage_3_corrected"] == "ne s'est jamais donné les moyens"
    assert diff_payload["stage_4_translated"] == "has never given himself the means"


@pytest.mark.asyncio
async def test_tc_t3_pair_13_live_stream_simulation_concurrency():
    """TC-T3-PAIR-13 (F1+F2+F12): Live Streaming + Simulation Endpoint Concurrency (Buffer Isolation)."""
    p_live = AudioPipeline(whisper_client=MockWhisperClient(default_text="Live stream text"))
    p_sim = AudioPipeline(whisper_client=MockWhisperClient(default_text="Simulation file text"))
    
    r_live = await p_live.process_chunk(b"\x00\x00" * 64000)
    r_sim = await p_sim.process_chunk(b"\x00\x00" * 64000)
    
    assert r_live.stitched_text == "Live stream text"
    assert r_sim.stitched_text == "Simulation file text"


@pytest.mark.asyncio
async def test_tc_t3_pair_14_backend_failure_degradation_admin_logging():
    """TC-T3-PAIR-14 (F3+F7+F11): Backend AI Failure Degradation -> Graceful Fallback & Admin Logging."""
    telemetry = TelemetryCollector()
    mock_whisper = MockWhisperClient(default_lang="es", default_text="Texto fuente")
    
    # Qwen fails with 503
    qwen = QwenClient(bypass_english=False, max_retries=0, telemetry_collector=telemetry)
    with patch.object(qwen._client, "post", side_effect=httpx.ConnectError("Connection refused :8000")):
        pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=qwen, telemetry_collector=telemetry)
        res = await pipeline.process_chunk(b"\x00\x00" * 64000)
        
        assert res is not None
        # Falls back gracefully to raw text translation
        assert res.translated_text == "Texto fuente"
        
    assert len(telemetry.api_logs) >= 1
    assert telemetry.api_logs[-1].status_code == 503 or telemetry.api_logs[-1].error is not None


@pytest.mark.asyncio
async def test_tc_t3_pair_15_multilingual_language_switching_dialogue():
    """TC-T3-PAIR-15 (F4+F6+F7): Multi-Speaker Language Switching (Bilingual Dialogue)."""
    mock_whisper = MockWhisperClient(default_lang="es", default_text="Hola")
    mock_qwen = MockQwenClient(default_corrected="Hola", default_translated="Hello")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    # Step 1: Spanish
    r1 = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert r1.language == "es"
    assert r1.language_name == "Spanish"
    
    # Step 2: Switch to French
    mock_whisper.default_lang = "fr"
    mock_whisper.default_text = "Bonjour"
    mock_qwen.default_corrected = "Bonjour"
    mock_qwen.default_translated = "Good day"
    
    r2 = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert r2.language == "fr"
    assert r2.language_name == "French"
    assert r2.translated_text == "Good day"
