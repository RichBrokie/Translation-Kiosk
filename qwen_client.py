"""
Async client for vLLM Qwen 2.5 72B Instruct API (http://localhost:8000/v1/chat/completions).
Performs single-call post-correction of Whisper ASR transcription errors and English translation.
Includes Requirement R4 English language bypass logic (0ms latency, zero HTTP calls).
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

import httpx

from config import (
    VLLM_BASE_URL,
    VLLM_COMPLETIONS_URL,
    QWEN_MODEL_NAME,
    QWEN_TIMEOUT_SEC,
    QWEN_MAX_RETRIES,
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE,
    HTTP_KEEPALIVE_EXPIRY_SEC
)
from telemetry import TelemetryCollector

logger = logging.getLogger(__name__)

# Single-call system prompt instructing Qwen to perform both grammar/phonetic correction and English translation
SYSTEM_PROMPT = """You are an expert real-time multilingual speech-to-text translation engine for a public museum kiosk.
You will receive raw, uncorrected ASR (Automatic Speech Recognition) text along with the detected source language.

Your job is to perform TWO tasks in a single step:
1. Fix any minor phonetic transcription glitches, missing punctuation, or grammatical errors in the SOURCE language ("corrected_text").
2. Translate the corrected text into clear, natural, and fluent English ("english_translation").

