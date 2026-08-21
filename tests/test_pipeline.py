"""
Comprehensive Unit & Integration Test Suite for Translation Kiosk Core Audio Pipeline.
Covers:
- RIFF WAV packaging (44-byte canonical header, wave module validation)
- Audio rolling buffer math, chunk accumulation, window slicing, stride, flush zero-padding, max retention enforcement
- TextStitcher fuzzy alignment, overlap deduplication, prefix word preservation, boundary word repair, zero-match commit, hallucination filtering
- WhisperClient HTTP parsing, connection pooling, retries, null language safety, and timeout fallbacks
- QwenClient single-call post-correction, 5-stage JSON parser, null language safety, and English bypass (0ms overhead)
- Telemetry percentiles, latency tracking, API call audit logs
- ComparativeEngine diff tokenization (naive non-overlapping vs sliding-window)
- End-to-end AudioPipeline coordinator integration flow
"""
import pytest
import struct
import wave
import io
import json
import time
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

# Import pipeline components
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
from audio_pipeline import (
    pack_pcm_to_wav,
    create_wav_bytes,
    AudioRollingBuffer,
    AudioBuffer,
    TextStitcher,
    TextMerger,
    ComparativeEngine,
    AudioPipeline,
    PipelineResult
)
from whisper_client import (
    WhisperClient,
    TranscriptionResult,
    WhisperResponse
)
from qwen_client import (
    QwenClient,
    TranslationResult,
    QwenResponse,
    parse_qwen_json
)
from telemetry import (
    TelemetryCollector,
    ChunkTelemetry,
    APICallLog
)


# ============================================================================
# 1. RIFF WAV Header & Binary Tests
# ============================================================================

def test_wav_header_44_bytes():
    """Verify RIFF WAV packaging generates exact canonical 44-byte header."""
    pcm_data = b"\x00\x00" * 16000  # 1.0s of 16kHz mono 16-bit audio = 32,000 bytes
    wav_data = pack_pcm_to_wav(pcm_data, sample_rate=16000, channels=1, bits_per_sample=16)

    assert len(wav_data) == 44 + len(pcm_data)

    # Unpack canonical 44-byte header
    riff, chunk_size, wave_id, fmt, subchunk1_size, audio_fmt, channels, rate, byte_rate, align, bps, data_id, data_size = struct.unpack(
        '<4sI4s4sIHHIIHH4sI', wav_data[:44]
    )

    assert riff == b"RIFF"
    assert wave_id == b"WAVE"
    assert fmt == b"fmt "
    assert subchunk1_size == 16
    assert audio_fmt == 1          # PCM format
    assert channels == 1           # Mono
    assert rate == 16000           # 16 kHz
    assert byte_rate == 32000      # 16000 * 1 * 2
    assert align == 2              # 1 * 2
    assert bps == 16               # 16-bit
    assert data_id == b"data"
    assert data_size == len(pcm_data)
    assert chunk_size == 36 + len(pcm_data)


def test_wav_readable_by_standard_wave_module():
    """Verify in-memory WAV payload is 100% valid for standard python wave reader."""
    # 0.5s synthetic audio pattern
    pcm_data = b"\x12\x34" * 8000
    wav_bytes = create_wav_bytes(pcm_data, sample_rate=16000, channels=1, bits_per_sample=16)

    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 8000
        read_pcm = wf.readframes(8000)
        assert read_pcm == pcm_data


# ============================================================================
# 2. Audio Rolling Buffer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_audio_buffer_slicing_math():
    """Verify rolling buffer maintains window and stride parameters accurately."""
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, sample_rate=16000)

    # 1.0s audio chunk = 32,000 bytes
    chunk_1s = b"\x01\x00" * 16000

    # Stream 3.0s: buffer should NOT have a full 4.0s window yet
    for _ in range(3):
        await buf.append_pcm(chunk_1s)
    assert not await buf.has_window()

    # Stream 4th second: now ready for first 4.0s window
    await buf.append_pcm(chunk_1s)
    assert await buf.has_window()

    slice_1 = await buf.slice_next_window()
    assert slice_1 is not None
    window_pcm, idx, start_sec = slice_1
    assert len(window_pcm) == 128000
    assert idx == 0
    assert start_sec == 0.0

    # After slicing, stride (64,000B = 2.0s) was consumed, leaving 2.0s in buffer
    assert not await buf.has_window()

    # Append 2 more seconds: now ready for window 2 (starting at t = 2.0s)
    await buf.append_pcm(chunk_1s)
    await buf.append_pcm(chunk_1s)
    assert await buf.has_window()

    slice_2 = await buf.slice_next_window()
    assert slice_2 is not None
    window_pcm_2, idx_2, start_sec_2 = slice_2
    assert len(window_pcm_2) == 128000
    assert idx_2 == 1
    assert start_sec_2 == 2.0


