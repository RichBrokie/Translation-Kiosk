"""
Adversarial Challenger Test Suite for Milestone 1:
- Client Null-Safety & Malformed Language Parameters
- Synthetic Corrupt Audio Chunks & Robust WAV Packaging
- Network Latency Spikes, Disconnects, & Transient Error Recovery
- AudioPipeline Streaming & Session Flush Boundary Matrix
- Live / Mock End-to-End Execution Under Stress
"""
import asyncio
import io
import json
import math
import os
import struct
import time
import wave
from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import numpy as np
import pytest

from config import (
    SAMPLE_RATE,
    BYTES_PER_SAMPLE,
    CHANNELS,
    BYTE_RATE,
    WINDOW_SEC,
    STRIDE_SEC,
    WINDOW_BYTES,
    STRIDE_BYTES,
    MIN_FLUSH_BYTES,
    MAX_RETENTION_BYTES,
    get_language_name
)
from whisper_client import (
    WhisperClient,
    TranscriptionResult,
    WhisperClientError,
    WhisperConnectionError,
    WhisperTimeoutError
)
from qwen_client import (
    QwenClient,
    TranslationResult,
    parse_qwen_json
)
from audio_pipeline import (
    AudioRollingBuffer,
    TextStitcher,
    ComparativeEngine,
    AudioPipeline,
    PipelineResult,
    pack_pcm_to_wav
)
from telemetry import TelemetryCollector, ChunkTelemetry


# ============================================================================
# 1. CLIENT NULL-SAFETY & MALFORMED PARAMETERS
# ============================================================================

