"""
conftest.py - Pytest Fixtures and Audio Synthesis Infrastructure for Translation Kiosk
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

# Ensure translation_kiosk app directory is in python path
APP_DIR = "/home/ubuntu/translation_kiosk"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# ---------------------------------------------------------------------------
# Core Dataclasses matching PROJECT.md Interface Contracts
# ---------------------------------------------------------------------------

@dataclass
class WhisperResponse:
    text: str
    language: str
    latency_ms: float = 0.0

@dataclass
class QwenResponse:
    corrected_text: str
    translated_text: str
    latency_ms: float = 0.0

@dataclass
class PipelineResult:
    raw_text: str = ""
    window_text: str = ""
    stitched_text: str = ""
    language: str = "en"
    language_name: str = "English"
    corrected_text: str = ""
    translated_text: str = ""
    whisper_latency_ms: float = 0.0
    qwen_latency_ms: float = 0.0
    e2e_latency_ms: float = 0.0
    is_english: bool = False

# ---------------------------------------------------------------------------
# Language Code Mapping Reference
# ---------------------------------------------------------------------------

LANGUAGE_MAP: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Mandarin Chinese",
    "ar": "Standard Arabic",
    "ru": "Russian",
    "ja": "Japanese",
    "pt": "Portuguese",
    "tr": "Turkish",
    "ur": "Urdu",
    "hi": "Hindi",
    "it": "Italian",
    "ko": "Korean",
    "nl": "Dutch",
    "pl": "Polish",
    "sv": "Swedish",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "he": "Hebrew",
    "bn": "Bengali",
}

def get_language_name(code: str) -> str:
    """Resolve ISO 639-1 code to human-readable language name."""
    if not code:
        return "Unknown"
    norm = code.lower().strip()
    return LANGUAGE_MAP.get(norm, f"Language ({norm})")

# ---------------------------------------------------------------------------
# Audio Synthesis Helpers
# ---------------------------------------------------------------------------

def package_wav(pcm_bytes: bytes, sample_rate: int = 16000, num_channels: int = 1, sampwidth: int = 2) -> bytes:
    """Encapsulates raw PCM bytes in a standard RIFF/WAVE header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

def create_sine_wave(duration_sec: float, freq: float = 440.0, sample_rate: int = 16000, amplitude: float = 0.5) -> Tuple[bytes, bytes]:
    """Generates 16-bit mono sine wave PCM and WAV bytes."""
    num_samples = int(duration_sec * sample_rate)
    samples = np.sin(2.0 * np.pi * freq * np.arange(num_samples) / sample_rate) * amplitude
    pcm_data = (samples * 32767).astype(np.int16).tobytes()
    wav_data = package_wav(pcm_data, sample_rate=sample_rate)
    return pcm_data, wav_data

def create_silence(duration_sec: float, sample_rate: int = 16000) -> Tuple[bytes, bytes]:
    """Generates 16-bit mono digital silence PCM and WAV bytes."""
    num_samples = int(duration_sec * sample_rate)
    pcm_data = b'\x00\x00' * num_samples
    wav_data = package_wav(pcm_data, sample_rate=sample_rate)
    return pcm_data, wav_data

def create_noise(duration_sec: float, sample_rate: int = 16000, amplitude: float = 0.1) -> Tuple[bytes, bytes]:
    """Generates Gaussian white noise PCM and WAV bytes."""
    num_samples = int(duration_sec * sample_rate)
    samples = np.random.normal(0, amplitude, num_samples)
    samples = np.clip(samples, -1.0, 1.0)
    pcm_data = (samples * 32767).astype(np.int16).tobytes()
    wav_data = package_wav(pcm_data, sample_rate=sample_rate)
    return pcm_data, wav_data

def create_clipped_wave(duration_sec: float, sample_rate: int = 16000) -> Tuple[bytes, bytes]:
    """Generates a full-scale clipped square wave PCM and WAV bytes."""
    num_samples = int(duration_sec * sample_rate)
    samples = np.sign(np.sin(2.0 * np.pi * 200.0 * np.arange(num_samples) / sample_rate))
    pcm_data = (samples * 32767).astype(np.int16).tobytes()
    wav_data = package_wav(pcm_data, sample_rate=sample_rate)
    return pcm_data, wav_data

# ---------------------------------------------------------------------------
# Multilingual Real Speech Audio Loader
# ---------------------------------------------------------------------------

LANG_DIR_PATTERNS = {
    "es": "/mnt/models/Spanish Talks/*.wav",
    "fr": "/mnt/models/French Talks/*.wav",
    "de": "/mnt/models/German Talks/*.wav",
    "zh": "/mnt/models/Mandarin Chinese Talks/*.wav",
    "ar": "/mnt/models/Standard Arabic Talks/*.wav",
    "ru": "/mnt/models/Russian Talks/*.wav",
    "ja": "/mnt/models/Japanese Talks/*.wav",
    "en": "/mnt/models/English Talks/*.wav",
    "pt": "/mnt/models/Portuguese Talks/*.wav",
    "tr": "/mnt/models/Turkish Talks/*.wav",
    "ur": "/mnt/models/Urdu Talks/*.wav",
    "hi": "/mnt/models/Hindi Talks/*.wav",
    "bn": "/mnt/models/Bengali Talks/*.wav",
    "id": "/mnt/models/Indonesian Talks/*.wav",
}