@pytest.mark.asyncio
async def test_audio_buffer_arbitrary_chunk_sizes():
    """Verify buffer ingests arbitrary streaming chunk sizes (50ms, 100ms, 250ms)."""
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, sample_rate=16000)

    # 50ms chunk = 1600 bytes
    chunk_50ms = b"\x02\x00" * 800
    for _ in range(80):  # 80 * 50ms = 4000ms = 4.0s
        await buf.append_pcm(chunk_50ms)

    assert await buf.has_window()
    slice_res = await buf.slice_next_window()
    assert slice_res is not None
    assert len(slice_res[0]) == 128000


@pytest.mark.asyncio
async def test_audio_buffer_flush_zero_padding():
    """Verify buffer zero-pads residual audio on flush when >= min_flush_sec."""
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, min_flush_sec=0.5, sample_rate=16000)

    # Push 1.5s audio (48,000 bytes) -> greater than min_flush (16,000B) but less than window (128,000B)
    chunk_1_5s = b"\x05\x00" * 24000
    await buf.append_pcm(chunk_1_5s)

    assert not await buf.has_window()
    flush_res = await buf.flush()
    assert flush_res is not None
    padded_pcm, idx, start_sec = flush_res

    # Output should be padded to full 128,000 bytes
    assert len(padded_pcm) == 128000
    assert padded_pcm[:48000] == chunk_1_5s
    assert padded_pcm[48000:] == b"\x00" * 80000


@pytest.mark.asyncio
async def test_audio_buffer_flush_discard_below_min():
    """Verify buffer discards audio below min_flush_sec on flush."""
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, min_flush_sec=0.5, sample_rate=16000)

    # Push 0.2s audio (6,400 bytes) -> less than min_flush (16,000B)
    chunk_0_2s = b"\x01\x00" * 3200
    await buf.append_pcm(chunk_0_2s)

    flush_res = await buf.flush()
    assert flush_res is None


@pytest.mark.asyncio
async def test_audio_buffer_metrics():
    """Verify buffer health diagnostic metrics."""
    buf = AudioRollingBuffer(sample_rate=16000)
    chunk_1s = b"\x00\x00" * 16000
    await buf.append_pcm(chunk_1s)

    metrics = await buf.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 32000
    assert metrics["buffered_seconds"] == 1.0
    assert metrics["total_received_bytes"] == 32000
    assert metrics["window_index"] == 0


@pytest.mark.asyncio
async def test_audio_buffer_max_retention_enforcement():
    """Regression test: Verify AudioRollingBuffer trims buffer when exceeding max_retention_bytes."""
    buf = AudioRollingBuffer(sample_rate=16000, max_retention_sec=12.0)
    assert buf.max_retention_bytes == 384000

    # Stream 16.0s of PCM (512,000 bytes)
    chunk_16s = b"\x03\x00" * (16000 * 16)
    await buf.append_pcm(chunk_16s)

    metrics = await buf.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 384000
    assert metrics["total_received_bytes"] == 512000
    assert len(buf._buffer) == 384000

    # Also test synchronous add_pcm
    buf.reset()
    buf.add_pcm(chunk_16s)
    assert len(buf._buffer) == 384000


# ============================================================================
# 3. Text Alignment & Stitching Engine Tests
# ============================================================================

def test_text_alignment_clean_overlap():
    """Verify SequenceMatcher merges overlapping transcriptions without duplicating words."""
    stitcher = TextStitcher(overlap_ratio=0.5)

    # Window 1 transcription
    w1_text = "Welcome to the national museum of science and"
    c1, t1, d1, r1 = stitcher.process_window(w1_text)

    assert d1 == w1_text
    assert c1 == "Welcome to the national"
    assert t1 == "museum of science and"

    # Window 2 overlapping transcription
    w2_text = "museum of science and industry where we explore tomorrow"
    c2, t2, d2, r2 = stitcher.process_window(w2_text)

    # Verify no duplication of overlap phrase
    assert "museum of science and industry" in d2
    assert d2.count("science and") == 1
    assert d2 == "Welcome to the national museum of science and industry where we explore tomorrow"


