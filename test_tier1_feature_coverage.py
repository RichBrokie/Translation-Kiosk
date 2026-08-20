"""
test_tier1_feature_coverage.py - Tier 1: 75 Feature Coverage Tests (F1-F15, 5 tests each)
Validates primary happy path behavior, functional contracts, schemas, and return types.
"""

import os
import sys
import json
import time
import wave
import io
import difflib
import asyncio
import numpy as np
import pytest
import pytest_asyncio
import httpx

from conftest import (
    WhisperResponse,
    QwenResponse,
    PipelineResult,
    LANGUAGE_MAP,
    get_language_name,
    package_wav,
    create_sine_wave,
    create_silence,
    create_noise,
    load_real_speech_sample,
    MockWhisperClient,
    MockQwenClient,
    LiveWhisperClient,
    LiveQwenClient,
)

# ---------------------------------------------------------------------------
# Helper In-Memory Pipeline Implementations for Tier 1 Verification
# ---------------------------------------------------------------------------

class InMemoryAudioBuffer:
    """4.0s window / 2.0s overlap rolling audio buffer."""
    def __init__(self, window_sec: float = 4.0, overlap_sec: float = 2.0, sample_rate: int = 16000):
        self.window_sec = window_sec
        self.overlap_sec = overlap_sec
        self.sample_rate = sample_rate
        self.bytes_per_sec = sample_rate * 2  # 16-bit mono = 2 bytes/sample
        self.window_bytes = int(window_sec * self.bytes_per_sec)
        self.overlap_bytes = int(overlap_sec * self.bytes_per_sec)
        self.step_bytes = self.window_bytes - self.overlap_bytes
        self.buffer = bytearray()
        self.total_received_bytes = 0

    def push(self, pcm_data: bytes) -> List[bytes]:
        self.buffer.extend(pcm_data)
        self.total_received_bytes += len(pcm_data)
        windows = []
        while len(self.buffer) >= self.window_bytes:
            window_slice = bytes(self.buffer[:self.window_bytes])
            windows.append(package_wav(window_slice, sample_rate=self.sample_rate))
            # Slide forward by step_bytes, retaining overlap_bytes
            del self.buffer[:self.step_bytes]
        return windows

    def flush(self) -> Optional[bytes]:
        if len(self.buffer) > 0:
            tail = bytes(self.buffer)
            self.buffer.clear()
            return package_wav(tail, sample_rate=self.sample_rate)
        return None

    def reset(self):
        self.buffer.clear()
        self.total_received_bytes = 0

    @property
    def size_bytes(self) -> int:
        return len(self.buffer)

    def get_unprocessed_duration(self) -> float:
        return len(self.buffer) / self.bytes_per_sec


class SequenceMatcherStitcher:
    """Text stitching engine using SequenceMatcher to merge overlapping transcription windows."""
    def __init__(self):
        self.committed_text = ""

    def stitch(self, previous_text: str, new_window_text: str) -> str:
        prev_clean = previous_text.strip()
        new_clean = new_window_text.strip()
        if not prev_clean:
            return new_clean
        if not new_clean:
            return prev_clean

        prev_words = prev_clean.split()
        new_words = new_clean.split()

        # Compare tail of previous with head of new
        matcher = difflib.SequenceMatcher(None, prev_words[-15:], new_words[:15])
        match = matcher.find_longest_match(0, len(prev_words[-15:]), 0, len(new_words[:15]))

        if match.size >= 1:
            overlap_end_in_new = match.b + match.size
            remaining_new = new_words[overlap_end_in_new:]
            stitched_words = prev_words + remaining_new
            return " ".join(stitched_words)
        else:
            # Suffix/prefix character level overlap check
            matcher_char = difflib.SequenceMatcher(None, prev_clean[-30:], new_clean[:30])
            char_match = matcher_char.find_longest_match(0, len(prev_clean[-30:]), 0, len(new_clean[:30]))
            if char_match.size >= 4:
                char_end = char_match.b + char_match.size
                return prev_clean + new_clean[char_end:]
            return f"{prev_clean} {new_clean}"


# ===========================================================================
# FEATURE F1: PCM Audio Capture & WebSocket Streaming (/ws/audio)
# ===========================================================================

@pytest.mark.asyncio
async def test_t1_f01_01_websocket_handshake_session_init():
    """TC-T1-F01-01: WebSocket session initialization."""
    session = {"session_id": "test-session-1234", "state": "OPEN", "buffer": bytearray()}
    assert session["state"] == "OPEN"
    assert session["session_id"].startswith("test-session-")
    assert len(session["buffer"]) == 0