class TestClientNullSafetyAndMalformedParams:
    """Adversarially tests clients against None, empty, and malformed inputs."""

    @pytest.mark.asyncio
    async def test_whisper_client_empty_and_zero_byte_wav(self):
        """WhisperClient should handle empty byte arrays safely without HTTP calls."""
        client = WhisperClient()
        res = await client.transcribe_wav(b"")
        assert res.is_empty is True
        assert res.text == ""
        assert res.language == "en"
        assert res.latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_whisper_client_null_language_in_server_json(self):
        """Whisper returns JSON with language=None or language=''."""
        mock_response = httpx.Response(
            status_code=200,
            json={"text": "Bonjour tout le monde", "language": None, "language_prob": None},
            request=httpx.Request("POST", "http://localhost:8001/transcribe")
        )
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.return_value = mock_response

        client = WhisperClient(client=mock_http)
        res = await client.transcribe_wav(b"\x00\x00" * 1000)
        assert res.text == "Bonjour tout le monde"
        assert res.language == "en"  # Safe fallback
        assert res.language_name == "English"
        assert res.is_empty is False

    @pytest.mark.asyncio
    async def test_whisper_client_malformed_language_types_in_server_json(self):
        """Whisper returns JSON with malformed language (int, dict, whitespace, uppercase)."""
        test_cases = [
            ({"text": "Hola", "language": "  ES  "}, "es", "Spanish"),
            ({"text": "Guten Tag", "language": "DE"}, "de", "German"),
            ({"text": "Test", "language": ""}, "en", "English"),
            ({"text": "Test", "language": "   "}, "en", "English"),
        ]
        for payload, expected_code, expected_name in test_cases:
            mock_response = httpx.Response(
                status_code=200,
                json=payload,
                request=httpx.Request("POST", "http://localhost:8001/transcribe")
            )
            mock_http = AsyncMock(spec=httpx.AsyncClient)
            mock_http.is_closed = False
            mock_http.post.return_value = mock_response

            client = WhisperClient(client=mock_http)
            res = await client.transcribe_wav(b"\x00\x00" * 500)
            assert res.language == expected_code.strip().lower()
            assert res.language_name == expected_name

    @pytest.mark.asyncio
    async def test_whisper_client_missing_fields_and_none_text(self):
        """Whisper returns JSON missing 'text' or 'text'=None."""
        for payload in [{"language": "es"}, {"text": None, "language": "es"}, {}]:
            mock_response = httpx.Response(
                status_code=200,
                json=payload,
                request=httpx.Request("POST", "http://localhost:8001/transcribe")
            )
            mock_http = AsyncMock(spec=httpx.AsyncClient)
            mock_http.is_closed = False
            mock_http.post.return_value = mock_response

            client = WhisperClient(client=mock_http)
            res = await client.transcribe_wav(b"\x00\x00" * 500)
            assert res.text == ""
            assert res.is_empty is True

    @pytest.mark.asyncio
    async def test_qwen_client_null_empty_whitespace_source_language(self):
        """QwenClient post_correct_and_translate with None, empty, or whitespace language."""
        client = QwenClient(bypass_english=True)

        # None language -> defaults to 'en', bypasses if English
        res_none = await client.post_correct_and_translate("Hello world", source_language=None)
        assert res_none.bypassed is True
        assert res_none.corrected_text == "Hello world"
        assert res_none.english_translation == "Hello world"
        assert res_none.source_language == "en"

        # Empty language -> defaults to 'en', bypasses
        res_empty = await client.post_correct_and_translate("Hello world", source_language="")
        assert res_empty.bypassed is True

        # Whitespace language -> defaults to 'en', bypasses
        res_ws = await client.post_correct_and_translate("Hello world", source_language="   ")
        assert res_ws.bypassed is True

    @pytest.mark.asyncio
    async def test_qwen_client_null_and_empty_text(self):
        """QwenClient handles None or empty input text safely without HTTP requests."""
        client = QwenClient()
        for empty_val in ["", "   ", "\n\t  "]:
            res = await client.post_correct_and_translate(empty_val, source_language="es")
            assert res.corrected_text == ""
            assert res.english_translation == ""
            assert res.latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_qwen_client_uppercase_and_padded_source_language(self):
        """QwenClient correctly handles uppercase and whitespace-padded languages."""
        client = QwenClient(bypass_english=True)
        res_en_upper = await client.post_correct_and_translate("The quick brown fox", source_language="  EN  ")
        assert res_en_upper.bypassed is True

        res_english_word = await client.post_correct_and_translate("The quick brown fox", source_language="English")
        assert res_english_word.bypassed is True

    def test_parse_qwen_json_adversarial_corruptions(self):
        """Adversarial stress testing of parse_qwen_json parser stages."""
        fallback = "Original raw transcript text"

        # 1. Null / None values inside JSON
        corrupt_null = '{"corrected_text": null, "english_translation": null}'
        parsed = parse_qwen_json(corrupt_null, fallback_text=fallback)
        assert parsed["corrected_text"] == fallback
        assert parsed["english_translation"] == fallback

        # 2. Inverted / missing keys
        corrupt_missing = '{"output": "translated text"}'
        parsed = parse_qwen_json(corrupt_missing, fallback_text=fallback)
        assert parsed["corrected_text"] == fallback

        # 3. Truncated JSON
        corrupt_trunc = '{"corrected_text": "Hola mundo", "english_translation": "Hello wor'
        parsed = parse_qwen_json(corrupt_trunc, fallback_text=fallback)
        assert parsed["corrected_text"] == "Hola mundo"  # Extracted by regex fallback

        # 4. Nested markdown codeblock with commentary
        nested_md = "```json\n{\n  \"corrected_text\": \"Bonjour\",\n  \"english_translation\": \"Hello\"\n}\n```\nHope that helps!"
        parsed = parse_qwen_json(nested_md, fallback_text=fallback)
        assert parsed["corrected_text"] == "Bonjour"
        assert parsed["english_translation"] == "Hello"

        # 5. Non-dict JSON (array, primitive)
        assert parse_qwen_json("[1, 2, 3]", fallback_text=fallback)["corrected_text"] == fallback
        assert parse_qwen_json("12345", fallback_text=fallback)["corrected_text"] == fallback
        assert parse_qwen_json("null", fallback_text=fallback)["corrected_text"] == fallback
        assert parse_qwen_json("", fallback_text=fallback)["corrected_text"] == fallback

    def test_config_get_language_name_robustness(self):
        """get_language_name handles None, empty, unknown, numbers, and symbols."""
        assert get_language_name(None) == "Unknown"
        assert get_language_name("") == "Unknown"
        assert get_language_name("   ") == "Unknown"
        assert get_language_name("ES") == "Spanish"
        assert get_language_name("  fr  ") == "French"
        assert get_language_name("klingon") == "Klingon"
        assert get_language_name(123) == "123"


# ============================================================================
# 2. SYNTHETIC CORRUPT AUDIO CHUNKS & WAV PACKAGING
# ============================================================================