def test_text_alignment_boundary_truncation_repair():
    """Verify alignment fixes truncated boundary words from previous window."""
    stitcher = TextStitcher(overlap_ratio=0.5)

    # Window 1 cut off mid-word on "egypt"
    w1_text = "Here we have ancient egypt"
    c1, t1, d1, r1 = stitcher.process_window(w1_text)

    # Window 2 provides lookahead fixing to "ancient egyptian artifacts from the tomb"
    w2_text = "ancient egyptian artifacts from the tomb"
    c2, t2, d2, r2 = stitcher.process_window(w2_text)

    assert "egyptian artifacts" in d2
    assert "ancient egypt ancient" not in d2
    assert "have" in d2
    assert d2 == "Here we have ancient egyptian artifacts from the tomb"
    assert r2 >= 1  # Boundary repair detected


def test_text_stitcher_offset_match_preserves_prefix_words():
    """Regression test: Verify SequenceMatcher does not drop unmatched prefix words when match.a > 0."""
    stitcher = TextStitcher(overlap_ratio=0.5)

    # Window 1: "Here we have ancient egypt"
    c1, t1, d1, r1 = stitcher.process_window("Here we have ancient egypt")
    assert c1 == "Here we"
    assert t1 == "have ancient egypt"

    # Window 2: "ancient egyptian artifacts from the tomb" -> matches "ancient" at index 1 of tail
    c2, t2, d2, r2 = stitcher.process_window("ancient egyptian artifacts from the tomb")
    # "have" must be committed before "ancient egyptian"
    assert "have" in c2
    assert "have" in d2
    assert d2 == "Here we have ancient egyptian artifacts from the tomb"
    assert c2 == "Here we have ancient egyptian"
    assert t2 == "artifacts from the tomb"


def test_text_stitcher_zero_match_commits_previous_tail():
    """Regression test: Verify zero-overlap transition (match.size == 0) commits all previous tentative tail."""
    stitcher = TextStitcher(overlap_ratio=0.5)

    # Window 1: "The quick brown fox jumps"
    c1, t1, d1, r1 = stitcher.process_window("The quick brown fox jumps")
    assert c1 == "The quick"
    assert t1 == "brown fox jumps"

    # Window 2: Disjoint utterance "over a lazy dog" (zero word overlap)
    c2, t2, d2, r2 = stitcher.process_window("over a lazy dog")
    # Entire previous tail "brown fox jumps" must be committed into c2 and appear in d2
    assert "brown fox jumps" in c2
    assert "brown fox jumps" in d2
    assert d2 == "The quick brown fox jumps over a lazy dog"
    assert c2 == "The quick brown fox jumps over a"
    assert t2 == "lazy dog"


def test_text_alignment_hallucination_filtering():
    """Verify silence hallucinations are filtered out."""
    stitcher = TextStitcher()

    assert stitcher.clean_hallucinations("[Music]") == ""
    assert stitcher.clean_hallucinations("Thank you for watching.") == ""
    assert stitcher.clean_hallucinations("Subtitles by...") == ""
    assert stitcher.clean_hallucinations("Hello world") == "Hello world"


def test_text_alignment_flush_final():
    """Verify flush_final commits remaining tentative tail."""
    stitcher = TextStitcher(overlap_ratio=0.5)
    stitcher.process_window("This is tentative audio")
    assert stitcher.tentative_tail != ""

    final_text = stitcher.flush_final()
    assert final_text == "This is tentative audio"
    assert stitcher.tentative_tail == ""


# ============================================================================
# 4. Whisper Client HTTP Tests
# ============================================================================

