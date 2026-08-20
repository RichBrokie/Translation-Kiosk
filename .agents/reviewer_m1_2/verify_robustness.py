import sys
import os
import io
import time
import math
import struct
import wave
import asyncio
import difflib
import re

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from config import (
    SAMPLE_RATE, BYTES_PER_SAMPLE, CHANNELS, BYTE_RATE,
    WINDOW_SEC, STRIDE_SEC, OVERLAP_SEC, MIN_FLUSH_SEC,
    WINDOW_BYTES, STRIDE_BYTES, OVERLAP_BYTES, MIN_FLUSH_BYTES,
    MAX_RETENTION_BYTES, get_language_name
)
from audio_pipeline import (
    pack_pcm_to_wav,
    AudioRollingBuffer,
    TextStitcher,
    ComparativeEngine,
    AudioPipeline,
    PipelineResult
)
from whisper_client import WhisperClient, TranscriptionResult
from qwen_client import QwenClient, TranslationResult, parse_qwen_json
from telemetry import TelemetryCollector, ChunkTelemetry, APICallLog

print("=== STARTING ROBUSTNESS & EDGE-CASE VERIFICATION ===")

# ============================================================================
# 1. pack_pcm_to_wav Edge Cases
# ============================================================================
print("\n[1] Testing pack_pcm_to_wav...")

# Test 1.1: 0-byte PCM
wav_0 = pack_pcm_to_wav(b"")
assert len(wav_0) == 44, f"Expected 44 bytes, got {len(wav_0)}"
with wave.open(io.BytesIO(wav_0), "rb") as wf:
    assert wf.getnchannels() == 1
    assert wf.getsampwidth() == 2
    assert wf.getframerate() == 16000
    assert wf.getnframes() == 0
print("  - Empty PCM -> valid 44-byte WAV: PASS")

# Test 1.2: Standard 4.0s (128,000 bytes)
pcm_4s = b"\x10\x20" * 64000
wav_4s = pack_pcm_to_wav(pcm_4s)
assert len(wav_4s) == 44 + 128000
with wave.open(io.BytesIO(wav_4s), "rb") as wf:
    assert wf.getnframes() == 64000
    assert wf.readframes(64000) == pcm_4s
print("  - Standard 4.0s PCM -> valid 128,044-byte WAV: PASS")

# Test 1.3: Arbitrary/odd lengths
pcm_odd = b"\x01\x02\x03"
wav_odd = pack_pcm_to_wav(pcm_odd)
assert len(wav_odd) == 44 + 3
print("  - Odd-byte length packing: PASS")

# Test 1.4: Parameter variations
wav_stereo = pack_pcm_to_wav(b"\x00" * 8000, sample_rate=44100, channels=2, bits_per_sample=16)
with wave.open(io.BytesIO(wav_stereo), "rb") as wf:
    assert wf.getnchannels() == 2
    assert wf.getframerate() == 44100
print("  - Stereo / custom sample rate WAV: PASS")


# ============================================================================
# 2. AudioRollingBuffer Edge Cases
# ============================================================================
print("\n[2] Testing AudioRollingBuffer...")