class TestCorruptAudioAndWavPackaging:
    """Adversarially tests audio buffer and packaging under corrupt/abnormal audio data."""

    @pytest.mark.asyncio
    async def test_buffer_odd_byte_length_chunks(self):
        """AudioRollingBuffer receiving non-word-aligned (odd byte) PCM chunks."""
        buf = AudioRollingBuffer()
        # Ingest 3 bytes, 4 bytes, 15 bytes -> total 22 bytes
        await buf.append_pcm(b"\x01\x02\x03")
        await buf.append_pcm(b"\x04\x05\x06\x07")
        await buf.append_pcm(b"\x08" * 15)

        metrics = await buf.get_buffer_metrics()
        assert metrics["buffered_bytes"] == 22
        assert metrics["total_received_bytes"] == 22

    @pytest.mark.asyncio
    async def test_buffer_extreme_oversized_chunk_pruning(self):
        """Buffer strictly enforces MAX_RETENTION_BYTES (12.0s = 384,000B) on giant chunk append."""
        buf = AudioRollingBuffer(max_retention_sec=12.0)
        giant_chunk = b"\x55\xaa" * 300000  # 600,000 bytes (~18.75s)
        await buf.append_pcm(giant_chunk)

        metrics = await buf.get_buffer_metrics()
        assert metrics["buffered_bytes"] == 384000
        assert metrics["total_received_bytes"] == 600000

        # Verify sliced window still operates perfectly
        assert await buf.has_window() is True
        slice_res = await buf.slice_next_window()
        assert slice_res is not None
        win_pcm, win_idx, start_sec = slice_res
        assert len(win_pcm) == 128000

    def test_pack_pcm_to_wav_adversarial_inputs(self):
        """pack_pcm_to_wav generates valid RIFF header for empty, odd, and giant byte strings."""
        test_inputs = [
            b"",                     # 0 bytes
            b"\x00",                 # 1 byte (odd)
            b"\xff\xfe\xfd",         # 3 bytes (odd)
            b"\x00\x01" * 8000,      # 16,000 bytes (0.5s)
            b"\x7f\x80" * 64000,     # 128,000 bytes (4.0s)
            os.urandom(1000000),     # 1MB random binary noise
        ]
        for pcm in test_inputs:
            wav_bytes = pack_pcm_to_wav(pcm, sample_rate=16000, channels=1, bits_per_sample=16)
            assert len(wav_bytes) == len(pcm) + 44
            assert wav_bytes[:4] == b"RIFF"
            assert wav_bytes[8:12] == b"WAVE"
            assert wav_bytes[12:16] == b"fmt "
            assert wav_bytes[36:40] == b"data"

            # Parse with standard Python wave module
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2
                assert wf.getframerate() == 16000
                frames = wf.readframes(len(pcm) // 2)
                # Verify payload match for even-sized chunks
                if len(pcm) % 2 == 0:
                    assert frames == pcm

    @pytest.mark.asyncio
    async def test_audio_pipeline_with_garbage_and_dc_offset_audio(self):
        """AudioPipeline ingests DC offset (all 0xFF) and silence without crashing."""
        mock_whisper = AsyncMock(spec=WhisperClient)
        mock_whisper.transcribe_wav.return_value = TranscriptionResult(
            text="", language="en", latency_ms=15.0, is_empty=True
        )
        mock_qwen = AsyncMock(spec=QwenClient)
        mock_qwen.post_correct_and_translate.return_value = TranslationResult(
            corrected_text="", english_translation="", source_language="en", latency_ms=0.0, bypassed=True
        )

        pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)

        # Feed 128,000 bytes of 0xFF (clipped DC offset)
        clipped_pcm = b"\xff\xff" * 64000
        res = await pipeline.process_chunk(clipped_pcm)
        assert res is not None
        assert res.raw_text == ""
        assert res.stitched_text == ""
        assert res.is_english is True


# ============================================================================
# 3. NETWORK LATENCY SPIKES & TRANSIENT ERROR RECOVERY
# ============================================================================