@pytest.mark.asyncio
async def test_whisper_client_success():
    """Verify WhisperClient correctly parses 200 OK responses."""
    mock_resp = httpx.Response(200, json={"text": "Hola mundo", "language": "es"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        client = WhisperClient(base_url="http://localhost:8001")
        res = await client.transcribe_wav(b"RIFF_FAKE_AUDIO")

        assert res.text == "Hola mundo"
        assert res.language == "es"
        assert res.language_name == "Spanish"
        assert not res.is_empty
        assert res.error is None


@pytest.mark.asyncio
async def test_whisper_client_retry_and_timeout():
    """Verify WhisperClient retries on failure and gracefully returns fallback result."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        client = WhisperClient(base_url="http://localhost:8001", max_retries=1)
        res = await client.transcribe_wav(b"RIFF_FAKE_AUDIO")

        assert res.text == ""
        assert res.is_empty is True
        assert res.error is not None


# ============================================================================
# 5. Qwen Client & JSON Parser Tests
# ============================================================================

def test_qwen_json_parser_clean():
    """Verify JSON parser handles clean JSON object."""
    raw = '{"corrected_text": "Bonjour le monde", "english_translation": "Hello world"}'
    parsed = parse_qwen_json(raw, fallback_text="Bonjour")
    assert parsed["corrected_text"] == "Bonjour le monde"
    assert parsed["english_translation"] == "Hello world"


def test_qwen_json_parser_markdown_wrapped():
    """Verify JSON parser handles markdown code blocks."""
    raw = "```json\n{\n  \"corrected_text\": \"Hola\",\n  \"english_translation\": \"Hello\"\n}\n```"
    parsed = parse_qwen_json(raw, fallback_text="Hola")
    assert parsed["corrected_text"] == "Hola"
    assert parsed["english_translation"] == "Hello"


def test_qwen_json_parser_embedded():
    """Verify JSON parser extracts outermost JSON from conversational preambles."""
    raw = "Here is your translation:\n{\"corrected_text\": \"Guten Tag\", \"english_translation\": \"Good day\"}\nHope this helps!"
    parsed = parse_qwen_json(raw, fallback_text="Guten Tag")
    assert parsed["corrected_text"] == "Guten Tag"
    assert parsed["english_translation"] == "Good day"


def test_qwen_json_parser_malformed_fallback():
    """Verify JSON parser falls back cleanly without raising exception."""
    raw = "I could not translate: unparseable syntax {"
    parsed = parse_qwen_json(raw, fallback_text="Original text")
    assert parsed["corrected_text"] == "Original text"
    assert parsed["english_translation"] == raw


@pytest.mark.asyncio
async def test_qwen_client_english_bypass():
    """Verify Requirement R4: English input bypasses LLM call entirely (0ms latency)."""
    client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)

    # No HTTP mock configured because HTTP call should never happen
    res = await client.post_correct_and_translate("Welcome to the kiosk", source_language="en")

    assert res.bypassed is True
    assert res.latency_ms == 0.0
    assert res.corrected_text == "Welcome to the kiosk"
    assert res.english_translation == "Welcome to the kiosk"


@pytest.mark.asyncio
async def test_qwen_client_translation_success():
    """Verify Qwen client calls LLM and parses JSON for non-English languages."""
    mock_resp = httpx.Response(200, json={
        "choices": [{
            "message": {
                "content": '{"corrected_text": "Bonjour et bienvenue.", "english_translation": "Hello and welcome."}'
            }
        }]
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
        res = await client.post_correct_and_translate("bonjour et bienvenue", source_language="fr")

        assert res.bypassed is False
        assert res.corrected_text == "Bonjour et bienvenue."
        assert res.english_translation == "Hello and welcome."
        assert res.source_language == "fr"


@pytest.mark.asyncio
async def test_whisper_and_qwen_clients_null_language_safety():
    """Regression test: Verify WhisperClient and QwenClient safely handle null/None language values without AttributeError."""
    # 1. Whisper response with null language: {"text": "Hello world", "language": None}
    mock_resp = httpx.Response(200, json={"text": "Hello world", "language": None, "language_prob": None})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        whisper = WhisperClient(base_url="http://localhost:8001")
        res = await whisper.transcribe_wav(b"RIFF_FAKE_AUDIO")

        assert res.text == "Hello world"
        assert res.language == "en"
        assert res.language_name == "English"
        assert res.error is None

    # 2. Qwen client called with source_language=None
    qwen = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
    qwen_res = await qwen.post_correct_and_translate("Hello museum", source_language=None)
    assert qwen_res.bypassed is True
    assert qwen_res.latency_ms == 0.0
    assert qwen_res.source_language == "en"
    assert qwen_res.english_translation == "Hello museum"


# ============================================================================
# 6. Telemetry & Comparative Engine Tests
# ============================================================================

def test_telemetry_recording_and_percentiles():
    """Verify TelemetryCollector aggregates percentiles, counters, and admin payloads."""
    collector = TelemetryCollector(history_size=50)

    # Record 5 mock chunks with latencies: 200, 400, 600, 800, 1000 ms
    for i in range(1, 6):
        collector.record_chunk(ChunkTelemetry(
            chunk_id=i,
            timestamp=time.time(),
            audio_duration_s=2.0,
            buffer_depth_bytes=64000,
            whisper_latency_ms=200.0 * i,
            qwen_latency_ms=500.0,
            alignment_latency_ms=2.0,
            e2e_latency_ms=200.0 * i + 502.0,
            source_language="es",
            is_english_bypassed=False,
            naive_text=f"naive_{i}",
            sliding_window_text=f"sliding_{i}",
            repairs_count=1
        ))

    stats = collector.get_summary_stats()
    assert stats["total_chunks_processed"] == 5
    assert stats["total_audio_seconds"] == 10.0
    assert stats["boundary_corrections_count"] == 5
    assert stats["whisper_latency"]["p50"] == 600.0
    assert stats["whisper_latency"]["min"] == 200.0
    assert stats["whisper_latency"]["max"] == 1000.0

    payload = collector.get_admin_telemetry_payload()
    assert payload["type"] == "admin_telemetry"
    assert payload["latest_chunk"]["chunk_id"] == 5


def test_comparative_engine_diff_tokens():
    """Verify ComparativeEngine produces structured word-level diff tokens."""
    engine = ComparativeEngine()

    step_res = engine.process_step(
        naive_chunk_text="Welcome to museum",
        sliding_stitched_text="Welcome to the national museum",
        whisper_sliding_latency_ms=300.0
    )

    assert step_res["step_repairs"] >= 0
    assert len(step_res["diff_tokens"]) > 0
    assert "Welcome" in step_res["sliding_full_text"]


# ============================================================================
# 7. Integrated AudioPipeline Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_pipeline_mock_flow():
    """Integration test running synthetic audio through buffer -> whisper -> qwen -> alignment -> telemetry."""
    whisper_mock = AsyncMock()
    whisper_mock.transcribe_wav.return_value = TranscriptionResult(
        text="Bonjour et bienvenue",
        language="fr",
        language_name="French",
        latency_ms=250.0
    )

    qwen_mock = AsyncMock()
    qwen_mock.post_correct_and_translate.return_value = TranslationResult(
        corrected_text="Bonjour et bienvenue.",
        english_translation="Hello and welcome.",
        source_language="fr",
        latency_ms=450.0,
        bypassed=False
    )

    telemetry = TelemetryCollector()
    pipeline = AudioPipeline(
        whisper_client=whisper_mock,
        qwen_client=qwen_mock,
        telemetry_collector=telemetry,
        window_sec=4.0,
        stride_sec=2.0
    )

    # Feed 4.0s of silence PCM
    pcm_chunk = b"\x00\x00" * (16000 * 4)
    result = await pipeline.process_chunk(pcm_chunk)

    assert result is not None
    assert result.language == "fr"
    assert result.language_name == "French"
    assert result.corrected_text == "Bonjour et bienvenue."
    assert result.translated_text == "Hello and welcome."
    assert result.whisper_latency_ms == 250.0
    assert result.qwen_latency_ms == 450.0
    assert result.is_english is False

    stats = telemetry.get_summary_stats()
    assert stats["total_chunks_processed"] == 1


@pytest.mark.asyncio
async def test_full_pipeline_english_bypass_flow():
    """Integration test verifying English language bypass in end-to-end pipeline."""
    whisper_mock = AsyncMock()
    whisper_mock.transcribe_wav.return_value = TranscriptionResult(
        text="Hello and welcome to the exhibit",
        language="en",
        language_name="English",
        latency_ms=200.0
    )

    # Real QwenClient with bypass enabled
    qwen_client = QwenClient(bypass_english=True)

    pipeline = AudioPipeline(
        whisper_client=whisper_mock,
        qwen_client=qwen_client,
        window_sec=4.0,
        stride_sec=2.0
    )

    pcm_chunk = b"\x00\x00" * (16000 * 4)
    result = await pipeline.process_chunk(pcm_chunk)

    assert result is not None
    assert result.is_english is True
    assert result.qwen_latency_ms == 0.0
    assert result.translated_text == "Hello and welcome to the exhibit"