async def test_buffer():
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, min_flush_sec=0.5, sample_rate=16000)
    
    # 2.1: Empty appends
    await buf.append_pcm(b"")
    assert not await buf.has_window()
    assert (await buf.get_buffer_metrics())["buffered_bytes"] == 0
    print("  - Empty append: PASS")

    # 2.2: Micro-chunks (e.g. 1 sample = 2 bytes, 10ms = 320 bytes, etc.)
    # Stream 4.0s in 10ms chunks (400 chunks of 320 bytes)
    for _ in range(400):
        await buf.append_pcm(b"\x05\x00" * 160)
    assert await buf.has_window()
    
    slice1 = await buf.slice_next_window()
    assert slice1 is not None
    pcm1, idx1, t1 = slice1
    assert len(pcm1) == 128000
    assert idx1 == 0
    assert t1 == 0.0
    # Remaining in buffer: 2.0s = 64,000 bytes
    metrics = await buf.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 64000
    print("  - Micro-chunk accumulation and stride math: PASS")

    # 2.3: Massive chunk (e.g. 10.0s = 320,000 bytes all at once)
    await buf.append_pcm(b"\x01\x02" * 160000)
    # Total now: 64,000 + 320,000 = 384,000 bytes.
    # Can slice window 1 (starts at t=2.0), window 2 (starts at t=4.0), etc.
    s2 = await buf.slice_next_window()
    assert s2 is not None and s2[1] == 1 and s2[2] == 2.0
    s3 = await buf.slice_next_window()
    assert s3 is not None and s3[1] == 2 and s3[2] == 4.0
    s4 = await buf.slice_next_window()
    assert s4 is not None and s4[1] == 3 and s4[2] == 6.0
    s5 = await buf.slice_next_window()
    assert s5 is not None and s5[1] == 4 and s5[2] == 8.0
    s6 = await buf.slice_next_window()
    assert s6 is not None and s6[1] == 5 and s6[2] == 10.0
    assert not await buf.has_window()
    print("  - Large batch chunk slicing (multiple windows in backlog): PASS")

    # 2.4: Flush zero-padding
    # Remaining audio: 64,000 bytes (2.0s). Flush should zero-pad to 128,000 bytes (4.0s)
    flush_res = await buf.flush()
    assert flush_res is not None
    fl_pcm, fl_idx, fl_t = flush_res
    assert len(fl_pcm) == 128000
    assert fl_pcm[:64000] == b"\x01\x02" * 32000
    assert fl_pcm[64000:] == b"\x00" * 64000
    assert fl_idx == 6
    assert fl_t == 12.0
    print("  - Flush zero-padding for >= 0.5s audio: PASS")

    # 2.5: Flush discard when < min_flush (0.5s = 16,000 bytes)
    await buf.append_pcm(b"\x03\x04" * 4000) # 8000 bytes = 0.25s
    flush_discard = await buf.flush()
    assert flush_discard is None
    assert (await buf.get_buffer_metrics())["buffered_bytes"] == 0
    print("  - Flush discard when < 0.5s residual: PASS")

    # 2.6: Flush on completely empty buffer
    assert await buf.flush() is None
    print("  - Flush on empty buffer: PASS")

    # 2.7: Memory stability / reset
    buf.reset()
    assert (await buf.get_buffer_metrics())["buffered_bytes"] == 0
    assert (await buf.get_buffer_metrics())["window_index"] == 0
    print("  - Buffer reset: PASS")

asyncio.run(test_buffer())


# ============================================================================
# 3. TextStitcher Edge Cases & Adversarial Inputs
# ============================================================================
print("\n[3] Testing TextStitcher...")

stitcher = TextStitcher(overlap_ratio=0.5)

# Test 3.1: Empty and whitespace strings
c, t, d, r = stitcher.process_window("")
assert c == "" and t == "" and d == "" and r == 0
c, t, d, r = stitcher.process_window("   ")
assert c == "" and t == "" and d == "" and r == 0
print("  - Empty / whitespace windows: PASS")

# Test 3.2: Single word windows
stitcher.reset()
c1, t1, d1, r1 = stitcher.process_window("Hello")
assert d1 == "Hello"
c2, t2, d2, r2 = stitcher.process_window("Hello world")
assert "Hello world" in d2
print("  - Single-word window sequence: PASS")

# Test 3.3: Boundary truncation repair
# Example: w1 ends with truncated word "exhibi", w2 starts with "exhibition of modern"
stitcher.reset()
w1 = "Welcome to the grand exhibi"
c1, t1, d1, r1 = stitcher.process_window(w1)
w2 = "the grand exhibition of modern art and history"
c2, t2, d2, r2 = stitcher.process_window(w2)
assert "exhibition of modern" in d2
assert "exhibi exhibition" not in d2
assert r2 >= 1
print("  - Boundary truncation repair ('exhibi' -> 'exhibition'): PASS")

# Test 3.4: Punctuation and casing normalization
stitcher.reset()
w1 = "We have seen Mars, Jupiter,"
c1, t1, d1, r1 = stitcher.process_window(w1)
w2 = "jupiter and Saturn in the telescope."
c2, t2, d2, r2 = stitcher.process_window(w2)
print("  DEBUG 3.4: c1=", repr(c1), "t1=", repr(t1), "-> c2=", repr(c2), "t2=", repr(t2), "d2=", repr(d2), "r2=", r2)
assert "Jupiter, jupiter" not in d2
assert "Saturn in the telescope." in d2
print("  - Punctuation & casing overlap alignment: PASS")

