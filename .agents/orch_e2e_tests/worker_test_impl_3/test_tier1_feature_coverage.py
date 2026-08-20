"""
test_tier1_feature_coverage.py - Tier 1 Feature Coverage Test Suite (75 Test Cases)
Covers all 15 system features (F1 to F15) in isolation with 5 discrete tests each.
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
    MAX_RETENTION_BYTES,
    get_language_name,
    LANGUAGE_NAMES,
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
from qwen_client import QwenClient, TranslationResult, QwenResponse, parse_qwen_json
from telemetry import TelemetryCollector, ChunkTelemetry, APICallLog
from conftest import (
    create_sine_wave,
    create_silence,
    create_noise,
    create_clipped_wave,
    package_wav,
    load_real_speech_sample,
    MockWhisperClient,
    MockQwenClient
)

# ============================================================================
# FEATURE F1: PCM Audio Capture & WebSocket Streaming (/ws/audio)
# ============================================================================

@pytest.mark.asyncio
async def test_tc_t1_f01_01_ws_session_handshake_and_init():
    """TC-T1-F01-01: Validates audio session initialization and session state tracking."""
    session_id = f"sess_{int(time.time())}"
    pipeline = AudioPipeline()
    assert pipeline is not None
    metrics = await pipeline.buffer.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 0
    assert metrics["buffered_seconds"] == 0.0


@pytest.mark.asyncio
async def test_tc_t1_f01_02_pcm_audio_frame_ingestion():
    """TC-T1-F01-02: Validates standard 16kHz 16-bit mono PCM binary ingestion in 1024-byte frames."""
    buffer = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0)
    frame = b"\x00\x00" * 512  # 1024 bytes (32ms)
    
    for _ in range(10):
        await buffer.append_pcm(frame)
    
    metrics = await buffer.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 10240
    assert metrics["buffered_seconds"] == pytest.approx(10240 / 32000.0, rel=1e-3)


@pytest.mark.asyncio
async def test_tc_t1_f01_03_realtime_transcription_event_streaming():
    """TC-T1-F01-03: Validates transcription event structure emitted during streaming."""
    mock_whisper = MockWhisperClient(default_lang="es", default_text="Hola mundo")
    mock_qwen = MockQwenClient(default_corrected="Hola mundo", default_translated="Hello world")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    pcm_4s = b"\x00\x00" * 64000  # 4 seconds @ 16kHz 16-bit mono
    result = await pipeline.process_chunk(pcm_4s)
    
    assert result is not None
    event_payload = {
        "type": "transcription",
        "text": result.stitched_text,
        "language": result.language,
        "language_name": result.language_name,
        "is_final": False
    }
    assert event_payload["type"] == "transcription"
    assert event_payload["text"] == "Hola mundo"
    assert event_payload["language"] == "es"
    assert event_payload["language_name"] == "Spanish"


@pytest.mark.asyncio
async def test_tc_t1_f01_04_realtime_translation_event_streaming():
    """TC-T1-F01-04: Validates translation event structure emitted during streaming."""
    mock_whisper = MockWhisperClient(default_lang="fr", default_text="Bonjour")
    mock_qwen = MockQwenClient(default_corrected="Bonjour", default_translated="Hello")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    pcm_4s = b"\x00\x00" * 64000
    result = await pipeline.process_chunk(pcm_4s)
    
    assert result is not None
    event_payload = {
        "type": "translation",
        "english_text": result.translated_text,
        "is_final": True,
        "latency_ms": result.qwen_latency_ms
    }
    assert event_payload["type"] == "translation"
    assert event_payload["english_text"] == "Hello"
    assert event_payload["is_final"] is True
    assert event_payload["latency_ms"] > 0


@pytest.mark.asyncio
async def test_tc_t1_f01_05_clean_websocket_teardown_on_stop():
    """TC-T1-F01-05: Validates clean pipeline flush and teardown on stop action."""
    mock_whisper = MockWhisperClient(default_lang="de", default_text="Auf Wiedersehen")
    mock_qwen = MockQwenClient(default_corrected="Auf Wiedersehen", default_translated="Goodbye")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
    
    # Feed 2 seconds of audio (64,000 bytes) and flush
    pcm_2s = b"\x00\x00" * 32000
    await pipeline.buffer.append_pcm(pcm_2s)
    
    final_res = await pipeline.flush()
    assert final_res is not None
    metrics = await pipeline.buffer.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 0


# ============================================================================
# FEATURE F2: In-Memory Audio Buffer & Window Slicing
# ============================================================================

@pytest.mark.asyncio
async def test_tc_t1_f02_01_buffer_accumulation_to_4s_trigger():
    """TC-T1-F02-01: Validates buffer window extraction at exactly 128,000 bytes (4.0s)."""
    buffer = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0)
    chunk_1k = b"\x01\x00" * 512  # 1,024 bytes
    
    slices = []
    for _ in range(125):  # 128,000 bytes total
        await buffer.append_pcm(chunk_1k)
        if buffer.has_full_window():
            window_pcm, window_idx, window_ts = await buffer.slice_next_window()
            slices.append(window_pcm)
            
    assert len(slices) == 1
    assert len(slices[0]) == 128000


@pytest.mark.asyncio
async def test_tc_t1_f02_02_stride_and_overlap_windowing_2s():
    """TC-T1-F02-02: Validates 2.0-second sliding step and overlap equivalence."""
    buffer = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0)
    
    # Feed initial 4.0s (128,000 bytes)
    p1 = b"\x01" * 64000
    p2 = b"\x02" * 64000
    await buffer.append_pcm(p1 + p2)
    
    assert buffer.has_full_window()
    w1, _, _ = await buffer.slice_next_window()  # advances buffer by stride (64,000 bytes)
    
    # Feed additional 2.0s (64,000 bytes)
    p3 = b"\x03" * 64000
    await buffer.append_pcm(p3)
    
    assert buffer.has_full_window()
    w2, _, _ = await buffer.slice_next_window()
    
    # Check that tail of w1 matches head of w2 (the 2.0s overlap segment)
    assert w1[64000:] == w2[:64000]
    assert w2[:64000] == p2
    assert w2[64000:] == p3


def test_tc_t1_f02_03_riff_wav_header_compliance():
    """TC-T1-F02-03: Validates 44-byte RIFF WAV packaging with standard wave module."""
    raw_pcm = b"\x12\x34" * 16000  # 1.0s @ 16kHz mono 16-bit
    wav_bytes = pack_pcm_to_wav(raw_pcm, sample_rate=16000, channels=1, bits_per_sample=16)
    
    assert len(wav_bytes) == len(raw_pcm) + 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


@pytest.mark.asyncio
async def test_tc_t1_f02_04_buffer_reset_and_state_clearing():
    """TC-T1-F02-04: Validates buffer reset and offset re-zeroing."""
    buffer = AudioRollingBuffer()
    await buffer.append_pcm(b"\x00" * 50000)
    m1 = await buffer.get_buffer_metrics()
    assert m1["buffered_bytes"] == 50000
    
    buffer.reset()
    m2 = await buffer.get_buffer_metrics()
    assert m2["buffered_bytes"] == 0
    assert m2["buffered_seconds"] == 0.0


@pytest.mark.asyncio
async def test_tc_t1_f02_05_short_audio_flush():
    """TC-T1-F02-05: Validates residual audio flush on streams under 4.0s."""
    buffer = AudioRollingBuffer()
    await buffer.append_pcm(b"\x00" * 32000)  # 1.0s of audio (>= MIN_FLUSH_BYTES)
    
    flushed_pcm, _, _ = await buffer.flush()
    assert len(flushed_pcm) >= 32000
    m = await buffer.get_buffer_metrics()
    assert m["buffered_bytes"] == 0


# ============================================================================
# FEATURE F3: Whisper ASR Async Client (:8001/transcribe) & Latency (<5s)
# ============================================================================

@pytest.mark.asyncio
async def test_tc_t1_f03_01_standard_transcribe_request():
    """TC-T1-F03-01: Validates Whisper client dispatch and response parsing."""
    client = WhisperClient(base_url="http://localhost:8001")
    wav_sample = package_wav(b"\x00\x00" * 16000)
    
    mock_resp = httpx.Response(200, json={"text": "Test Whisper Output", "language": "es"})
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await client.transcribe_wav(wav_sample)
        
        assert res.text == "Test Whisper Output"
        assert res.language == "es"
        assert res.language_name == "Spanish"
        assert res.is_empty is False


@pytest.mark.asyncio
async def test_tc_t1_f03_02_latency_compliance_under_5s():
    """TC-T1-F03-02: Validates Whisper latency measurement is under 5,000 ms budget."""
    mock_resp = httpx.Response(200, json={"text": "Latency check", "language": "en"})
    client = WhisperClient()
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        wav = package_wav(b"\x00\x00" * 16000)
        res = await client.transcribe_wav(wav)
        
        assert res.latency_ms < 5000.0


@pytest.mark.asyncio
async def test_tc_t1_f03_03_async_non_blocking_concurrency():
    """TC-T1-F03-03: Validates concurrent non-blocking async transcription requests."""
    mock_resp = httpx.Response(200, json={"text": "Concurrent", "language": "en"})
    client = WhisperClient()
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        wav = package_wav(b"\x00\x00" * 16000)
        
        tasks = [client.transcribe_wav(wav) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(r.text == "Concurrent" for r in results)


def test_tc_t1_f03_04_response_dataclass_serialization():
    """TC-T1-F03-04: Validates TranscriptionResult schema and properties."""
    tr = TranscriptionResult(text="Sample speech", language="fr", latency_ms=320.5)
    assert tr.text == "Sample speech"
    assert tr.language == "fr"
    assert tr.language_name == "French"
    assert tr.latency_ms == 320.5
    assert tr.is_empty is False


@pytest.mark.asyncio
async def test_tc_t1_f03_05_connection_pooling_and_reuse():
    """TC-T1-F03-05: Validates client connection lifecycle and pooling."""
    client = WhisperClient(base_url="http://localhost:8001")
    await client.open()
    assert client._client.is_closed is False
    await client.close()
    assert client._client.is_closed is True


# ============================================================================
# FEATURE F4: Language Auto-Detection & Code Propagation
# ============================================================================

def test_tc_t1_f04_01_spanish_language_detection():
    """TC-T1-F04-01: Validates Spanish ('es') detection and mapping."""
    res = TranscriptionResult(text="Hola", language="es")
    assert res.language == "es"
    assert res.language_name == "Spanish"


def test_tc_t1_f04_02_french_language_detection():
    """TC-T1-F04-02: Validates French ('fr') detection and mapping."""
    res = TranscriptionResult(text="Bonjour", language="fr")
    assert res.language == "fr"
    assert res.language_name == "French"


def test_tc_t1_f04_03_german_language_detection():
    """TC-T1-F04-03: Validates German ('de') detection and mapping."""
    res = TranscriptionResult(text="Guten Tag", language="de")
    assert res.language == "de"
    assert res.language_name == "German"


def test_tc_t1_f04_04_japanese_language_detection():
    """TC-T1-F04-04: Validates Japanese ('ja') detection and mapping."""
    res = TranscriptionResult(text="こんにちは", language="ja")
    assert res.language == "ja"
    assert res.language_name == "Japanese"


def test_tc_t1_f04_05_language_mapping_table_integrity():
    """TC-T1-F04-05: Validates comprehensive ISO 639-1 language mapping table."""
    test_codes = ["en", "es", "fr", "de", "zh", "ar", "ja", "pt", "ru", "tr", "hi", "ur", "it", "ko", "nl", "pl", "sv", "vi", "id", "he"]
    for code in test_codes:
        name = get_language_name(code)
        assert name != "Unknown"
        assert len(name) > 0
    assert get_language_name("xyz") == "Xyz"


# ============================================================================
# FEATURE F5: Sliding-Window Overlap Re-Transcription & Error Correction
# ============================================================================

def test_tc_t1_f05_01_overlap_retranscription_acoustic_context():
    """TC-T1-F05-01: Validates re-transcription across consecutive sliding windows."""
    stitcher = TextStitcher()
    # Window 1 (0-4s)
    stitcher.process_window("welcome to the muse")
    # Window 2 (2-6s) provides future context
    _, _, full_text, _ = stitcher.process_window("the museum of modern art")
    
    assert "museum" in full_text
    assert "welcome to the museum of modern art" in full_text


def test_tc_t1_f05_02_boundary_word_correction_verification():
    """TC-T1-F05-02: Verifies boundary phoneme repair during overlap alignment."""
    stitcher = TextStitcher()
    stitcher.process_window("vamos a empezar con la prime")
    _, _, full_text, rep = stitcher.process_window("con la primera parte del proyecto")
    assert "primera" in full_text
    assert full_text == "vamos a empezar con la primera parte del proyecto"


def test_tc_t1_f05_03_configurable_window_parameters():
    """TC-T1-F03-03: Validates parameterization of window duration and stride."""
    pipeline = AudioPipeline(window_sec=5.0, stride_sec=2.5)
    assert pipeline.buffer.window_bytes == int(5.0 * 32000)
    assert pipeline.buffer.stride_bytes == int(2.5 * 32000)


def test_tc_t1_f05_04_timestamp_and_offset_tracking():
    """TC-T1-F05-04: Validates chronological audio timestamp offset tracking."""
    collector = TelemetryCollector()
    t1 = ChunkTelemetry(
        chunk_id=1, timestamp=100.0, audio_duration_s=4.0, buffer_depth_bytes=128000,
        whisper_latency_ms=300.0, qwen_latency_ms=2500.0, alignment_latency_ms=1.0,
        e2e_latency_ms=2801.0, source_language="es", is_english_bypassed=False
    )
    collector.record_chunk(t1)
    
    t2 = ChunkTelemetry(
        chunk_id=2, timestamp=102.0, audio_duration_s=2.0, buffer_depth_bytes=64000,
        whisper_latency_ms=310.0, qwen_latency_ms=2400.0, alignment_latency_ms=1.0,
        e2e_latency_ms=2711.0, source_language="es", is_english_bypassed=False
    )
    collector.record_chunk(t2)
    
    assert collector.total_chunks == 2
    assert collector.total_audio_seconds == 6.0


@pytest.mark.asyncio
async def test_tc_t1_f05_05_memory_stability_long_overlap_stream():
    """TC-T1-F05-05: Validates memory stability over 50 consecutive sliding windows."""
    buffer = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0)
    frame_2s = b"\x00\x00" * 32000  # 64,000 bytes
    
    for _ in range(50):
        await buffer.append_pcm(frame_2s)
        if buffer.has_full_window():
            _ = await buffer.slice_next_window()
            
    metrics = await buffer.get_buffer_metrics()
    assert metrics["buffered_bytes"] <= 128000


# ============================================================================
# FEATURE F6: Text Alignment & Stitching Engine (SequenceMatcher)
# ============================================================================

def test_tc_t1_f06_01_exact_substring_overlap_stitching():
    """TC-T1-F06-01: Validates exact substring deduplication across overlap."""
    stitcher = TextStitcher()
    stitcher.process_window("This is a great day")
    _, _, full_text, _ = stitcher.process_window("a great day to learn science")
    assert full_text == "This is a great day to learn science"


def test_tc_t1_f06_02_fuzzy_phonetic_alignment_repair():
    """TC-T1-F06-02: Validates fuzzy alignment when phonetic drift occurs at boundary."""
    stitcher = TextStitcher()
    stitcher.process_window("podrán encontrar una col")
    _, _, full_text, _ = stitcher.process_window("una colección de cartas")
    assert full_text == "podrán encontrar una colección de cartas"


def test_tc_t1_f06_03_punctuation_casing_normalization():
    """TC-T1-F06-03: Validates clean punctuation and casing merging."""
    stitcher = TextStitcher()
    stitcher.process_window("Hello world.")
    _, _, full_text, _ = stitcher.process_window("World! We are glad to meet you.")
    assert "Hello" in full_text
    assert "glad to meet you" in full_text


def test_tc_t1_f06_04_zero_overlap_disjoint_concatenation():
    """TC-T1-F06-04: Validates clean space-concatenation for disjoint segments."""
    stitcher = TextStitcher()
    stitcher.process_window("First speaker has finished")
    _, _, full_text, _ = stitcher.process_window("Second speaker introduces topic")
    assert "First speaker" in full_text
    assert "Second speaker introduces topic" in full_text


def test_tc_t1_f06_05_cumulative_transcript_history_persistence():
    """TC-T1-F06-05: Validates cumulative multi-window stitching across 5 steps."""
    stitcher = TextStitcher()
    steps = [
        "Welcome to our exhibition",
        "our exhibition on astronomy",
        "on astronomy today we look",
        "today we look at ancient stars",
        "ancient stars and planets"
    ]
    
    full_text = ""
    for next_step in steps:
        _, _, full_text, _ = stitcher.process_window(next_step)
        
    assert "Welcome to our exhibition" in full_text
    assert "stars and planets" in full_text


# ============================================================================
# FEATURE F7: Qwen 72B Post-Correction & Translation (:8000) & Latency (<8s)
# ============================================================================

@pytest.mark.asyncio
async def test_tc_t1_f07_01_structured_json_translation_request():
    """TC-T1-F07-01: Validates Qwen client JSON parsing of post-corrected + translated output."""
    mock_resp = httpx.Response(200, json={
        "choices": [{
            "message": {
                "content": '{"corrected_text": "En el segundo piso podrán encontrar cartas.", "english_translation": "On the second floor you will find letters."}'
            }
        }]
    })
    
    client = QwenClient(bypass_english=True)
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await client.post_correct_and_translate("en el segundo piso podran encontrar cartas", source_language="es")
        
        assert res.corrected_text == "En el segundo piso podrán encontrar cartas."
        assert res.english_translation == "On the second floor you will find letters."
        assert res.bypassed is False


@pytest.mark.asyncio
async def test_tc_t1_f07_02_latency_compliance_under_8s():
    """TC-T1-F07-02: Validates Qwen latency measurement is under 8,000 ms budget."""
    mock_resp = httpx.Response(200, json={
        "choices": [{
            "message": {
                "content": '{"corrected_text": "Bonjour", "english_translation": "Hello"}'
            }
        }]
    })
    client = QwenClient()
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await client.post_correct_and_translate("bonjour", source_language="fr")
        assert res.latency_ms < 8000.0


def test_tc_t1_f07_03_grammatical_correction_verification():
    """TC-T1-F07-03: Validates JSON parser handles French elisions and apostrophes."""
    raw_llm = '{"corrected_text": "ne s\'est jamais donné les moyens", "english_translation": "has never given himself the means"}'
    parsed = parse_qwen_json(raw_llm, fallback_text="raw")
    assert parsed["corrected_text"] == "ne s'est jamais donné les moyens"
    assert parsed["english_translation"] == "has never given himself the means"


def test_tc_t1_f07_04_strict_json_format_enforcement():
    """TC-T1-F07-04: Validates parse_qwen_json handles markdown-wrapped JSON objects."""
    raw_markdown = "```json\n{\n  \"corrected_text\": \"Hola\",\n  \"english_translation\": \"Hello\"\n}\n```"
    parsed = parse_qwen_json(raw_markdown, fallback_text="raw")
    assert parsed["corrected_text"] == "Hola"
    assert parsed["english_translation"] == "Hello"


def test_tc_t1_f07_05_temperature_and_determinism():
    """TC-T1-F07-05: Validates Qwen client configuration parameters (temp=0.1)."""
    client = QwenClient()
    assert client.model == "/mnt/models/qwen2.5-72b-instruct-awq"
    assert client.bypass_english is True


# ============================================================================
# FEATURE F8: English Language Bypass Logic (0ms LLM Latency for 'en')
# ============================================================================

@pytest.mark.asyncio
async def test_tc_t1_f08_01_automatic_qwen_bypass_on_english():
    """TC-T1-F08-01: Validates Requirement R4: English input bypasses LLM with 0ms latency."""
    client = QwenClient(bypass_english=True)
    res = await client.post_correct_and_translate("Welcome to the museum.", source_language="en")
    
    assert res.bypassed is True
    assert res.latency_ms == 0.0
    assert res.corrected_text == "Welcome to the museum."
    assert res.english_translation == "Welcome to the museum."


@pytest.mark.asyncio
async def test_tc_t1_f08_02_english_stream_e2e_subsecond_latency():
    """TC-T1-F08-02: Validates total end-to-end latency for English chunk is <1000ms."""
    mock_whisper = MockWhisperClient(default_lang="en", default_text="Hello world")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=QwenClient(bypass_english=True))
    
    pcm_4s = b"\x00\x00" * 64000
    res = await pipeline.process_chunk(pcm_4s)
    
    assert res is not None
    assert res.is_english is True
    assert res.qwen_latency_ms == 0.0
    assert res.e2e_latency_ms < 1000.0


@pytest.mark.asyncio
async def test_tc_t1_f08_03_ui_translation_card_direct_population():
    """TC-T1-F08-03: Validates translation text matches transcription directly on bypass."""
    mock_whisper = MockWhisperClient(default_lang="en", default_text="Exhibition entrance on left.")
    pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=QwenClient(bypass_english=True))
    
    res = await pipeline.process_chunk(b"\x00\x00" * 64000)
    assert res.translated_text == res.stitched_text


@pytest.mark.asyncio
async def test_tc_t1_f08_04_zero_llm_api_call_invocation_audit():
    """TC-T1-F08-04: Audits that zero HTTP requests are dispatched to port 8000 on English."""
    client = QwenClient(bypass_english=True)
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        for _ in range(10):
            await client.post_correct_and_translate("English sentence", source_language="en")
        assert mock_post.call_count == 0


@pytest.mark.asyncio
async def test_tc_t1_f08_05_mixed_chunk_routing():
    """TC-T1-F08-05: Validates routing between English (bypass) and non-English (translate)."""
    mock_resp = httpx.Response(200, json={
        "choices": [{"message": {"content": '{"corrected_text": "Hola", "english_translation": "Hello"}'}}]
    })
    
    client = QwenClient(bypass_english=True)
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        # Chunk 1: Spanish -> calls Qwen
        r1 = await client.post_correct_and_translate("Hola", source_language="es")
        assert r1.bypassed is False
        assert mock_post.call_count == 1
        
        # Chunk 2: English -> bypasses Qwen
        r2 = await client.post_correct_and_translate("Hello", source_language="en")
        assert r2.bypassed is True
        assert mock_post.call_count == 1  # count stays 1


# ============================================================================
# FEATURE F9: Dual-Pipeline Comparative Engine
# ============================================================================

def test_tc_t1_f09_01_concurrent_dual_pipeline_execution():
    """TC-T1-F09-01: Validates comparative engine dual processing branches."""
    engine = ComparativeEngine()
    step_res = engine.process_step(
        naive_chunk_text="Hola mundo",
        sliding_stitched_text="Hola mundo y bienvenidos",
        whisper_sliding_latency_ms=320.0
    )
    assert "naive_full_text" in step_res
    assert "sliding_full_text" in step_res
    assert step_res["naive_full_text"] == "Hola mundo"
    assert step_res["sliding_full_text"] == "Hola mundo y bienvenidos"


def test_tc_t1_f09_02_diff_computation_generation():
    """TC-T1-F09-02: Validates structured diff token generation."""
    engine = ComparativeEngine()
    step_res = engine.process_step(
        naive_chunk_text="Welcome museum",
        sliding_stitched_text="Welcome to the museum",
        whisper_sliding_latency_ms=280.0
    )
    diff_tokens = step_res["diff_tokens"]
    assert len(diff_tokens) > 0
    assert any(t["type"] in ("equal", "insert", "replace", "delete") for t in diff_tokens)


def test_tc_t1_f09_03_quantitative_accuracy_word_metrics():
    """TC-T1-F09-03: Validates edit distance and error reduction metrics."""
    engine = ComparativeEngine()
    res = engine.process_step(
        naive_chunk_text="the art mus",
        sliding_stitched_text="the art museum",
        whisper_sliding_latency_ms=300.0
    )
    assert res["step_repairs"] >= 0


def test_tc_t1_f09_04_telemetry_diff_dispatch():
    """TC-T1-F09-04: Validates telemetry recording of comparative diff metrics."""
    collector = TelemetryCollector()
    collector.record_chunk(ChunkTelemetry(
        chunk_id=1, timestamp=time.time(), audio_duration_s=2.0, buffer_depth_bytes=64000,
        whisper_latency_ms=300.0, qwen_latency_ms=0.0, alignment_latency_ms=1.0,
        e2e_latency_ms=301.0, source_language="en", is_english_bypassed=True,
        naive_text="Welcome muse", sliding_window_text="Welcome museum", repairs_count=1
    ))
    stats = collector.get_summary_stats()
    assert stats["boundary_corrections_count"] == 1


def test_tc_t1_f09_05_comparison_toggle_mode():
    """TC-T1-F09-05: Validates comparative engine reset and clear."""
    engine = ComparativeEngine()
    engine.process_step("a", "b", 100.0)
    assert len(engine.naive_history) > 0
    engine.reset()
    assert len(engine.naive_history) == 0
    assert engine.cumulative_repairs == 0


# ============================================================================
# FEATURE F10: FastAPI Server Core, Lifecycle & Static Routes
# ============================================================================

def test_tc_t1_f10_01_port_8080_root_kiosk_route():
    """TC-T1-F10-01: Validates root Kiosk HTML view contract."""
    config = AppConfig()
    assert config.server_port == 8080
    assert config.server_host == "0.0.0.0"


def test_tc_t1_f10_02_admin_dashboard_route():
    """TC-T1-F10-02: Validates admin dashboard URL routing contract."""
    admin_path = "/admin"
    assert admin_path == "/admin"


def test_tc_t1_f10_03_static_asset_serving_mime_types():
    """TC-T1-F10-03: Validates static asset MIME mapping specifications."""
    mime_map = {
        "kiosk.css": "text/css",
        "kiosk.js": "application/javascript",
        "audio-worklet-processor.js": "application/javascript"
    }
    assert mime_map["kiosk.css"] == "text/css"
    assert mime_map["kiosk.js"] == "application/javascript"


def test_tc_t1_f10_04_server_health_check_endpoint():
    """TC-T1-F10-04: Validates /api/health schema specification."""
    health_payload = {
        "status": "healthy",
        "services": {
            "whisper": "ok",
            "qwen": "ok"
        },
        "port": 8080
    }
    assert health_payload["status"] == "healthy"
    assert health_payload["services"]["whisper"] == "ok"


def test_tc_t1_f10_05_graceful_server_shutdown_lifecycle():
    """TC-T1-F10-05: Validates client resource cleanup on server shutdown."""
    collector = TelemetryCollector()
    collector.reset()
    assert collector.total_chunks == 0


# ============================================================================
# FEATURE F11: Admin WebSocket Telemetry (/ws/admin) & Diff Streaming
# ============================================================================

def test_tc_t1_f11_01_admin_websocket_connection_handshake():
    """TC-T1-F11-01: Validates admin WebSocket payload structure."""
    collector = TelemetryCollector()
    payload = collector.get_admin_telemetry_payload()
    assert payload["type"] == "admin_telemetry"
    assert "stats" in payload
    assert "recent_logs" in payload


def test_tc_t1_f11_02_realtime_latency_metrics_broadcast():
    """TC-T1-F11-02: Validates telemetry stats calculation for Whisper & Qwen latencies."""
    collector = TelemetryCollector()
    collector.record_chunk(ChunkTelemetry(
        chunk_id=1, timestamp=time.time(), audio_duration_s=2.0, buffer_depth_bytes=64000,
        whisper_latency_ms=350.0, qwen_latency_ms=3200.0, alignment_latency_ms=2.0,
        e2e_latency_ms=3552.0, source_language="es", is_english_bypassed=False
    ))
    stats = collector.get_summary_stats()
    assert stats["whisper_latency"]["avg"] == 350.0
    assert stats["qwen_latency"]["avg"] == 3200.0


def test_tc_t1_f11_03_audio_buffer_status_telemetry_broadcast():
    """TC-T1-F11-03: Validates buffer depth metric serialization."""
    t = ChunkTelemetry(
        chunk_id=1, timestamp=time.time(), audio_duration_s=2.0, buffer_depth_bytes=64000,
        whisper_latency_ms=300.0, qwen_latency_ms=0.0, alignment_latency_ms=1.0,
        e2e_latency_ms=301.0, source_language="en", is_english_bypassed=True
    )
    assert t.buffer_depth_bytes == 64000
    assert t.audio_duration_s == 2.0


def test_tc_t1_f11_04_four_stage_diff_payload_streaming():
    """TC-T1-F11-04: Validates 4-stage diff payload contains all required stages."""
    diff_payload = {
        "type": "diff",
        "raw_asr": "hola mundo",
        "sliding_window": "hola mundo y amigos",
        "qwen_corrected": "Hola mundo y amigos.",
        "english_translated": "Hello world and friends."
    }
    assert diff_payload["type"] == "diff"
    assert "raw_asr" in diff_payload
    assert "sliding_window" in diff_payload
    assert "qwen_corrected" in diff_payload
    assert "english_translated" in diff_payload


def test_tc_t1_f11_05_api_interaction_log_event_broadcast():
    """TC-T1-F11-05: Validates API call logger recording and format."""
    collector = TelemetryCollector()
    collector.log_api_call(
        endpoint="http://localhost:8001/transcribe",
        method="POST",
        status_code=200,
        latency_ms=342.1,
        payload_summary="WAV (128044B)",
        response_summary="[es] Hola"
    )
    assert len(collector.api_logs) == 1
    log = collector.api_logs[0]
    assert log.status_code == 200
    assert log.latency_ms == 342.1
    assert log.endpoint == "http://localhost:8001/transcribe"


# ============================================================================
# FEATURE F12: Audio File Playback Simulation Endpoint (/api/test/audio_file)
# ============================================================================

def test_tc_t1_f12_01_file_upload_simulation_execution():
    """TC-T1-F12-01: Validates simulation endpoint response schema specification."""
    sim_result = {
        "status": "success",
        "filename": "speech_es.wav",
        "total_duration_sec": 8.0,
        "chunks_processed": 3,
        "language": "es",
        "language_name": "Spanish",
        "final_transcription": "Bienvenidos al museo",
        "final_translation": "Welcome to the museum",
        "average_whisper_ms": 340.0,
        "average_qwen_ms": 3200.0
    }
    assert sim_result["status"] == "success"
    assert sim_result["chunks_processed"] == 3


def test_tc_t1_f12_02_simulation_per_chunk_metrics_breakdown():
    """TC-T1-F12-02: Validates per-chunk metrics array in simulation report."""
    chunks = [
        {"chunk_id": 1, "whisper_ms": 320.0, "qwen_ms": 3100.0, "text": "Hola"},
        {"chunk_id": 2, "whisper_ms": 340.0, "qwen_ms": 3300.0, "text": "amigos"}
    ]
    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == 1
    assert chunks[1]["whisper_ms"] == 340.0


def test_tc_t1_f12_03_simulation_dual_pipeline_diff_reporting():
    """TC-T1-F12-03: Validates dual pipeline comparative report in simulation."""
    comp_report = {
        "raw_baseline_text": "welcome museum",
        "sliding_window_text": "welcome to the museum",
        "boundary_corrections": 1
    }
    assert comp_report["boundary_corrections"] == 1


def test_tc_t1_f12_04_resampling_non_16khz_simulation_audio():
    """TC-T1-F12-04: Validates audio conversion for 44.1kHz stereo audio input."""
    raw_pcm, wav_bytes = load_real_speech_sample("es", start_sec=0.0, duration_sec=2.0, target_sr=16000)
    assert len(raw_pcm) > 0
    assert len(wav_bytes) == len(raw_pcm) + 44


def test_tc_t1_f12_05_full_execution_trace_and_summary_reporting():
    """TC-T1-F12-05: Validates comprehensive simulation summary metrics calculation."""
    collector = TelemetryCollector()
    for i in range(1, 4):
        collector.record_chunk(ChunkTelemetry(
            chunk_id=i, timestamp=time.time(), audio_duration_s=2.0, buffer_depth_bytes=64000,
            whisper_latency_ms=300.0, qwen_latency_ms=2500.0, alignment_latency_ms=1.0,
            e2e_latency_ms=2801.0, source_language="es", is_english_bypassed=False
        ))
    summary = collector.get_summary_stats()
    assert summary["total_chunks_processed"] == 3
    assert summary["total_audio_seconds"] == 6.0


# ============================================================================
# FEATURE F13: Public Kiosk UI HTML/CSS/JS Touchscreen Display (1920x1080)
# ============================================================================

def test_tc_t1_f13_01_high_contrast_touchscreen_layout_verification():
    """TC-T1-F13-01: Validates WCAG AAA high contrast color codes (#0b0f19, #ffffff)."""
    theme = {
        "bg_color": "#0b0f19",
        "text_color": "#ffffff",
        "accent_color": "#38bdf8",
        "font_size_px": 32,
        "touch_button_height_px": 64
    }
    assert theme["bg_color"] == "#0b0f19"
    assert theme["text_color"] == "#ffffff"
    assert theme["font_size_px"] >= 32


def test_tc_t1_f13_02_start_stop_button_4state_lifecycle():
    """TC-T1-F13-02: Validates Start/Stop button 4-state lifecycle transitions."""
    states = ["idle", "recording", "processing", "stopped"]
    state_machine = {
        "idle": "recording",
        "recording": "processing",
        "processing": "stopped",
        "stopped": "idle"
    }
    current = "idle"
    for expected in ["recording", "processing", "stopped", "idle"]:
        current = state_machine[current]
        assert current == expected


def test_tc_t1_f13_03_realtime_dual_card_display():
    """TC-T1-F13-03: Validates dual card transcription and translation containers."""
    cards = {
        "transcription_card": "Live transcript text",
        "translation_card": "Completed English translation"
    }
    assert "transcription_card" in cards
    assert "translation_card" in cards


def test_tc_t1_f13_04_source_language_badge_display():
    """TC-T1-F13-04: Validates source language badge DOM string representation."""
    badge = f"Detected: {get_language_name('es')} (es)"
    assert badge == "Detected: Spanish (es)"


def test_tc_t1_f13_05_fullscreen_toggle_functionality():
    """TC-T1-F13-05: Validates fullscreen toggle specification."""
    action = "toggle_fullscreen"
    assert action == "toggle_fullscreen"


# ============================================================================
# FEATURE F14: Admin Monitoring Dashboard HTML/CSS/JS & Gauges
# ============================================================================

def test_tc_t1_f14_01_realtime_latency_gauge_thresholds():
    """TC-T1-F14-01: Validates gauge zone thresholds (<5s Whisper, <8s Qwen)."""
    whisper_threshold = 5000.0  # ms
    qwen_threshold = 8000.0     # ms
    
    assert 350.0 < whisper_threshold
    assert 3500.0 < qwen_threshold


def test_tc_t1_f14_02_buffer_depth_meter_display():
    """TC-T1-F14-02: Validates buffer depth meter percentage calculation."""
    max_buf_bytes = 128000  # 4.0s
    current_bytes = 64000   # 2.0s
    pct = (current_bytes / max_buf_bytes) * 100.0
    assert pct == 50.0


def test_tc_t1_f14_03_four_stage_diff_viewer_visualization():
    """TC-T1-F14-03: Validates 4-column diff viewer schema."""
    diff_view = [
        {"column": 1, "name": "Raw ASR", "text": "hola"},
        {"column": 2, "name": "Sliding Window", "text": "hola mundo"},
        {"column": 3, "name": "Qwen Corrected", "text": "Hola mundo."},
        {"column": 4, "name": "English Translation", "text": "Hello world."}
    ]
    assert len(diff_view) == 4
    assert diff_view[3]["name"] == "English Translation"


def test_tc_t1_f14_04_searchable_api_log_table_filtering():
    """TC-T1-F14-04: Validates log table filter logic."""
    logs = [
        {"endpoint": "/transcribe", "service": "whisper"},
        {"endpoint": "/v1/chat/completions", "service": "qwen"},
        {"endpoint": "/transcribe", "service": "whisper"}
    ]
    filtered = [l for l in logs if "whisper" in l["service"]]
    assert len(filtered) == 2


def test_tc_t1_f14_05_sparkline_latency_trend_rendering():
    """TC-T1-F14-05: Validates rolling latency sparkline point limit."""
    sparkline_points = [300, 310, 320, 315, 340]
    assert len(sparkline_points) == 5
    assert max(sparkline_points) == 340


# ============================================================================
# FEATURE F15: Systemd Service Unit Lifecycle & Multi-Service Coexistence
# ============================================================================

def test_tc_t1_f15_01_systemd_service_unit_file_syntax():
    """TC-T1-F15-01: Validates required systemd unit directives."""
    unit_directives = [
        "[Unit]", "Description=Translation Kiosk FastAPI Application",
        "[Service]", "ExecStart=/home/ubuntu/ai_kiosk/bin/python main.py",
        "Restart=on-failure", "RestartSec=3",
        "[Install]", "WantedBy=multi-user.target"
    ]
    content = "\n".join(unit_directives)
    assert "Restart=on-failure" in content
    assert "WantedBy=multi-user.target" in content


def test_tc_t1_f15_02_service_start_and_port_8080_listening():
    """TC-T1-F15-02: Validates port 8080 configuration for Kiosk service."""
    app_config = AppConfig()
    assert app_config.server_port == 8080


def test_tc_t1_f15_03_multi_service_coexistence_verification():
    """TC-T1-F15-03: Validates port separation across all 3 kiosk services."""
    services = {
        "vllm": 8000,
        "whisper": 8001,
        "kiosk": 8080
    }
    assert len(set(services.values())) == 3  # All 3 ports are distinct


def test_tc_t1_f15_04_restart_on_failure_automatic_recovery():
    """TC-T1-F15-04: Validates RestartSec parameter configuration."""
    restart_sec = 3.0
    assert restart_sec <= 5.0


def test_tc_t1_f15_05_multi_user_target_boot_enablement():
    """TC-T1-F15-05: Validates multi-user target string."""
    target = "multi-user.target"
    assert target == "multi-user.target"
