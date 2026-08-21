"""
conftest.py - Pytest Fixtures, Audio Synthesis & Test Harness for Translation Kiosk
"""

import os
import sys
import math
import struct
import io
import wave
import json
import time
import glob
import asyncio
import numpy as np
import pytest
import pytest_asyncio
import httpx
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from unittest.mock import AsyncMock, MagicMock

# Ensure translation_kiosk app directory is in python path
APP_DIR = "/home/ubuntu/translation_kiosk"
TESTS_DIR = "/home/ubuntu/translation_kiosk/tests"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from config import get_language_name, LANGUAGE_NAMES
from whisper_client import TranscriptionResult, WhisperResponse
from qwen_client import TranslationResult, QwenResponse
from audio_pipeline import PipelineResult

# ---------------------------------------------------------------------------
# Audio Synthesis & Processing Helpers
# ---------------------------------------------------------------------------

def package_wav(pcm_bytes: bytes, sample_rate: int = 16000, num_channels: int = 1, sampwidth: int = 2) -> bytes:
    """Encapsulates raw PCM bytes in a standard 44-byte RIFF/WAVE header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

def create_sine_wave(duration_sec: float = 4.0, freq: float = 440.0, sample_rate: int = 16000, amplitude: float = 0.5) -> Tuple[bytes, bytes]:
    """Generates pure sine wave audio as (pcm_bytes, wav_bytes)."""
    num_samples = int(duration_sec * sample_rate)
    t = np.arange(num_samples) / sample_rate
    samples = (amplitude * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    pcm_bytes = samples.tobytes()
    wav_bytes = package_wav(pcm_bytes, sample_rate=sample_rate)
    return pcm_bytes, wav_bytes

def create_silence(duration_sec: float = 4.0, sample_rate: int = 16000) -> Tuple[bytes, bytes]:
    """Generates digital silence (all 0x00) as (pcm_bytes, wav_bytes)."""
    num_samples = int(duration_sec * sample_rate)
    pcm_bytes = b"\x00\x00" * num_samples
    wav_bytes = package_wav(pcm_bytes, sample_rate=sample_rate)
    return pcm_bytes, wav_bytes

def create_noise(duration_sec: float = 4.0, sample_rate: int = 16000, amplitude: float = 0.1) -> Tuple[bytes, bytes]:
    """Generates Gaussian white noise as (pcm_bytes, wav_bytes)."""
    num_samples = int(duration_sec * sample_rate)
    samples = (np.random.normal(0, amplitude, num_samples) * 32767).clip(-32768, 32767).astype(np.int16)
    pcm_bytes = samples.tobytes()
    wav_bytes = package_wav(pcm_bytes, sample_rate=sample_rate)
    return pcm_bytes, wav_bytes

def create_clipped_wave(duration_sec: float = 4.0, freq: float = 220.0, sample_rate: int = 16000) -> Tuple[bytes, bytes]:
    """Generates full-scale square/clipped audio as (pcm_bytes, wav_bytes)."""
    num_samples = int(duration_sec * sample_rate)
    t = np.arange(num_samples) / sample_rate
    samples = np.where(np.sin(2 * np.pi * freq * t) >= 0, 32767, -32768).astype(np.int16)
    pcm_bytes = samples.tobytes()
    wav_bytes = package_wav(pcm_bytes, sample_rate=sample_rate)
    return pcm_bytes, wav_bytes

# ---------------------------------------------------------------------------
# Multilingual Audio Slicer & Loader
# ---------------------------------------------------------------------------

LANG_FOLDER_MAP = {
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Mandarin Chinese",
    "ar": "Standard Arabic",
    "ru": "Russian",
    "ja": "Japanese",
    "en": "English",
    "pt": "Portuguese",
    "tr": "Turkish",
    "hi": "Hindi",
    "ur": "Urdu",
    "id": "Indonesian",
    "bn": "Bengali"
}

NATIVE_FILE_PREFERENCES = {
    "es": (["Canaliza", "*"], 15.0),
    "fr": (["Choisir", "*"], 15.0),
    "de": (["K\u00f6nig", "Die Kunst", "*"], 15.0),
    "zh": (["Speaking mandarin", "Examples of wrong", "*"], 30.0),
    "ar": (["TEDx", "*"], 15.0),
    "ru": (["\u0418\u0441\u043a\u0443\u0441\u0441\u0442\u0432\u043e", "\u0420\u0430\u0437\u0440\u0435\u0448\u0438", "*"], 15.0),
    "ja": (["TEDx", "*"], 15.0),
    "en": (["TED", "*"], 15.0)
}

def load_real_speech_sample(
    lang_code: str,
    start_sec: Optional[float] = None,
    duration_sec: float = 4.0,
    target_sr: int = 16000
) -> Tuple[bytes, bytes]:
    """
    Extracts a sliced PCM and WAV sample from /mnt/models/<Language> Talks/*.wav.
    Downmixes stereo to mono and resamples to 16kHz.
    """
    lang_folder = LANG_FOLDER_MAP.get(lang_code.lower(), "Spanish")
    patterns, default_start = NATIVE_FILE_PREFERENCES.get(lang_code.lower(), (["*"], 15.0))
    offset_sec = start_sec if start_sec is not None else default_start
    
    all_files = sorted(glob.glob(f"/mnt/models/{lang_folder} Talks/*.wav"))
    selected_file = None
    for pat in patterns:
        for f in all_files:
            if pat in os.path.basename(f) or pat == "*":
                selected_file = f
                break
        if selected_file:
            break
            
    if not selected_file and all_files:
        selected_file = all_files[0]
            
    if selected_file:
        try:
            with wave.open(selected_file, "rb") as wf:
                in_sr = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                
                start_frame = int(offset_sec * in_sr)
                num_frames = int(duration_sec * in_sr)
                wf.setpos(min(start_frame, max(0, wf.getnframes() - num_frames)))
                raw_data = wf.readframes(num_frames)
                
                if len(raw_data) > 0:
                    audio_arr = np.frombuffer(raw_data, dtype=np.int16)
                    if n_channels > 1:
                        audio_arr = audio_arr.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
                    
                    if in_sr != target_sr:
                        from scipy.signal import resample
                        target_len = int(len(audio_arr) * target_sr / in_sr)
                        resampled = resample(audio_arr.astype(np.float32), target_len)
                        audio_arr = np.clip(resampled, -32768, 32767).astype(np.int16)
                    
                    pcm_bytes = audio_arr.tobytes()
                    wav_bytes = package_wav(pcm_bytes, sample_rate=target_sr)
                    return pcm_bytes, wav_bytes
        except Exception:
            pass

    # Modulated speech fallback
    num_samples = int(duration_sec * target_sr)
    t = np.arange(num_samples) / target_sr
    carrier = np.sin(2 * np.pi * 220 * t)
    modulator = 0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)
    samples = np.clip(carrier * modulator * 0.4, -1.0, 1.0)
    pcm_bytes = (samples * 32767).astype(np.int16).tobytes()
    wav_bytes = package_wav(pcm_bytes, sample_rate=target_sr)
    return pcm_bytes, wav_bytes

# ---------------------------------------------------------------------------
# In-Memory Mocks for Isolated Component Testing
# ---------------------------------------------------------------------------

class MockWhisperClient:
    """In-memory mock for Whisper ASR testing."""
    def __init__(self, default_lang: str = "es", default_text: str = "Transcripci?n de prueba"):
        self.default_lang = default_lang
        self.default_text = default_text
        self.call_count = 0

    async def transcribe_wav(self, wav_bytes: bytes, filename: str = "chunk.wav") -> TranscriptionResult:
        if not wav_bytes or len(wav_bytes) <= 44:
            raise ValueError("Cannot transcribe empty audio")
        self.call_count += 1
        await asyncio.sleep(0.01)
        return TranscriptionResult(
            text=self.default_text,
            language=self.default_lang,
            language_name=get_language_name(self.default_lang),
            latency_ms=15.0
        )

    async def aclose(self):
        pass

class MockQwenClient:
    """In-memory mock for Qwen 72B LLM testing."""
    def __init__(self, default_corrected: str = "Texto corregido", default_translated: str = "Corrected English translation", bypass_english: bool = True):
        self.default_corrected = default_corrected
        self.default_translated = default_translated
        self.bypass_english = bypass_english
        self.call_count = 0

    async def post_correct_and_translate(self, text: str, source_language: str = "es") -> TranslationResult:
        text_clean = text.strip()
        if not text_clean:
            return TranslationResult(
                corrected_text="",
                english_translation="",
                source_language=source_language,
                latency_ms=0.0
            )
        
        lang_lower = source_language.lower().strip()
        if self.bypass_english and lang_lower in ("en", "english"):
            return TranslationResult(
                corrected_text=text_clean,
                english_translation=text_clean,
                source_language=source_language,
                latency_ms=0.0,
                bypassed=True
            )

        self.call_count += 1
        await asyncio.sleep(0.02)
        return TranslationResult(
            corrected_text=self.default_corrected or text_clean,
            english_translation=self.default_translated,
            source_language=source_language,
            latency_ms=25.0,
            bypassed=False
        )

    async def aclose(self):
        pass

# ---------------------------------------------------------------------------
# Live Clients Connecting to Active GPU Services (:8001 & :8000)
# ---------------------------------------------------------------------------

class LiveWhisperClient:
    """Live HTTP client for Faster-Whisper ASR on port 8001."""
    def __init__(self, endpoint: str = "http://localhost:8001/transcribe", timeout_sec: float = 10.0):
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.client = httpx.AsyncClient(timeout=timeout_sec)
        self.call_count = 0

    async def transcribe_wav(self, wav_bytes: bytes, filename: str = "chunk.wav") -> TranscriptionResult:
        if not wav_bytes:
            raise ValueError("Cannot transcribe empty audio")
        self.call_count += 1
        t0 = time.perf_counter()
        files = {"file": (filename, wav_bytes, "audio/wav")}
        resp = await self.client.post(self.endpoint, files=files)
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        data = resp.json()
        lang = data.get("language", "unknown").strip()
        return TranscriptionResult(
            text=data.get("text", "").strip(),
            language=lang,
            language_name=get_language_name(lang),
            latency_ms=latency_ms
        )

    async def aclose(self):
        await self.client.aclose()

class LiveQwenClient:
    """Live HTTP client for Qwen 2.5 72B Instruct AWQ on port 8000."""
    def __init__(
        self,
        endpoint: str = "http://localhost:8000/v1/chat/completions",
        model: str = "/mnt/models/qwen2.5-72b-instruct-awq",
        timeout_sec: float = 15.0,
        bypass_english: bool = True
    ):
        self.endpoint = endpoint
        self.model = model
        self.timeout_sec = timeout_sec
        self.bypass_english = bypass_english
        self.client = httpx.AsyncClient(timeout=timeout_sec)
        self.call_count = 0

    async def post_correct_and_translate(self, text: str, source_language: str = "es") -> TranslationResult:
        text_clean = text.strip()
        if not text_clean:
            return TranslationResult(
                corrected_text="",
                english_translation="",
                source_language=source_language,
                latency_ms=0.0
            )

        lang_lower = source_language.lower().strip()
        if self.bypass_english and lang_lower in ("en", "english"):
            return TranslationResult(
                corrected_text=text_clean,
                english_translation=text_clean,
                source_language=source_language,
                latency_ms=0.0,
                bypassed=True
            )

        self.call_count += 1
        t0 = time.perf_counter()
        system_prompt = (
            "You are an expert real-time translation kiosk engine. Your task:\n"
            "1. Take raw, potentially noisy or error-prone ASR speech transcripts in any language.\n"
            "2. Contextually correct any grammatical, phonetic, or boundary stitching errors in the source language.\n"
            "3. Accurately translate the corrected text into natural, fluent English.\n"
            "Output strictly valid JSON with exactly two fields:\n"
            "{\n"
            '  "corrected_text": "<corrected transcript in source language>",\n'
            '  "english_translation": "<fluent English translation>"\n'
            "}"
        )
        user_prompt = f"Source Language: {source_language}\nRaw ASR Transcript: \"{text_clean}\"\n\nProduce JSON output."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "response_format": {"type": "json_object"}
        }
        resp = await self.client.post(self.endpoint, json=payload)
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(content)
        return TranslationResult(
            corrected_text=parsed.get("corrected_text", text_clean),
            english_translation=parsed.get("english_translation", ""),
            source_language=source_language,
            latency_ms=latency_ms,
            bypassed=False
        )

    async def aclose(self):
        await self.client.aclose()

# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sine_audio_4s():
    return create_sine_wave(duration_sec=4.0, freq=440.0)

@pytest.fixture
def silence_audio_4s():
    return create_silence(duration_sec=4.0)

@pytest.fixture
def noise_audio_4s():
    return create_noise(duration_sec=4.0)

@pytest.fixture
def clipped_audio_4s():
    return create_clipped_wave(duration_sec=4.0)

@pytest.fixture
def spanish_speech_4s():
    return load_real_speech_sample("es", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def french_speech_4s():
    return load_real_speech_sample("fr", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def german_speech_4s():
    return load_real_speech_sample("de", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def mandarin_speech_4s():
    return load_real_speech_sample("zh", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def arabic_speech_4s():
    return load_real_speech_sample("ar", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def russian_speech_4s():
    return load_real_speech_sample("ru", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def japanese_speech_4s():
    return load_real_speech_sample("ja", start_sec=2.0, duration_sec=4.0)

@pytest.fixture
def english_speech_4s():
    return load_real_speech_sample("en", start_sec=2.0, duration_sec=4.0)

@pytest_asyncio.fixture
async def live_whisper_client():
    client = LiveWhisperClient()
    yield client
    await client.aclose()

@pytest_asyncio.fixture
async def live_qwen_client():
    client = LiveQwenClient()
    yield client
    await client.aclose()

@pytest.fixture
def mock_whisper_client():
    return MockWhisperClient()

@pytest.fixture
def mock_qwen_client():
    return MockQwenClient()