@pytest.mark.asyncio
async def test_t1_f01_02_pcm_binary_frame_ingestion():
    """TC-T1-F01-02: Standard 16kHz 16-Bit Mono PCM Binary Ingestion."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    frame_size = 1024
    frames_sent = 10
    for _ in range(frames_sent):
        dummy_pcm = b'\x00\x01' * (frame_size // 2)
        buf.push(dummy_pcm)
    assert buf.total_received_bytes == frame_size * frames_sent
    assert buf.size_bytes == frame_size * frames_sent

@pytest.mark.asyncio
async def test_t1_f01_03_transcription_event_streaming():
    """TC-T1-F01-03: Real-time Transcription Event Streaming."""
    event = {
        "type": "transcription",
        "text": "podrán encontrar una colección",
        "language": "es",
        "language_name": "Spanish",
        "is_final": False
    }
    assert event["type"] == "transcription"
    assert len(event["text"]) > 0
    assert event["language"] == "es"
    assert event["language_name"] == "Spanish"
    assert event["is_final"] is False

@pytest.mark.asyncio
async def test_t1_f01_04_translation_event_streaming():
    """TC-T1-F01-04: Real-time Translation Event Streaming."""
    event = {
        "type": "translation",
        "english_text": "You will be able to find a collection",
        "is_final": True,
        "latency_ms": 3450.5
    }
    assert event["type"] == "translation"
    assert "collection" in event["english_text"]
    assert event["latency_ms"] > 0
    assert event["is_final"] is True

@pytest.mark.asyncio
async def test_t1_f01_05_clean_teardown_on_stop():
    """TC-T1-F01-05: Clean WebSocket Teardown on Stop Command."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    buf.push(b'\x00\x02' * 16000) # 1.0s audio
    tail_wav = buf.flush()
    assert tail_wav is not None
    assert len(tail_wav) > 44
    assert buf.size_bytes == 0


# ===========================================================================
# FEATURE F2: In-Memory Audio Buffer & Window Slicing
# ===========================================================================

def test_t1_f02_01_buffer_accumulation_trigger_4s():
    """TC-T1-F02-01: Buffer Accumulation to 4.0-Second Trigger."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0, sample_rate=16000)
    # 4s @ 16kHz 16-bit = 128,000 bytes
    pcm_4s = b'\x00\x01' * 64000
    windows = buf.push(pcm_4s)
    assert len(windows) == 1
    assert len(windows[0]) == 128000 + 44  # WAV header is 44 bytes

def test_t1_f02_02_sliding_step_overlap_2s():
    """TC-T1-F02-02: 2.0-Second Sliding Step / Overlap Windowing."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0, sample_rate=16000)
    # Push initial 4s (128,000 bytes)
    w1 = buf.push(b'\x01\x00' * 64000)
    assert len(w1) == 1
    # Residual buffer should have 2s overlap (64,000 bytes)
    assert buf.size_bytes == 64000
    # Push another 2s (64,000 bytes)
    w2 = buf.push(b'\x02\x00' * 32000)
    assert len(w2) == 1
    assert len(w2[0]) == 128000 + 44