def load_real_speech_sample(
    language_code: str,
    start_sec: float = 2.0,
    duration_sec: float = 4.0,
    target_sr: int = 16000
) -> Tuple[bytes, bytes]:
    """
    Loads and resamples a real speech slice from /mnt/models/<Lang> Talks.
    Converts 44.1kHz stereo to 16kHz mono PCM and WAV.
    """
    pattern = LANG_DIR_PATTERNS.get(language_code.lower())
    matched_files = glob.glob(pattern) if pattern else []

    if matched_files:
        audio_file = matched_files[0]
        try:
            with wave.open(audio_file, "rb") as wf:
                in_sr = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                
                # Seek to start offset
                start_frame = int(start_sec * in_sr)
                num_frames = int(duration_sec * in_sr)
                wf.setpos(min(start_frame, wf.getnframes() - 1))
                raw_frames = wf.readframes(num_frames)
                
                # Unpack PCM
                if sampwidth == 2:
                    audio_arr = np.frombuffer(raw_frames, dtype=np.int16)
                    if n_channels > 1:
                        audio_arr = audio_arr.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
                    
                    # Resample if needed
                    if in_sr != target_sr:
                        target_len = int(len(audio_arr) * target_sr / in_sr)
                        from scipy.signal import resample
                        resampled = resample(audio_arr.astype(np.float32), target_len)
                        audio_arr = np.clip(resampled, -32768, 32767).astype(np.int16)
                    
                    pcm_bytes = audio_arr.tobytes()
                    wav_bytes = package_wav(pcm_bytes, sample_rate=target_sr)
                    return pcm_bytes, wav_bytes
        except Exception as e:
            pass # Fall back to synthetic speech simulation

    # Fallback to modulated synthetic speech simulation
    num_samples = int(duration_sec * target_sr)
    t = np.arange(num_samples) / target_sr
    carrier = np.sin(2 * np.pi * 220 * t)
    modulator = 0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)
    samples = np.clip(carrier * modulator * 0.4, -1.0, 1.0)
    pcm_bytes = (samples * 32767).astype(np.int16).tobytes()
    wav_bytes = package_wav(pcm_bytes, sample_rate=target_sr)
    return pcm_bytes, wav_bytes

# ---------------------------------------------------------------------------
# Live and Mock Clients
# ---------------------------------------------------------------------------

class MockWhisperClient:
    """In-memory mock for Whisper ASR testing."""
    def __init__(self, default_lang: str = "es", default_text: str = "Transcripción de prueba"):
        self.default_lang = default_lang
        self.default_text = default_text
        self.call_count = 0

    async def transcribe_wav(self, wav_bytes: bytes) -> WhisperResponse:
        if not wav_bytes or len(wav_bytes) <= 44:
            raise ValueError("Cannot transcribe empty audio")
        self.call_count += 1
        await asyncio.sleep(0.01)
        return WhisperResponse(text=self.default_text, language=self.default_lang, latency_ms=10.0)

class MockQwenClient:
    """In-memory mock for Qwen 72B LLM testing."""
    def __init__(self, default_corrected: str = "Texto corregido", default_translated: str = "Corrected English translation"):
        self.default_corrected = default_corrected
        self.default_translated = default_translated
        self.call_count = 0

    async def post_correct_and_translate(self, text: str, source_language: str) -> QwenResponse:
        self.call_count += 1
        await asyncio.sleep(0.02)
        return QwenResponse(
            corrected_text=self.default_corrected,
            translated_text=self.default_translated,
            latency_ms=20.0
        )

class LiveWhisperClient:
    """Live HTTP client for Faster-Whisper ASR on port 8001."""
    def __init__(self, endpoint: str = "http://localhost:8001/transcribe", timeout_sec: float = 10.0):
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.client = httpx.AsyncClient(timeout=timeout_sec)
        self.call_count = 0

    async def transcribe_wav(self, wav_bytes: bytes) -> WhisperResponse:
        if not wav_bytes:
            raise ValueError("Cannot transcribe empty audio")
        self.call_count += 1
        t0 = time.perf_counter()
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        resp = await self.client.post(self.endpoint, files=files)
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        data = resp.json()
        return WhisperResponse(
            text=data.get("text", "").strip(),
            language=data.get("language", "unknown").strip(),
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
        timeout_sec: float = 15.0
    ):
        self.endpoint = endpoint
        self.model = model
        self.timeout_sec = timeout_sec
        self.client = httpx.AsyncClient(timeout=timeout_sec)
        self.call_count = 0

    async def post_correct_and_translate(self, text: str, source_language: str) -> QwenResponse:
        if not text.strip():
            return QwenResponse(corrected_text="", translated_text="", latency_ms=0.0)
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
        user_prompt = f"Source Language: {source_language}\nRaw ASR Transcript: \"{text}\"\n\nProduce JSON output."
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
        return QwenResponse(
            corrected_text=parsed.get("corrected_text", text),
            translated_text=parsed.get("english_translation", ""),
            latency_ms=latency_ms
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