# Test 3.5: Hallucination filtering
assert stitcher.clean_hallucinations("[Music]") == ""
assert stitcher.clean_hallucinations("(Applause)") == ""
assert stitcher.clean_hallucinations("Thank you for watching!") == ""
assert stitcher.clean_hallucinations("Subtitles by...") == ""
assert stitcher.clean_hallucinations("Please subscribe to the channel") == ""
assert stitcher.clean_hallucinations("♪♪♪") == ""
assert stitcher.clean_hallucinations("... ...") == ""
assert stitcher.clean_hallucinations("Normal speech text") == "Normal speech text"
print("  - Hallucination pattern stripping: PASS")

# Test 3.6: Multi-lingual / Unicode text (Spanish, French, Chinese, Arabic)
stitcher.reset()
w1_es = "Bienvenidos al museo nacional de"
stitcher.process_window(w1_es)
w2_es = "museo nacional de antropología e historia"
c_es, t_es, d_es, r_es = stitcher.process_window(w2_es)
assert d_es == "Bienvenidos al museo nacional de antropología e historia"
print("  - Spanish Unicode alignment: PASS")

stitcher.reset()
w1_fr = "Voici le premier tableau de l'exposition"
stitcher.process_window(w1_fr)
w2_fr = "tableau de l'exposition permanente du Louvre"
c_fr, t_fr, d_fr, r_fr = stitcher.process_window(w2_fr)
assert "l'exposition permanente du Louvre" in d_fr
print("  - French apostrophe/accent alignment: PASS")

# Test 3.7: Flush final commits tentative tail
final_flush = stitcher.flush_final()
assert stitcher.tentative_tail == ""
assert len(final_flush) > 0
print("  - Final flush committing: PASS")


# ============================================================================
# 4. QwenClient & parse_qwen_json 5-Stage Resilience
# ============================================================================
print("\n[4] Testing QwenClient & parse_qwen_json...")

# Stage 1 & 2: Clean JSON & Markdown code fence
clean_json = '{"corrected_text": "Texto corregido", "english_translation": "Corrected text"}'
p1 = parse_qwen_json(clean_json, "fallback")
assert p1["corrected_text"] == "Texto corregido"
assert p1["english_translation"] == "Corrected text"

md_json = '```json\n{\n  "corrected_text": "Texto corregido",\n  "english_translation": "Corrected text"\n}\n```'
p2 = parse_qwen_json(md_json, "fallback")
assert p2["corrected_text"] == "Texto corregido"
assert p2["english_translation"] == "Corrected text"
print("  - Stage 1 & 2 (Clean JSON / Markdown fences): PASS")

# Stage 3: Embedded JSON with conversational text
embedded_json = 'Certainly! Here is the corrected translation:\n{"corrected_text": "Bonjour tout le monde", "english_translation": "Hello everyone"}\nI hope that was helpful.'
p3 = parse_qwen_json(embedded_json, "fallback")
assert p3["corrected_text"] == "Bonjour tout le monde"
assert p3["english_translation"] == "Hello everyone"
print("  - Stage 3 (Embedded JSON in conversational text): PASS")

# Stage 4: Regex field key/value extraction on broken JSON syntax
broken_json = 'Here is the result: "corrected_text": "Hola amigo", "english_translation": "Hello friend", but closing brace was missing'
p4 = parse_qwen_json(broken_json, "fallback")
assert p4["corrected_text"] == "Hola amigo"
assert p4["english_translation"] == "Hello friend"
print("  - Stage 4 (Regex field extraction on broken syntax): PASS")

# Stage 5: Completely unparseable garbage fallback
garbage = "I cannot translate this input because of reasons."
p5 = parse_qwen_json(garbage, fallback_text="Original text")
assert p5["corrected_text"] == "Original text"
assert p5["english_translation"] == garbage
print("  - Stage 5 (Graceful fallback on garbage): PASS")