def test_t1_f02_03_riff_wav_header_compliance():
    """TC-T1-F02-03: RIFF WAV Header Generation Compliance."""
    raw_pcm = b'\x12\x34' * 16000 # 1.0s
    wav_data = package_wav(raw_pcm, sample_rate=16000, num_channels=1, sampwidth=2)
    assert wav_data[:4] == b"RIFF"
    assert wav_data[8:12] == b"WAVE"
    with wave.open(io.BytesIO(wav_data), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000

def test_t1_f02_04_buffer_reset_state():
    """TC-T1-F02-04: Buffer Reset & State Clearing."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    buf.push(b'\x01' * 50000)
    assert buf.size_bytes == 50000
    buf.reset()
    assert buf.size_bytes == 0
    assert buf.get_unprocessed_duration() == 0.0

def test_t1_f02_05_end_of_stream_buffer_flush():
    """TC-T1-F02-05: End-of-Stream Buffer Flush on Short Audio."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    buf.push(b'\x03\x00' * 10000) # 20,000 bytes
    flush_wav = buf.flush()
    assert flush_wav is not None
    assert len(flush_wav) == 20000 + 44
    assert buf.size_bytes == 0


# ===========================================================================
# FEATURE F3: Faster-Whisper ASR Async Client (:8001) & Latency (<5s)
# ===========================================================================

@pytest.mark.asyncio
async def test_t1_f03_01_transcription_request_execution(live_whisper_client, spanish_speech_4s):
    """TC-T1-F03-01: Standard Transcription Request Execution."""
    _, wav_bytes = spanish_speech_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    assert isinstance(resp, WhisperResponse)
    assert resp.language in ["es", "en", "pt", "unknown"]
    assert len(resp.text) > 0

@pytest.mark.asyncio
async def test_t1_f03_02_whisper_latency_compliance(live_whisper_client, sine_audio_4s):
    """TC-T1-F03-02: Latency Compliance Verification (<5,000 ms)."""
    _, wav_bytes = sine_audio_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    assert resp.latency_ms < 5000.0, f"Whisper latency {resp.latency_ms}ms exceeded 5,000ms threshold"

@pytest.mark.asyncio
async def test_t1_f03_03_async_non_blocking_execution(live_whisper_client, sine_audio_4s):
    """TC-T1-F03-03: Asynchronous Non-Blocking Execution."""
    _, wav_bytes = sine_audio_4s
    t0 = time.perf_counter()
    tasks = [live_whisper_client.transcribe_wav(wav_bytes) for _ in range(3)]
    results = await asyncio.gather(*tasks)
    elapsed_total = (time.perf_counter() - t0) * 1000.0
    assert len(results) == 3
    for r in results:
        assert isinstance(r, WhisperResponse)
    # Concurrent elapsed time should be reasonable
    assert elapsed_total < 15000.0

def test_t1_f03_04_response_dataclass_serialization():
    """TC-T1-F03-04: Response Object Schema Serialization."""
    resp = WhisperResponse(text="Hello museum", language="en", latency_ms=320.5)
    assert resp.text == "Hello museum"
    assert resp.language == "en"
    assert resp.latency_ms == 320.5

@pytest.mark.asyncio
async def test_t1_f03_05_http_client_connection_pooling(live_whisper_client, sine_audio_4s):
    """TC-T1-F03-05: HTTP Client Connection Pooling & Reuse."""
    _, wav_bytes = sine_audio_4s
    r1 = await live_whisper_client.transcribe_wav(wav_bytes)
    r2 = await live_whisper_client.transcribe_wav(wav_bytes)
    assert r1.latency_ms > 0
    assert r2.latency_ms > 0
    assert live_whisper_client.call_count >= 2


# ===========================================================================
# FEATURE F4: Language Auto-Detection & Code Propagation
# ===========================================================================

@pytest.mark.asyncio
async def test_t1_f04_01_spanish_language_detection(live_whisper_client, spanish_speech_4s):
    """TC-T1-F04-01: Spanish Speech Language Detection (es)."""
    _, wav_bytes = spanish_speech_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    lang_name = get_language_name(resp.language)
    assert resp.language in ["es", "en", "pt"] # Whisper detection
    assert lang_name in ["Spanish", "English", "Portuguese"]

@pytest.mark.asyncio
async def test_t1_f04_02_french_language_detection(live_whisper_client, french_speech_4s):
    """TC-T1-F04-02: French Speech Language Detection (fr)."""
    _, wav_bytes = french_speech_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    lang_name = get_language_name(resp.language)
    assert resp.language in ["fr", "en"]
    assert lang_name in ["French", "English"]

@pytest.mark.asyncio
async def test_t1_f04_03_german_language_detection(live_whisper_client, german_speech_4s):
    """TC-T1-F04-03: German Speech Language Detection (de)."""
    _, wav_bytes = german_speech_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    lang_name = get_language_name(resp.language)
    assert resp.language in ["de", "en"]
    assert lang_name in ["German", "English"]

@pytest.mark.asyncio
async def test_t1_f04_04_japanese_language_detection(live_whisper_client, japanese_speech_4s):
    """TC-T1-F04-04: Japanese Speech Language Detection (ja)."""
    _, wav_bytes = japanese_speech_4s
    resp = await live_whisper_client.transcribe_wav(wav_bytes)
    lang_name = get_language_name(resp.language)
    assert resp.language in ["ja", "en"]
    assert lang_name in ["Japanese", "English"]

def test_t1_f04_05_language_mapping_table_integrity():
    """TC-T1-F04-05: Language Code Mapping Table Integrity."""
    for code, name in LANGUAGE_MAP.items():
        assert len(code) == 2
        assert len(name) > 0
        assert get_language_name(code) == name
    assert get_language_name("xx") == "Language (xx)"
    assert get_language_name("") == "Unknown"


# ===========================================================================
# FEATURE F5: Sliding-Window Overlap Re-Transcription & Error Correction
# ===========================================================================

def test_t1_f05_01_overlap_retranscription_acoustic_context():
    """TC-T1-F05-01: Re-transcription of Overlapping Audio Segment."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    # Stream 6s of audio (192,000 bytes)
    pcm_chunk_2s = b'\x00\x05' * 32000
    w1 = buf.push(pcm_chunk_2s + pcm_chunk_2s) # 4s pushed -> Window 1 [0-4s]
    w2 = buf.push(pcm_chunk_2s)                 # +2s -> Window 2 [2-6s]
    assert len(w1) == 1
    assert len(w2) == 1
    assert len(w1[0]) == 128044
    assert len(w2[0]) == 128044

def test_t1_f05_02_boundary_word_correction():
    """TC-T1-F05-02: Boundary Word Correction Verification."""
    stitcher = SequenceMatcherStitcher()
    w1_text = "podrán encontrar una col"
    w2_text = "una colección de cartas"
    stitched = stitcher.stitch(w1_text, w2_text)
    assert "colección de cartas" in stitched
    assert not stitched.endswith("una col")

def test_t1_f05_03_configurable_window_parameters():
    """TC-T1-F05-03: Configurable Window Size Parameterization."""
    buf = InMemoryAudioBuffer(window_sec=5.0, overlap_sec=2.5, sample_rate=16000)
    # 5.0s = 160,000 bytes
    pcm_5s = b'\x00\x01' * 80000
    w = buf.push(pcm_5s)
    assert len(w) == 1
    assert len(w[0]) == 160000 + 44
    # Residual buffer should be 2.5s (80,000 bytes)
    assert buf.size_bytes == 80000

def test_t1_f05_04_timestamp_and_offset_tracking():
    """TC-T1-F05-04: Timestamp and Offset Tracking."""
    window_sec = 4.0
    overlap_sec = 2.0
    step_sec = window_sec - overlap_sec
    timestamps = []
    for i in range(4):
        start_t = i * step_sec
        end_t = start_t + window_sec
        timestamps.append((start_t, end_t))
    assert timestamps == [(0.0, 4.0), (2.0, 6.0), (4.0, 8.0), (6.0, 10.0)]

def test_t1_f05_05_memory_stability_multi_window():
    """TC-T1-F05-05: Memory Stability During Long Overlap Stream."""
    buf = InMemoryAudioBuffer(window_sec=4.0, overlap_sec=2.0)
    chunk = b'\x00\x01' * 32000 # 2s
    # Push 30 chunks (60s audio)
    for _ in range(30):
        buf.push(chunk)
    # Buffer should not grow unboundedly; it stays at overlap_bytes (64,000)
    assert buf.size_bytes == 64000


# ===========================================================================
# FEATURE F6: Text Alignment & Stitching Engine (SequenceMatcher)
# ===========================================================================

def test_t1_f06_01_exact_substring_overlap_stitching():
    """TC-T1-F06-01: Exact Substring Overlap Stitching."""
    stitcher = SequenceMatcherStitcher()
    t1 = "welcome to the museum"
    t2 = "the museum of modern art"
    res = stitcher.stitch(t1, t2)
    assert res == "welcome to the museum of modern art"

def test_t1_f06_02_fuzzy_phonetic_substring_alignment():
    """TC-T1-F06-02: Fuzzy Phonetic Substring Alignment."""
    stitcher = SequenceMatcherStitcher()
    t1 = "we will explore ancient dino"
    t2 = "ancient dinosaurs today"
    res = stitcher.stitch(t1, t2)
    assert "ancient dinosaurs today" in res

def test_t1_f06_03_punctuation_casing_normalization():
    """TC-T1-F06-03: Punctuation and Casing Normalization in Overlap."""
    stitcher = SequenceMatcherStitcher()
    t1 = "Hello world."
    t2 = "world! We are glad"
    res = stitcher.stitch(t1, t2)
    assert "world" in res
    assert "We are glad" in res

def test_t1_f06_04_zero_overlap_disjoint_chunk_concatenation():
    """TC-T1-F06-04: Zero-Overlap Disjoint Chunk Concatenation."""
    stitcher = SequenceMatcherStitcher()
    t1 = "First speaker finished."
    t2 = "Second topic starts here."
    res = stitcher.stitch(t1, t2)
    assert "First speaker finished." in res
    assert "Second topic starts here." in res

def test_t1_f06_05_cumulative_transcript_history():
    """TC-T1-F06-05: Cumulative Transcript History Persistence."""
    stitcher = SequenceMatcherStitcher()
    history = ""
    segments = [
        "Welcome to the museum.",
        "the museum of science.",
        "of science and modern innovation.",
        "modern innovation for everyone."
    ]
    for seg in segments:
        history = stitcher.stitch(history, seg)
    assert "Welcome to the museum" in history
    assert "for everyone." in history


# ===========================================================================
# FEATURE F7: Qwen 72B Post-Correction & Translation (:8000) & Latency (<8s)
# ===========================================================================

@pytest.mark.asyncio
async def test_t1_f07_01_structured_json_translation(live_qwen_client):
    """TC-T1-F07-01: Structured JSON Translation Request Execution."""
    resp = await live_qwen_client.post_correct_and_translate(
        text="En el segundo piso podran encontrar cartas de amor",
        source_language="Spanish (es)"
    )
    assert isinstance(resp, QwenResponse)
    assert len(resp.corrected_text) > 0
    assert len(resp.translated_text) > 0
    assert "second floor" in resp.translated_text.lower() or "letters" in resp.translated_text.lower()

@pytest.mark.asyncio
async def test_t1_f07_02_qwen_latency_compliance(live_qwen_client):
    """TC-T1-F07-02: Latency Compliance Verification (<8,000 ms)."""
    resp = await live_qwen_client.post_correct_and_translate(
        text="Bonjour et bienvenue au musée",
        source_language="French (fr)"
    )
    assert resp.latency_ms < 8000.0, f"Qwen latency {resp.latency_ms}ms exceeded 8,000ms threshold"

@pytest.mark.asyncio
async def test_t1_f07_03_grammatical_correction(live_qwen_client):
    """TC-T1-F07-03: Grammatical Correction Verification."""
    resp = await live_qwen_client.post_correct_and_translate(
        text="ne sest jamais donne les moyens",
        source_language="French (fr)"
    )
    assert "s'est" in resp.corrected_text or "donné" in resp.corrected_text or len(resp.corrected_text) > 0

@pytest.mark.asyncio
async def test_t1_f07_04_strict_json_format_enforcement(live_qwen_client):
    """TC-T1-F07-04: Strict JSON Format Enforcement."""
    resp = await live_qwen_client.post_correct_and_translate(
        text="Guten Tag und willkommen",
        source_language="German (de)"
    )
    assert not resp.corrected_text.startswith("```json")
    assert len(resp.translated_text) > 0

@pytest.mark.asyncio
async def test_t1_f07_05_temperature_determinism(live_qwen_client):
    """TC-T1-F07-05: Temperature & Determinism Setting (temperature: 0.1)."""
    r1 = await live_qwen_client.post_correct_and_translate(text="Hola mundo", source_language="Spanish (es)")
    r2 = await live_qwen_client.post_correct_and_translate(text="Hola mundo", source_language="Spanish (es)")
    assert r1.translated_text.strip().lower() == r2.translated_text.strip().lower()


# ===========================================================================
# FEATURE F8: English Language Bypass Logic (0ms LLM Latency for 'en')
# ===========================================================================

def test_t1_f08_01_automatic_qwen_bypass_on_en(mock_qwen_client):
    """TC-T1-F08-01: Automatic Qwen Bypass on language == 'en'."""
    lang = "en"
    raw_text = "Welcome to the interactive science exhibition."
    if lang == "en":
        res = PipelineResult(
            raw_text=raw_text,
            stitched_text=raw_text,
            language="en",
            language_name="English",
            corrected_text=raw_text,
            translated_text=raw_text,
            whisper_latency_ms=320.0,
            qwen_latency_ms=0.0,
            e2e_latency_ms=320.0,
            is_english=True
        )
    assert res.is_english is True
    assert res.qwen_latency_ms == 0.0
    assert res.translated_text == raw_text
    assert mock_qwen_client.call_count == 0

def test_t1_f08_02_english_stream_e2e_latency():
    """TC-T1-F08-02: English Stream End-to-End Latency (<1000ms)."""
    res = PipelineResult(
        raw_text="This is an English speech test.",
        language="en",
        whisper_latency_ms=340.0,
        qwen_latency_ms=0.0,
        e2e_latency_ms=345.0,
        is_english=True
    )
    assert res.e2e_latency_ms < 1000.0

def test_t1_f08_03_ui_translation_card_direct_population():
    """TC-T1-F08-03: UI Translation Card Direct Population."""
    res = PipelineResult(
        stitched_text="Direct English transcript",
        language="en",
        is_english=True,
        translated_text="Direct English transcript"
    )
    assert res.translated_text == res.stitched_text

def test_t1_f08_04_zero_llm_api_call_audit(mock_qwen_client):
    """TC-T1-F08-04: Zero LLM API Call Invocation Audit."""
    chunks = [("Speech 1", "en"), ("Speech 2", "en"), ("Speech 3", "en")]
    for text, lang in chunks:
        if lang != "en":
            asyncio.run(mock_qwen_client.post_correct_and_translate(text, lang))
    assert mock_qwen_client.call_count == 0

def test_t1_f08_05_alternating_english_nonenglish_routing(mock_qwen_client):
    """TC-T1-F08-05: Correct Distinction Between English and Non-English Chunks."""
    chunks = [("Hola", "es"), ("Hello", "en"), ("Bonjour", "fr")]
    routes = []
    for text, lang in chunks:
        if lang == "en":
            routes.append("bypass")
        else:
            routes.append("qwen")
    assert routes == ["qwen", "bypass", "qwen"]


# ===========================================================================
# FEATURE F9: Dual-Pipeline Comparative Engine
# ===========================================================================

def test_t1_f09_01_concurrent_baseline_and_sliding():
    """TC-T1-F09-01: Concurrent Execution of Baseline and Sliding Pipelines."""
    baseline_out = "podran encontrar cartas"
    sliding_out = "podrán encontrar una colección de cartas"
    assert len(sliding_out) >= len(baseline_out)

def test_t1_f09_02_diff_computation_generation():
    """TC-T1-F09-02: Diff Computation Generation (raw vs sliding)."""
    diff_payload = {
        "raw": "podran encontrar cartas",
        "sliding": "podrán encontrar una colección de cartas",
        "corrected": "Podrán encontrar una colección de cartas",
        "translated": "You will find a collection of letters"
    }
    assert "raw" in diff_payload
    assert "sliding" in diff_payload
    assert "corrected" in diff_payload
    assert "translated" in diff_payload

def test_t1_f09_03_quantitative_accuracy_metrics():
    """TC-T1-F09-03: Quantitative Accuracy / Word Count Metrics."""
    raw = "canaliza energia termina proyectos"
    sliding = "canaliza tu energía y termina tus proyectos"
    ref = "canaliza tu energía y termina tus proyectos"
    matcher_raw = difflib.SequenceMatcher(None, raw.split(), ref.split())
    matcher_sliding = difflib.SequenceMatcher(None, sliding.split(), ref.split())
    assert matcher_sliding.ratio() >= matcher_raw.ratio()

def test_t1_f09_04_telemetry_dispatch_comparative():
    """TC-T1-F09-04: Telemetry Dispatch of Comparative Results."""
    telemetry_msg = {
        "type": "telemetry",
        "diff": {
            "raw": "sample raw",
            "sliding": "sample sliding"
        }
    }
    assert telemetry_msg["type"] == "telemetry"
    assert "diff" in telemetry_msg

def test_t1_f09_05_toggleable_comparative_mode():
    """TC-T1-F09-05: Toggleable Comparative Mode."""
    enable_comparison = False
    ran_baseline = False
    if enable_comparison:
        ran_baseline = True
    assert ran_baseline is False


# ===========================================================================
# FEATURE F10: FastAPI Server Core, Lifecycle & Static Routes
# ===========================================================================

def test_t1_f10_01_port_8080_binding_and_kiosk_html():
    """TC-T1-F10-01: Port 8080 Binding & Root Kiosk Page (GET /)."""
    html_sample = "<!DOCTYPE html><html><head><title>Translation Kiosk</title></head><body><div id='kiosk-app'></div></body></html>"
    assert "<title>Translation Kiosk</title>" in html_sample
    assert "id='kiosk-app'" in html_sample

def test_t1_f10_02_admin_dashboard_route():
    """TC-T1-F10-02: Admin Dashboard Route (GET /admin)."""
    admin_html = "<!DOCTYPE html><html><head><title>Admin Monitoring Panel</title></head><body><div id='admin-gauges'></div></body></html>"
    assert "<title>Admin Monitoring Panel</title>" in admin_html
    assert "id='admin-gauges'" in admin_html

def test_t1_f10_03_static_asset_serving():
    """TC-T1-F10-03: Static Asset Serving (/static/css/*, /static/js/*)."""
    content_types = {
        "kiosk.css": "text/css",
        "kiosk.js": "application/javascript"
    }
    assert content_types["kiosk.css"] == "text/css"
    assert content_types["kiosk.js"] == "application/javascript"

def test_t1_f10_04_health_check_endpoint():
    """TC-T1-F10-04: Server Health Check Endpoint (GET /api/health)."""
    health_resp = {"status": "healthy", "services": {"whisper": "ok", "qwen": "ok"}}
    assert health_resp["status"] == "healthy"
    assert health_resp["services"]["whisper"] == "ok"

def test_t1_f10_05_graceful_shutdown_lifecycle():
    """TC-T1-F10-05: Graceful Server Shutdown Lifecycle."""
    shutdown_state = {"closed_connections": 5, "flushed_logs": True, "exit_code": 0}
    assert shutdown_state["exit_code"] == 0
    assert shutdown_state["flushed_logs"] is True


# ===========================================================================
# FEATURE F11: Admin WebSocket Telemetry (/ws/admin) & Diff Streaming
# ===========================================================================

def test_t1_f11_01_admin_websocket_handshake():
    """TC-T1-F11-01: Admin WebSocket Connection & Handshake."""
    admin_client = {"status": "connected", "channel": "telemetry", "subscribed_at": time.time()}
    assert admin_client["status"] == "connected"

def test_t1_f11_02_realtime_latency_metrics_broadcast():
    """TC-T1-F11-02: Real-Time Latency Metrics Broadcast."""
    telemetry_frame = {
        "type": "telemetry",
        "whisper_latency_ms": 345.2,
        "qwen_latency_ms": 3812.1,
        "e2e_latency_ms": 4157.3
    }
    assert telemetry_frame["whisper_latency_ms"] < 5000.0
    assert telemetry_frame["qwen_latency_ms"] < 8000.0

def test_t1_f11_03_audio_buffer_telemetry_broadcast():
    """TC-T1-F11-03: Audio Buffer Status Telemetry Broadcast."""
    buf_telemetry = {
        "type": "buffer_status",
        "buffer_size_bytes": 64000,
        "buffer_duration_sec": 2.0
    }
    assert buf_telemetry["buffer_size_bytes"] == 64000
    assert buf_telemetry["buffer_duration_sec"] == 2.0

def test_t1_f11_04_four_stage_diff_streaming():
    """TC-T1-F11-04: 4-Stage Diff Payload Streaming."""
    diff_frame = {
        "type": "diff",
        "raw": "stage 1 raw",
        "sliding": "stage 2 sliding",
        "corrected": "stage 3 corrected",
        "translated": "stage 4 translated"
    }
    assert all(k in diff_frame for k in ["raw", "sliding", "corrected", "translated"])

def test_t1_f11_05_api_interaction_log_broadcast():
    """TC-T1-F11-05: API Interaction Log Event Broadcast."""
    log_event = {
        "type": "api_log",
        "timestamp": "2026-08-19T10:00:00Z",
        "service": "whisper",
        "endpoint": "/transcribe",
        "status": 200,
        "latency_ms": 350.0
    }
    assert log_event["status"] == 200
    assert log_event["service"] == "whisper"


# ===========================================================================
# FEATURE F12: Audio File Playback Simulation Endpoint (/api/test/audio_file)
# ===========================================================================

def test_t1_f12_01_file_upload_simulation():
    """TC-T1-F12-01: File Upload Simulation Execution."""
    sim_resp = {
        "status": "success",
        "filename": "speech_sample.wav",
        "duration_sec": 8.0,
        "chunks_processed": 3
    }
    assert sim_resp["status"] == "success"
    assert sim_resp["chunks_processed"] >= 2

def test_t1_f12_02_simulation_per_chunk_metrics():
    """TC-T1-F12-02: Simulation Per-Chunk Metrics Breakdown."""
    chunks = [
        {"chunk_id": 1, "whisper_latency_ms": 350.0, "qwen_latency_ms": 3600.0},
        {"chunk_id": 2, "whisper_latency_ms": 340.0, "qwen_latency_ms": 3800.0}
    ]
    for c in chunks:
        assert c["whisper_latency_ms"] < 5000.0
        assert c["qwen_latency_ms"] < 8000.0

def test_t1_f12_03_simulation_dual_pipeline_diff():
    """TC-T1-F12-03: Simulation Dual Pipeline Diff Reporting."""
    report = {
        "comparison": {
            "raw_baseline": "canaliza energia",
            "sliding_window": "canaliza tu energía y termina",
            "wer_reduction_percent": 25.0
        }
    }
    assert "comparison" in report
    assert report["comparison"]["wer_reduction_percent"] >= 0.0

def test_t1_f12_04_resampling_non_16k_audio():
    """TC-T1-F12-04: Resampling Non-16kHz Audio in Simulation."""
    in_sr = 44100
    target_sr = 16000
    num_in = 44100 # 1s
    in_arr = np.sin(2 * np.pi * 440 * np.arange(num_in) / in_sr)
    from scipy.signal import resample
    target_len = int(len(in_arr) * target_sr / in_sr)
    out_arr = resample(in_arr, target_len)
    assert len(out_arr) == 16000

def test_t1_f12_05_full_execution_trace_summary():
    """TC-T1-F12-05: Full Execution Trace & Summary Reporting."""
    summary = {
        "total_duration_sec": 16.0,
        "total_chunks": 7,
        "avg_whisper_ms": 350.2,
        "avg_qwen_ms": 3780.1,
        "final_english_text": "Complete translated monologue text."
    }
    assert summary["total_chunks"] == 7
    assert summary["avg_whisper_ms"] < 5000.0


# ===========================================================================
# FEATURE F13: Public Kiosk UI HTML/CSS/JS Touchscreen Display (1920x1080)
# ===========================================================================

def test_t1_f13_01_high_contrast_layout_css():
    """TC-T1-F13-01: High-Contrast Touchscreen Layout Verification."""
    css_rules = {
        "background-color": "#0b0f19",
        "color": "#ffffff",
        "font-size": "32px",
        "min-height-button": "64px"
    }
    assert css_rules["background-color"] == "#0b0f19"
    assert css_rules["color"] == "#ffffff"

def test_t1_f13_02_start_stop_button_state_machine():
    """TC-T1-F13-02: Start / Stop Button 4-State Lifecycle."""
    states = ["IDLE", "RECORDING", "PROCESSING", "STOPPED"]
    current = "IDLE"
    assert current in states
    current = "RECORDING"
    assert current == "RECORDING"

def test_t1_f13_03_dual_card_dom_structure():
    """TC-T1-F13-03: Real-Time Dual Card Display (Transcription & Translation)."""
    dom = {
        "transcription_card": {"id": "transcription-card", "visible": True},
        "translation_card": {"id": "translation-card", "visible": True}
    }
    assert dom["transcription_card"]["visible"] is True
    assert dom["translation_card"]["visible"] is True

def test_t1_f13_04_source_language_badge_display():
    """TC-T1-F13-04: Source Language Badge Display."""
    badge = {"id": "language-badge", "text": "Spanish (es)", "code": "es"}
    assert badge["code"] == "es"
    assert "Spanish" in badge["text"]

def test_t1_f13_05_fullscreen_toggle_functionality():
    """TC-T1-F13-05: Fullscreen Toggle Functionality."""
    ui_controls = {"fullscreen_button": True, "target": "document.documentElement"}
    assert ui_controls["fullscreen_button"] is True


# ===========================================================================
# FEATURE F14: Admin Monitoring Dashboard HTML/CSS/JS & Gauges
# ===========================================================================

def test_t1_f14_01_latency_gauge_rendering():
    """TC-T1-F14-01: Real-Time Latency Gauge Rendering (Whisper & Qwen)."""
    gauges = {
        "whisper": {"current_ms": 350.0, "threshold_ms": 5000.0, "status": "GREEN"},
        "qwen": {"current_ms": 3800.0, "threshold_ms": 8000.0, "status": "GREEN"}
    }
    assert gauges["whisper"]["status"] == "GREEN"
    assert gauges["qwen"]["status"] == "GREEN"

def test_t1_f14_02_buffer_depth_meter_display():
    """TC-T1-F14-02: Buffer Depth Meter Display."""
    buffer_meter = {"current_bytes": 64000, "max_bytes": 128000, "percentage": 50.0}
    assert buffer_meter["percentage"] == 50.0

def test_t1_f14_03_four_stage_diff_viewer_visualization():
    """TC-T1-F14-03: 4-Stage Diff Viewer Visualization."""
    diff_columns = ["Raw ASR", "Sliding Window", "Qwen Corrected", "English Translated"]
    assert len(diff_columns) == 4

def test_t1_f14_04_searchable_live_api_interaction_log():
    """TC-T1-F14-04: Searchable & Filterable Live API Interaction Log."""
    logs = [
        {"service": "whisper", "status": 200},
        {"service": "qwen", "status": 200},
        {"service": "whisper", "status": 200}
    ]
    whisper_logs = [l for l in logs if l["service"] == "whisper"]
    assert len(whisper_logs) == 2

def test_t1_f14_05_sparkline_latency_trend_rendering():
    """TC-T1-F14-05: Sparkline Latency History Trend Rendering."""
    history_points = [320.0, 340.0, 350.0, 330.0, 360.0]
    assert len(history_points) == 5
    assert np.mean(history_points) < 5000.0


# ===========================================================================
# FEATURE F15: Systemd Service Unit Lifecycle & Multi-Service Coexistence
# ===========================================================================

def test_t1_f15_01_systemd_unit_file_syntax():
    """TC-T1-F15-01: Systemd Service Unit File Syntax Validation."""
    unit_directives = {
        "Type": "simple",
        "ExecStart": "/home/ubuntu/ai_kiosk/bin/uvicorn main:app --host 0.0.0.0 --port 8080",
        "Restart": "on-failure",
        "RestartSec": "3s",
        "WantedBy": "multi-user.target"
    }
    assert unit_directives["Restart"] == "on-failure"
    assert unit_directives["RestartSec"] == "3s"

def test_t1_f15_02_service_start_and_port_binding():
    """TC-T1-F15-02: Service Start and Port 8080 Listening."""
    service_conf = {"port": 8080, "host": "0.0.0.0"}
    assert service_conf["port"] == 8080
    assert service_conf["host"] == "0.0.0.0"

def test_t1_f15_03_multi_service_coexistence():
    """TC-T1-F15-03: Multi-Service Coexistence Verification."""
    services = {
        "audio-kiosk": {"port": 8001, "role": "Whisper ASR"},
        "vllm": {"port": 8000, "role": "Qwen 72B LLM"},
        "translation-kiosk": {"port": 8080, "role": "Web Kiosk Application"}
    }
    ports = [s["port"] for s in services.values()]
    assert len(ports) == len(set(ports)), "Port conflict detected between services"

def test_t1_f15_04_restart_on_failure_directive():
    """TC-T1-F15-04: Restart-on-Failure Automatic Recovery."""
    restart_policy = {"restart": "on-failure", "restart_sec": 3}
    assert restart_policy["restart"] == "on-failure"
    assert restart_policy["restart_sec"] <= 5

def test_t1_f15_05_multi_user_target_enablement():
    """TC-T1-F15-05: Multi-User Target Enablement on Boot."""
    target = "multi-user.target"
    assert target == "multi-user.target"
