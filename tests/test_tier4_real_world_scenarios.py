"""
test_tier4_real_world_scenarios.py - Tier 4 Real-World Multilingual Audio Workload Scenarios (8 Test Cases)
Validates real-world audio playback across Spanish, French, German, Mandarin, Arabic, Russian, Japanese, and English with noise using real audio from /mnt/models/* Talks/*.wav.
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
async def test_tc_t4_real_world_01_spanish_continuous_speech():
    """Scenario 1: Spanish Continuous Speech (es) using real speech audio."""
    pcm, wav = load_real_speech_sample("es", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    telemetry = TelemetryCollector()
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client, telemetry_collector=telemetry)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "es"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_02_french_conversational_speech():
    """Scenario 2: French Conversational Speech (fr) using real speech audio."""
    pcm, wav = load_real_speech_sample("fr", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "fr"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_03_german_compound_speech():
    """Scenario 3: German Speech with Compound Nouns (de) using real speech audio."""
    pcm, wav = load_real_speech_sample("de", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "de"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_04_mandarin_chinese_speech():
    """Scenario 4: Mandarin Chinese Continuous Speech (zh) using real speech audio."""
    pcm, wav = load_real_speech_sample("zh", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "zh"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_05_standard_arabic_speech():
    """Scenario 5: Standard Arabic Speech (ar) using real speech audio."""
    pcm, wav = load_real_speech_sample("ar", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "ar"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_06_russian_cyrillic_speech():
    """Scenario 6: Russian Speech with Cyrillic Script (ru) using real speech audio."""
    pcm, wav = load_real_speech_sample("ru", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "ru"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_07_japanese_honorific_speech():
    """Scenario 7: Japanese Speech with Kanji/Hiragana (ja) using real speech audio."""
    pcm, wav = load_real_speech_sample("ja", duration_sec=4.0)
    assert len(pcm) == 128000
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)
    
    res = await pipeline.process_chunk(pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.qwen_latency_ms < 8000.0
    assert res.language == "ja"
    assert len(res.window_text or res.raw_text) > 0
    assert len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()


@pytest.mark.asyncio
async def test_tc_t4_real_world_08_english_noisy_speech_bypass():
    """Scenario 8: English Speech with Background Noise (en) - Bypass Verification (0ms Qwen)."""
    raw_pcm, _ = load_real_speech_sample("en", duration_sec=4.0)
    
    # Mix with synthetic background noise at 15dB SNR
    noise_pcm, _ = create_noise(duration_sec=4.0, amplitude=0.02)
    raw_arr = np.frombuffer(raw_pcm, dtype=np.int16)
    noise_arr = np.frombuffer(noise_pcm, dtype=np.int16)
    mixed_arr = np.clip(raw_arr.astype(np.int32) + noise_arr.astype(np.int32), -32768, 32767).astype(np.int16)
    noisy_pcm = mixed_arr.tobytes()
    
    whisper_client = WhisperClient(base_url="http://localhost:8001")
    qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    telemetry = TelemetryCollector()
    pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client, telemetry_collector=telemetry)
    
    res = await pipeline.process_chunk(noisy_pcm)
    assert res is not None
    assert res.whisper_latency_ms < 5000.0
    assert res.is_english is True
    assert res.qwen_latency_ms == 0.0  # strictly 0ms bypass
    assert res.e2e_latency_ms < 5000.0
    assert len(res.window_text or res.raw_text) > 0
    assert res.translated_text == res.window_text or res.translated_text == res.raw_text or len(res.translated_text) > 0
    await whisper_client.close()
    await qwen_client.close()