# Requirement R4: English Bypass
async def test_qwen():
    qc = QwenClient(bypass_english=True)
    
    # 4.1: English bypass returns 0ms without network call
    res_en = await qc.post_correct_and_translate("Good morning visitors", source_language="en")
    assert res_en.bypassed is True
    assert res_en.latency_ms == 0.0
    assert res_en.corrected_text == "Good morning visitors"
    assert res_en.english_translation == "Good morning visitors"
    
    # 4.2: Case sensitivity & whitespace handling on language code
    res_en2 = await qc.post_correct_and_translate("Welcome", source_language="  EN  ")
    assert res_en2.bypassed is True
    res_en3 = await qc.post_correct_and_translate("Welcome", source_language="English")
    assert res_en3.bypassed is True
    
    # 4.3: Empty text returns immediately
    res_empty = await qc.post_correct_and_translate("", source_language="es")
    assert res_empty.corrected_text == ""
    assert res_empty.english_translation == ""
    assert res_empty.latency_ms == 0.0
    print("  - Requirement R4 English Bypass & edge cases: PASS")

asyncio.run(test_qwen())


# ============================================================================
# 5. TelemetryCollector Percentiles & Ring Buffer
# ============================================================================
print("\n[5] Testing TelemetryCollector...")

tc = TelemetryCollector(history_size=10, log_size=10)

# Test 5.1: Empty collector percentiles
p_empty = tc.compute_percentiles([])
assert p_empty == {"min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}
print("  - Empty percentiles computation: PASS")

# Test 5.2: Single item percentiles
p_single = tc.compute_percentiles([150.0])
assert p_single["min"] == 150.0
assert p_single["max"] == 150.0
assert p_single["avg"] == 150.0
assert p_single["p50"] == 150.0
assert p_single["p90"] == 150.0
assert p_single["p95"] == 150.0
print("  - Single-element percentiles: PASS")

# Test 5.3: Known distribution percentiles
vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
p_known = tc.compute_percentiles(vals)
assert p_known["min"] == 10.0
assert p_known["max"] == 100.0
assert p_known["avg"] == 55.0
assert p_known["p50"] == 55.0  # linear interpolation
print("  - 10-element percentiles calculation: PASS")

# Test 5.4: Ring buffer overflow & bound retention
for i in range(25):
    tc.record_chunk(ChunkTelemetry(
        chunk_id=i,
        timestamp=time.time(),
        audio_duration_s=4.0,
        buffer_depth_bytes=128000,
        whisper_latency_ms=300.0 + i,
        qwen_latency_ms=1000.0 + i,
        alignment_latency_ms=1.0,
        e2e_latency_ms=1301.0 + i,
        source_language="es",
        is_english_bypassed=False,
        repairs_count=1 if i % 2 == 0 else 0
    ))
    tc.log_api_call(
        endpoint="http://localhost:8001/transcribe",
        method="POST",
        status_code=200,
        latency_ms=300.0 + i,
        payload_summary="WAV",
        response_summary="text"
    )

assert len(tc.chunk_history) == 10, f"Expected ring buffer cap at 10, got {len(tc.chunk_history)}"
assert len(tc.api_logs) == 10, f"Expected log ring buffer cap at 10, got {len(tc.api_logs)}"
assert tc.total_chunks == 25
assert tc.total_audio_seconds == 100.0
print("  - Ring buffer capacity bound & cumulative counter preservation: PASS")

# Test 5.5: Admin payload generation
admin_payload = tc.get_admin_telemetry_payload()
assert admin_payload["type"] == "admin_telemetry"
assert admin_payload["latest_chunk"]["chunk_id"] == 24
assert len(admin_payload["recent_logs"]) <= 10
print("  - Admin telemetry payload serialization: PASS")

# Test 5.6: Collector reset
tc.reset()
assert len(tc.chunk_history) == 0
assert len(tc.api_logs) == 0
assert tc.total_chunks == 0
assert tc.total_audio_seconds == 0.0
print("  - TelemetryCollector reset: PASS")

print("\n=== ALL ROBUSTNESS & EDGE-CASE TESTS PASSED PERFECTLY ===")