class TestNetworkResilienceAndLatencySpikes:
    """Tests client retry logic, timeouts, and error resilience under network chaos."""

    @pytest.mark.asyncio
    async def test_whisper_client_transient_failure_then_success(self):
        """WhisperClient fails on attempt 1 with 503, succeeds on attempt 2."""
        mock_err = httpx.Response(
            status_code=503,
            text="Service Temporarily Unavailable",
            request=httpx.Request("POST", "http://localhost:8001/transcribe")
        )
        mock_ok = httpx.Response(
            status_code=200,
            json={"text": "Recovered successfully", "language": "en"},
            request=httpx.Request("POST", "http://localhost:8001/transcribe")
        )

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.side_effect = [mock_err, mock_ok]

        client = WhisperClient(client=mock_http, max_retries=2)
        res = await client.transcribe_wav(b"\x00\x00" * 1000)
        assert res.text == "Recovered successfully"
        assert res.error is None
        assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_whisper_client_persistent_timeout_fallback(self):
        """WhisperClient persistently times out -> returns graceful fallback result with error."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.side_effect = httpx.ReadTimeout("Read timed out after 4.0s")

        telemetry = TelemetryCollector()
        client = WhisperClient(client=mock_http, max_retries=1, telemetry_collector=telemetry)
        res = await client.transcribe_wav(b"\x00\x00" * 1000)

        assert res.is_empty is True
        assert res.text == ""
        assert "Timeout" in res.error
        assert mock_http.post.call_count == 2
        assert len(telemetry.api_logs) == 1
        assert telemetry.api_logs[0].status_code == 408

    @pytest.mark.asyncio
    async def test_qwen_client_transient_500_then_success(self):
        """QwenClient handles transient 500 error and recovers on retry."""
        mock_err = httpx.Response(
            status_code=500,
            text="vLLM Internal Server Error",
            request=httpx.Request("POST", "http://localhost:8000/v1/chat/completions")
        )
        mock_ok = httpx.Response(
            status_code=200,
            json={
                "choices": [{
                    "message": {
                        "content": '{"corrected_text": "El museo es grande", "english_translation": "The museum is large"}'
                    }
                }]
            },
            request=httpx.Request("POST", "http://localhost:8000/v1/chat/completions")
        )

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.side_effect = [mock_err, mock_ok]

        client = QwenClient(client=mock_http, max_retries=1, bypass_english=False)
        res = await client.post_correct_and_translate("El museo es grande", source_language="es")
        assert res.corrected_text == "El museo es grande"
        assert res.english_translation == "The museum is large"
        assert res.error is None
        assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_qwen_client_persistent_failure_fallback_preserves_text(self):
        """QwenClient persistent failure returns input text as fallback translation without crashing."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.side_effect = httpx.ConnectError("Connection refused on port 8000")

        client = QwenClient(client=mock_http, max_retries=1, bypass_english=False)
        res = await client.post_correct_and_translate("Bonjour le monde", source_language="fr")
        assert res.corrected_text == "Bonjour le monde"
        assert res.english_translation == "Bonjour le monde"  # Preserved fallback!
        assert res.error is not None

    @pytest.mark.asyncio
    async def test_audio_pipeline_survives_backend_failure_storm(self):
        """AudioPipeline processes multiple chunks even if Whisper and Qwen intermittently fail."""
        mock_whisper = AsyncMock(spec=WhisperClient)
        # Sequence: Success -> Fail -> Success
        mock_whisper.transcribe_wav.side_effect = [
            TranscriptionResult(text="First window text", language="es", latency_ms=100.0),
            TranscriptionResult(text="", language="en", latency_ms=4000.0, is_empty=True, error="Timeout"),
            TranscriptionResult(text="Third window text", language="es", latency_ms=120.0),
        ]

        mock_qwen = AsyncMock(spec=QwenClient)
        mock_qwen.post_correct_and_translate.side_effect = [
            TranslationResult(corrected_text="First window text", english_translation="First window", source_language="es", latency_ms=200.0),
            TranslationResult(corrected_text="First window text", english_translation="First window", source_language="en", latency_ms=0.0, bypassed=True),
            TranslationResult(corrected_text="Third window text", english_translation="Third window", source_language="es", latency_ms=210.0),
        ]

        pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)

        # Chunk 1 (4.0s)
        r1 = await pipeline.process_chunk(b"\x00\x00" * 64000)
        assert r1 is not None
        assert "First" in r1.raw_text

        # Chunk 2 (2.0s stride) - Whisper times out
        r2 = await pipeline.process_chunk(b"\x00\x00" * 32000)
        assert r2 is not None
        assert r2.raw_text == ""  # Gracefully handled empty/failed chunk

        # Chunk 3 (2.0s stride) - Whisper recovers
        r3 = await pipeline.process_chunk(b"\x00\x00" * 32000)
        assert r3 is not None
        assert "Third" in r3.raw_text


# ============================================================================
# 4. SESSION FLUSH & LIFECYCLE BOUNDARY MATRIX
# ============================================================================

