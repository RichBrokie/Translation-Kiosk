"""
Async client for Faster-Whisper ASR service (http://localhost:8001/transcribe).
Provides connection pooling, retry logic with exponential backoff, and robust error recovery.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
import httpx
import time
import asyncio
import logging

from config import (
    WHISPER_BASE_URL,
    WHISPER_TRANSCRIBE_URL,
    WHISPER_TIMEOUT_SEC,
    WHISPER_MAX_RETRIES,
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE,
    HTTP_KEEPALIVE_EXPIRY_SEC,
    get_language_name
)
from telemetry import TelemetryCollector

logger = logging.getLogger(__name__)

class WhisperClientError(Exception):
    """Base exception for Whisper client errors."""
    pass

class WhisperConnectionError(WhisperClientError):
    """Raised on connection failure to Whisper service."""
    pass

class WhisperTimeoutError(WhisperClientError):
    """Raised when Whisper request times out."""
    pass

@dataclass
class TranscriptionResult:
    """ASR transcription result from Faster-Whisper."""
    text: str
    language: str
    language_name: str = ""
    language_prob: Optional[float] = None
    duration_s: float = 0.0
    latency_ms: float = 0.0
    is_empty: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        if not self.language_name and self.language:
            self.language_name = get_language_name(self.language)
        self.is_empty = len(self.text.strip()) == 0

# Alias for PROJECT.md interface contract compatibility
WhisperResponse = TranscriptionResult

class WhisperClient:
    """
    Asynchronous HTTP client for the Faster-Whisper transcription microservice.
    """
    def __init__(
        self,
        base_url: str = WHISPER_BASE_URL,
        timeout_sec: float = WHISPER_TIMEOUT_SEC,
        max_retries: int = WHISPER_MAX_RETRIES,
        client: Optional[httpx.AsyncClient] = None,
        telemetry_collector: Optional[TelemetryCollector] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.transcribe_url = f"{self.base_url}/transcribe" if not self.base_url.endswith("/transcribe") else self.base_url
        self.timeout = httpx.Timeout(timeout_sec, connect=1.0, read=timeout_sec, write=2.0, pool=1.0)
        self.limits = httpx.Limits(
            max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            max_connections=HTTP_MAX_CONNECTIONS,
            keepalive_expiry=HTTP_KEEPALIVE_EXPIRY_SEC
        )
        self.max_retries = max_retries
        self.telemetry = telemetry_collector
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=self.timeout, limits=self.limits)

    async def open(self) -> None:
        """Ensures the internal HTTP client session is open."""
        if self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout, limits=self.limits)

    async def close(self) -> None:
        """Closes internal HTTP client connection pool if owned."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def transcribe_wav(
        self,
        wav_bytes: bytes,
        filename: str = "chunk.wav"
    ) -> TranscriptionResult:
        """
        Sends standard RIFF/WAV audio binary to Faster-Whisper /transcribe endpoint.
        Retries on transient network/timeout errors with exponential backoff.
        """
        if not wav_bytes:
            return TranscriptionResult(text="", language="en", latency_ms=0.0, is_empty=True)

        files = {"file": (filename, wav_bytes, "audio/wav")}
        form_data = {"language": "en"}
        last_error: Optional[str] = None
        status_code = 0
        latency_ms = 0.0

        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                response = await self._client.post(self.transcribe_url, files=files, data=form_data)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    text = str(data.get("text", "") or "").strip()
                    lang_raw = data.get("language")
                    if lang_raw is not None and str(lang_raw).strip():
                        lang = str(lang_raw).strip().lower()
                    else:
                        lang = "en"
                    prob = data.get("language_prob", None)
                    
                    if self.telemetry:
                        self.telemetry.log_api_call(
                            endpoint=self.transcribe_url,
                            method="POST",
                            status_code=200,
                            latency_ms=latency_ms,
                            payload_summary=f"WAV payload ({len(wav_bytes)}B)",
                            response_summary=f"[{lang}] {text[:60]}"
                        )

                    return TranscriptionResult(
                        text=text,
                        language=lang,
                        language_prob=prob,
                        latency_ms=latency_ms
                    )
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Whisper returned non-200 status: {last_error}")

            except httpx.TimeoutException as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 408
                last_error = f"Timeout after {latency_ms:.1f}ms: {e}"
                logger.warning(f"Whisper timeout on attempt {attempt + 1}/{self.max_retries + 1}: {e}")
            except (httpx.ConnectError, httpx.NetworkError) as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 503
                last_error = f"Connection failed: {e}"
                logger.warning(f"Whisper connection error on attempt {attempt + 1}/{self.max_retries + 1}: {e}")
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 500
                last_error = f"Unexpected error: {e}"
                logger.error(f"Whisper unexpected error: {e}")
                break

            # Exponential backoff before next attempt
            if attempt < self.max_retries:
                await asyncio.sleep(0.05 * (2 ** attempt))

        # Log failed attempt in telemetry
        if self.telemetry:
            self.telemetry.log_api_call(
                endpoint=self.transcribe_url,
                method="POST",
                status_code=status_code,
                latency_ms=latency_ms,
                payload_summary=f"WAV payload ({len(wav_bytes)}B)",
                response_summary="",
                error=last_error
            )

        # Fallback return on persistent failure (preserves pipeline execution)
        return TranscriptionResult(
            text="",
            language="en",
            latency_ms=latency_ms,
            is_empty=True,
            error=last_error or "Unknown Whisper ASR failure"
        )

    # Convenience alias for transcribe
    async def transcribe(self, wav_bytes: bytes) -> TranscriptionResult:
        """Alias for transcribe_wav."""
        return await self.transcribe_wav(wav_bytes)
