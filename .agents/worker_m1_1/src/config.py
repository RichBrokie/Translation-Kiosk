"""
Central configuration for Translation Kiosk.
Contains audio parameters, service URLs, model names, timeouts, and language mappings.
"""
from dataclasses import dataclass, field
from typing import Dict, Any

# ============================================================================
# Audio Streaming Parameters (16kHz, 16-bit Mono PCM)
# ============================================================================
SAMPLE_RATE: int = 16000
BYTES_PER_SAMPLE: int = 2  # 16-bit signed integer Little-Endian
CHANNELS: int = 1          # Mono
BYTE_RATE: int = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS  # 32,000 bytes/sec

# Sliding Window Slicing Configuration
WINDOW_SEC: float = 4.0    # 4.0 seconds window (128,000 bytes)
STRIDE_SEC: float = 2.0    # 2.0 seconds stride / step (64,000 bytes)
OVERLAP_SEC: float = WINDOW_SEC - STRIDE_SEC  # 2.0 seconds overlap
MIN_FLUSH_SEC: float = 0.5 # Minimum residual audio required to trigger final transcription (16,000 bytes)
MAX_RETENTION_SEC: float = 12.0 # In-memory buffer prune retention limit

# Exact Byte Offsets
WINDOW_BYTES: int = int(WINDOW_SEC * BYTE_RATE)      # 128,000 bytes
STRIDE_BYTES: int = int(STRIDE_SEC * BYTE_RATE)      # 64,000 bytes
OVERLAP_BYTES: int = int(OVERLAP_SEC * BYTE_RATE)    # 64,000 bytes
MIN_FLUSH_BYTES: int = int(MIN_FLUSH_SEC * BYTE_RATE)# 16,000 bytes
MAX_RETENTION_BYTES: int = int(MAX_RETENTION_SEC * BYTE_RATE)

# ============================================================================
# Service Endpoints & Network Configuration
# ============================================================================
WHISPER_BASE_URL: str = "http://localhost:8001"
WHISPER_TRANSCRIBE_URL: str = f"{WHISPER_BASE_URL}/transcribe"

VLLM_BASE_URL: str = "http://localhost:8000/v1"
VLLM_COMPLETIONS_URL: str = f"{VLLM_BASE_URL}/chat/completions"

SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8080

# ============================================================================
# Model & Client Settings
# ============================================================================
QWEN_MODEL_NAME: str = "/mnt/models/qwen2.5-72b-instruct-awq"

# Timeouts & Connection Limits
WHISPER_TIMEOUT_SEC: float = 4.0
QWEN_TIMEOUT_SEC: float = 6.0
HTTP_MAX_CONNECTIONS: int = 20
HTTP_MAX_KEEPALIVE: int = 10
HTTP_KEEPALIVE_EXPIRY_SEC: float = 30.0

WHISPER_MAX_RETRIES: int = 2
QWEN_MAX_RETRIES: int = 1

# ============================================================================
# Language Mappings (ISO 639-1 to Full Display Name)
# ============================================================================
LANGUAGE_NAMES: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ar": "Arabic",
    "ja": "Japanese",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ko": "Korean",
    "hi": "Hindi",
    "nl": "Dutch",
    "tr": "Turkish",
    "pl": "Polish",
    "sv": "Swedish",
    "vi": "Vietnamese",
    "uk": "Ukrainian",
    "el": "Greek",
    "cs": "Czech",
    "ro": "Romanian",
    "da": "Danish",
    "fi": "Finnish",
    "hu": "Hungarian",
    "he": "Hebrew",
    "id": "Indonesian",
    "th": "Thai",
    "no": "Norwegian",
    "fa": "Persian",
    "ur": "Urdu",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "tl": "Tagalog",
    "ms": "Malay",
    "sw": "Swahili"
}

def get_language_name(code: str) -> str:
    """Returns human-readable language name for an ISO 639-1 code."""
    if not code:
        return "Unknown"
    code_lower = code.lower().strip()
    return LANGUAGE_NAMES.get(code_lower, code.capitalize())

@dataclass
class AppConfig:
    sample_rate: int = SAMPLE_RATE
    bytes_per_sample: int = BYTES_PER_SAMPLE
    channels: int = CHANNELS
    window_sec: float = WINDOW_SEC
    stride_sec: float = STRIDE_SEC
    whisper_url: str = WHISPER_TRANSCRIBE_URL
    vllm_url: str = VLLM_COMPLETIONS_URL
    qwen_model: str = QWEN_MODEL_NAME
    server_host: str = SERVER_HOST
    server_port: int = SERVER_PORT
    whisper_timeout_sec: float = WHISPER_TIMEOUT_SEC
    qwen_timeout_sec: float = QWEN_TIMEOUT_SEC
    bypass_english: bool = True