class TestSessionFlushAndLifecycle:
    """Tests AudioPipeline and AudioRollingBuffer session termination, flush, and reset."""

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self):
        """Flushing an empty buffer returns None or empty tail pass."""
        pipeline = AudioPipeline()
        res = await pipeline.flush()
        assert res is None

    @pytest.mark.asyncio
    async def test_flush_below_min_flush_threshold(self):
        """Buffer with < 0.5s audio (15,998 bytes) discards residual audio on flush."""
        pipeline = AudioPipeline()
        # Feed 0.4s of audio (12,800 bytes)
        await pipeline.buffer.append_pcm(b"\x00\x00" * 6400)
        res = await pipeline.flush()
        assert res is None
        metrics = await pipeline.buffer.get_buffer_metrics()
        assert metrics["buffered_bytes"] == 0

    @pytest.mark.asyncio
    async def test_flush_above_min_flush_threshold_zero_pads(self):
        """Buffer with 1.0s audio (32,000 bytes) zero-pads to 128,000 bytes on flush."""
        mock_whisper = AsyncMock(spec=WhisperClient)
        mock_whisper.transcribe_wav.return_value = TranscriptionResult(
            text="Final goodbye", language="es", latency_ms=80.0
        )
        mock_qwen = AsyncMock(spec=QwenClient)
        mock_qwen.post_correct_and_translate.return_value = TranslationResult(
            corrected_text="Final goodbye", english_translation="Final goodbye", source_language="es", latency_ms=100.0
        )

        pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
        # Feed 1.0s audio (32,000 bytes)
        await pipeline.buffer.append_pcm(b"\x12\x34" * 16000)
        res = await pipeline.flush()

        assert res is not None
        assert res.is_final is True
        assert res.raw_text == "Final goodbye"

        # Verify WAV passed to whisper was full 4.0s (128,000 bytes + 44 header)
        call_args = mock_whisper.transcribe_wav.call_args[0]
        assert len(call_args[0]) == 128044

    @pytest.mark.asyncio
    async def test_consecutive_duplicate_flush_idempotency(self):
        """Calling flush twice consecutively does not crash and second call returns None."""
        mock_whisper = AsyncMock(spec=WhisperClient)
        mock_whisper.transcribe_wav.return_value = TranscriptionResult(
            text="One last thing", language="en", latency_ms=50.0
        )
        mock_qwen = AsyncMock(spec=QwenClient)
        mock_qwen.post_correct_and_translate.return_value = TranslationResult(
            corrected_text="One last thing", english_translation="One last thing", source_language="en", latency_ms=0.0, bypassed=True
        )

        pipeline = AudioPipeline(whisper_client=mock_whisper, qwen_client=mock_qwen)
        await pipeline.buffer.append_pcm(b"\x12\x34" * 20000)

        f1 = await pipeline.flush()
        assert f1 is not None
        assert f1.is_final is True

        f2 = await pipeline.flush()
        assert f2 is None  # Second flush should be None

    @pytest.mark.asyncio
    async def test_pipeline_reset_and_reuse_lifecycle(self):
        """Pipeline can be reset mid-stream or between sessions and cleanly re-accumulate."""
        pipeline = AudioPipeline()
        await pipeline.buffer.append_pcm(b"\x11\x22" * 40000)
        pipeline.reset()

        m = await pipeline.buffer.get_buffer_metrics()
        assert m["buffered_bytes"] == 0
        assert m["total_received_bytes"] == 0
        assert pipeline.stitcher.committed_text == ""
        assert pipeline.stitcher.tentative_tail == ""
        assert pipeline._chunk_counter == 0


# ============================================================================
# 5. LIVE GPU END-TO-END STREAMING BENCHMARK
# ============================================================================

class TestLiveServicesE2E:
    """Tests live integration with local Faster-Whisper (8001) and vLLM Qwen 72B (8000)."""

    @pytest.mark.asyncio
    async def test_live_whisper_and_qwen_spanish_e2e_stream(self):
        """Synthesizes Spanish speech waveform, streams through live pipeline, verifies outputs."""
        async with httpx.AsyncClient() as client:
            try:
                whisper_check = await client.get("http://localhost:8001/transcribe", timeout=1.0)
            except Exception:
                pass
            try:
                vllm_check = await client.get("http://localhost:8000/v1/models", timeout=1.0)
                vllm_ok = vllm_check.status_code == 200
            except Exception:
                vllm_ok = False

        if not vllm_ok:
            pytest.skip("Live vLLM (8000) not accessible; skipping live test.")

        whisper_client = WhisperClient(base_url="http://localhost:8001")
        qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
        pipeline = AudioPipeline(whisper_client=whisper_client, qwen_client=qwen_client)

        try:
            # Generate 6.0s synthetic audio tone stream (192,000 bytes)
            t = np.linspace(0, 6.0, int(16000 * 6.0), endpoint=False)
            sine_wave = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
            pcm_bytes = sine_wave.tobytes()

            results = []
            chunk_size = 16000  # 0.5s chunks
            for offset in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[offset:offset + chunk_size]
                res = await pipeline.process_chunk(chunk)
                if res:
                    results.append(res)

            flush_res = await pipeline.flush()
            if flush_res:
                results.append(flush_res)

            assert len(results) >= 1
            for r in results:
                assert r.whisper_latency_ms < 5000.0
                assert r.e2e_latency_ms < 10000.0
                assert isinstance(r.language, str)
        finally:
            await whisper_client.close()
            await qwen_client.close()