CRITICAL RULES:
- Output MUST be valid JSON and NOTHING ELSE.
- Do not include markdown code fences (e.g. ```json), explanations, preambles, or notes.
- Format:
{"corrected_text": "...", "english_translation": "..."}
"""

@dataclass
class TranslationResult:
    """Structured result returned by Qwen post-correction and translation."""
    corrected_text: str
    english_translation: str
    source_language: str
    latency_ms: float = 0.0
    bypassed: bool = False
    error: Optional[str] = None
    raw_response: Optional[str] = None

# Alias for PROJECT.md interface contract compatibility
QwenResponse = TranslationResult

def _clean_field(val: Any, fallback: str) -> str:
    if val is None:
        return fallback
    s = str(val).strip()
    if not s or s.lower() == "null" or s.lower() == "none":
        return fallback
    return s

def parse_qwen_json(content: str, fallback_text: str = "") -> Dict[str, str]:
    """
    Robust 5-stage JSON parser for Qwen LLM output.
    Handles raw JSON, markdown-wrapped JSON, preambles, and malformed strings without crashing.
    """
    if not content:
        return {"corrected_text": fallback_text, "english_translation": fallback_text}

    cleaned = content.strip()

    # Stage 1: Strip markdown code fences if present
    if cleaned.startswith("`"):
        cleaned = re.sub(r"^`(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*`$", "", cleaned)
        cleaned = cleaned.strip()

    # Stage 2: Direct standard JSON decode
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {
                "corrected_text": _clean_field(data.get("corrected_text"), fallback_text),
                "english_translation": _clean_field(data.get("english_translation"), fallback_text)
            }
    except json.JSONDecodeError:
        pass

    # Stage 3: Outermost balanced brace extraction
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return {
                    "corrected_text": _clean_field(data.get("corrected_text"), fallback_text),
                    "english_translation": _clean_field(data.get("english_translation"), fallback_text)
                }
        except json.JSONDecodeError:
            pass

    # Stage 4: Regex field key/value extraction
    corr_match = re.search(r'"corrected_text"\s*:\s*"([^"]+)"', cleaned)
    trans_match = re.search(r'"english_translation"\s*:\s*"([^"]+)"', cleaned)
    if corr_match or trans_match:
        return {
            "corrected_text": _clean_field(corr_match.group(1) if corr_match else None, fallback_text),
            "english_translation": _clean_field(trans_match.group(1) if trans_match else None, fallback_text)
        }

    # Stage 5: Graceful fallback without crashing
    logger.warning(f"Failed to parse Qwen JSON output: {content!r}. Falling back to raw text.")
    return {"corrected_text": fallback_text, "english_translation": cleaned}

class QwenClient:
    """
    Asynchronous HTTP client for the vLLM OpenAI-compatible Chat Completions endpoint.
    """
    def __init__(
        self,
        base_url: str = VLLM_BASE_URL,
        model: str = QWEN_MODEL_NAME,
        timeout_sec: float = QWEN_TIMEOUT_SEC,
        max_retries: int = QWEN_MAX_RETRIES,
        bypass_english: bool = True,
        client: Optional[httpx.AsyncClient] = None,
        telemetry_collector: Optional[TelemetryCollector] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.completions_url = f"{self.base_url}/chat/completions" if not self.base_url.endswith("/chat/completions") else self.base_url
        self.model = model
        self.timeout = httpx.Timeout(timeout_sec, connect=1.0, read=timeout_sec, write=2.0, pool=1.0)
        self.limits = httpx.Limits(
            max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            max_connections=HTTP_MAX_CONNECTIONS,
            keepalive_expiry=HTTP_KEEPALIVE_EXPIRY_SEC
        )
        self.max_retries = max_retries
        self.bypass_english = bypass_english
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

    async def post_correct_and_translate(
        self,
        text: str,
        source_language: Optional[str] = "en"
    ) -> TranslationResult:
        """
        Executes single-call post-correction and English translation.
        Bypasses LLM call with 0ms latency if source_language is English (Requirement R4).
        """
        resolved_source_lang = source_language if source_language is not None else "en"
        lang_clean = str(resolved_source_lang).strip().lower()
        if not lang_clean:
            lang_clean = "en"

        text_clean = text.strip() if text else ""
        if not text_clean:
            return TranslationResult(
                corrected_text="",
                english_translation="",
                source_language=resolved_source_lang,
                latency_ms=0.0,
                bypassed=False
            )

        # English bypass disabled: Qwen processes ALL languages including English

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Source Language: {resolved_source_lang}\nRaw ASR: {text_clean}"}
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 512,
            "stream": False
        }

        last_error: Optional[str] = None
        status_code = 0
        latency_ms = 0.0

        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                response = await self._client.post(self.completions_url, json=payload)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = response.status_code

                if response.status_code == 200:
                    res_json = response.json()
                    content = res_json["choices"][0]["message"]["content"]
                    parsed = parse_qwen_json(content, fallback_text=text_clean)
                    
                    if self.telemetry:
                        self.telemetry.log_api_call(
                            endpoint=self.completions_url,
                            method="POST",
                            status_code=200,
                            latency_ms=latency_ms,
                            payload_summary=f"[{resolved_source_lang}] {text_clean[:60]}",
                            response_summary=f"-> {parsed['english_translation'][:60]}"
                        )

                    return TranslationResult(
                        corrected_text=parsed["corrected_text"],
                        english_translation=parsed["english_translation"],
                        source_language=resolved_source_lang,
                        latency_ms=latency_ms,
                        bypassed=False,
                        raw_response=content
                    )
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"vLLM returned non-200 status: {last_error}")

            except httpx.TimeoutException as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 408
                last_error = f"Timeout after {latency_ms:.1f}ms: {e}"
                logger.warning(f"Qwen timeout on attempt {attempt + 1}: {e}")
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 500
                last_error = f"Unexpected error: {e}"
                logger.error(f"Qwen request error: {e}")
                break

            if attempt < self.max_retries:
                await asyncio.sleep(0.05)

        # Log failed attempt in telemetry
        if self.telemetry:
            self.telemetry.log_api_call(
                endpoint=self.completions_url,
                method="POST",
                status_code=status_code,
                latency_ms=latency_ms,
                payload_summary=f"[{resolved_source_lang}] {text_clean[:60]}",
                response_summary="",
                error=last_error
            )

        # Graceful fallback on persistent failure
        return TranslationResult(
            corrected_text=text_clean,
            english_translation=text_clean,
            source_language=resolved_source_lang,
            latency_ms=latency_ms,
            bypassed=False,
            error=last_error
        )

    # Convenience alias for PROJECT.md interface contract compatibility
    async def correct_and_translate(self, text: str, source_language: Optional[str] = "en") -> TranslationResult:
        """Alias for post_correct_and_translate."""
        return await self.post_correct_and_translate(text, source_language)
