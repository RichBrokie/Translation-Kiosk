import sys
import os
import asyncio
import time
import json
import wave
import io
import difflib

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from config import *
from telemetry import TelemetryCollector, ChunkTelemetry
from whisper_client import WhisperClient, TranscriptionResult
from qwen_client import QwenClient, parse_qwen_json
from audio_pipeline import (
    pack_pcm_to_wav,
    AudioRollingBuffer,
    TextStitcher,
    ComparativeEngine,
    AudioPipeline
)

async def test_live_services():
    print('=== 1. LIVE SERVICE VERIFICATION ===')
    
    # 1. Test Live Whisper
    whisper = WhisperClient()
    wav_files = []
    for root, dirs, files in os.walk('/mnt/models'):
        for f in files:
            if f.endswith('.wav'):
                wav_files.append(os.path.join(root, f))
    
    print(f'Found {len(wav_files)} WAV files in /mnt/models')
    sample_wav_path = wav_files[0] if wav_files else None
    
    if sample_wav_path:
        with wave.open(sample_wav_path, 'rb') as wf:
            n_frames = wf.getnframes()
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            print(f'Sample WAV: {sample_wav_path}')
            print(f'Params: {n_frames} frames, {sr}Hz, {ch}ch, {sw}B/sample')
            pcm = wf.readframes(sr * 4) # 4 seconds
            
        wav_payload = pack_pcm_to_wav(pcm, sample_rate=sr, channels=ch, bits_per_sample=sw*8)
        res = await whisper.transcribe_wav(wav_payload)
        print(f'Live Whisper result: text="{res.text}", lang="{res.language}", lang_name="{res.language_name}", latency={res.latency_ms:.1f}ms')
        assert res.text != "", "Whisper transcription returned empty text for real speech"
        assert res.language != "", "Whisper returned empty language"
    else:
        print('Warning: No WAV file found in /mnt/models')

    # 2. Test Live Qwen
    qwen = QwenClient()
    res_qwen = await qwen.post_correct_and_translate(
        "hola senor como esta usted hoy en el museo",
        source_language="es"
    )
    print(f'Live Qwen (es) result:')
    print(f'  corrected: "{res_qwen.corrected_text}"')
    print(f'  english:   "{res_qwen.english_translation}"')
    print(f'  latency:   {res_qwen.latency_ms:.1f}ms')
    assert "museum" in res_qwen.english_translation.lower() or "sir" in res_qwen.english_translation.lower() or "how" in res_qwen.english_translation.lower(), "Qwen translation failed"

    # 3. Test Live Qwen English Bypass
    res_bypass = await qwen.post_correct_and_translate(
        "Welcome to the science exhibit today",
        source_language="en"
    )
    print(f'Live Qwen (en bypass) result: latency={res_bypass.latency_ms:.1f}ms, bypassed={res_bypass.bypassed}')
    assert res_bypass.bypassed is True
    assert res_bypass.latency_ms == 0.0
    assert res_bypass.english_translation == "Welcome to the science exhibit today"
    
    await whisper.close()
    await qwen.close()
    print('>>> LIVE SERVICE VERIFICATION PASSED <<<\n')

async def test_edge_cases_and_adversarial():
    print('=== 2. ADVERSARIAL & EDGE CASE STRESS TESTS ===')

    # Test A: TextStitcher with non-Latin scripts (Chinese, Arabic, Russian)
    print('[Test A] Non-Latin script stitching')
    stitcher_zh = TextStitcher(overlap_ratio=0.5)
    c1, t1, d1, r1 = stitcher_zh.process_window("欢迎 来到 科学 博物馆")
    c2, t2, d2, r2 = stitcher_zh.process_window("科学 博物馆 探索 明天 的 科技")
    print(f'  Chinese stitched: "{d2}"')
    assert "科学 博物馆 探索" in d2
    assert d2.count("科学 博物馆") == 1

    # Test B: Severe noise / boundary stutter / partial truncation
    print('[Test B] Partial word truncation repair')
    stitcher_repair = TextStitcher(overlap_ratio=0.5)
    stitcher_repair.process_window("the dinosaur is very danger")
    _, _, d_rep, r_count = stitcher_repair.process_window("dangerous creature from prehistory")
    print(f'  Repaired display: "{d_rep}", repairs={r_count}')
    assert "dangerous creature" in d_rep
    assert "danger dangerous" not in d_rep
    assert r_count >= 1

    # Test C: Silence hallucinations filtering
    print('[Test C] Hallucination filters')
    assert TextStitcher.clean_hallucinations("[Music]") == ""
    assert TextStitcher.clean_hallucinations("(Applause)") == ""
    assert TextStitcher.clean_hallucinations("Thank you for watching!") == ""
    assert TextStitcher.clean_hallucinations("Subtitles by...") == ""
    assert TextStitcher.clean_hallucinations("...") == ""

    # Test D: Resilient JSON parser stress test
    print('[Test D] Qwen JSON Parser resilience against adversarial outputs')
    # 1. Markdown with triple backticks
    p1 = parse_qwen_json('```json\n{"corrected_text": "foo", "english_translation": "bar"}\n```', "fallback")
    assert p1 == {"corrected_text": "foo", "english_translation": "bar"}

    # 2. Markdown without 'json' tag
    p2 = parse_qwen_json('```\n{"corrected_text": "foo", "english_translation": "bar"}\n```', "fallback")
    assert p2 == {"corrected_text": "foo", "english_translation": "bar"}

    # 3. Preamble text + JSON
    p3 = parse_qwen_json('Here is the JSON response:\n{"corrected_text": "source", "english_translation": "dest"}\nHope this helps!', "fallback")
    assert p3 == {"corrected_text": "source", "english_translation": "dest"}

    # 4. Incomplete or trailing comma JSON (falls back to regex or fallback)
    p4 = parse_qwen_json('{"corrected_text": "source", "english_translation": "dest",}', "fallback")
    assert p4["corrected_text"] == "source" and p4["english_translation"] == "dest"

    # 5. Non-JSON conversational garbage
    p5 = parse_qwen_json('Sorry, I cannot translate this audio.', "fallback_orig")
    assert p5["corrected_text"] == "fallback_orig"
    assert "Sorry" in p5["english_translation"]

    # 6. Empty string
    p6 = parse_qwen_json('', "fallback_orig")
    assert p6["corrected_text"] == "fallback_orig"

    # Test E: High volume chunk streaming & concurrency
    print('[Test E] High volume buffer streaming (1000 chunks)')
    buf = AudioRollingBuffer(window_sec=4.0, stride_sec=2.0, sample_rate=16000)
    chunk_10ms = b"\x01\x00" * 160  # 320 bytes
    
    start_time = time.perf_counter()
    async def push_batch():
        for _ in range(100):
            await buf.append_pcm(chunk_10ms)
    
    await asyncio.gather(*[push_batch() for _ in range(10)])
    elapsed = time.perf_counter() - start_time
    print(f'  Pushed 1000 chunks concurrently in {elapsed*1000:.2f}ms')
    
    metrics = await buf.get_buffer_metrics()
    assert metrics["buffered_bytes"] == 320000
    assert metrics["buffered_seconds"] == 10.0
    
    slices = 0
    while await buf.has_window():
        s = await buf.slice_next_window()
        assert s is not None
        slices += 1
    print(f'  Sliced {slices} windows (expected 4 windows)')
    assert slices == 4

    # Test F: Boundary Flush (exact thresholds)
    print('[Test F] Buffer Flush boundary conditions')
    buf_f = AudioRollingBuffer(min_flush_sec=0.5, window_sec=4.0)
    
    # Exact min_flush: 16,000 bytes (0.5s)
    await buf_f.append_pcm(b"\x00\x00" * 8000)
    f_res = await buf_f.flush()
    assert f_res is not None
    assert len(f_res[0]) == 128000 # Padded to full 4s window
    
    # Below min_flush: 15,998 bytes (< 0.5s)
    await buf_f.append_pcm(b"\x00\x00" * 7999)
    f_res2 = await buf_f.flush()
    assert f_res2 is None # Discarded

    # Test G: Telemetry Percentiles precision
    print('[Test G] Telemetry Percentile calculations')
    t = TelemetryCollector()
    assert t.compute_percentiles([]) == {"min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}
    single = t.compute_percentiles([100.0])
    assert single["min"] == 100.0 and single["p50"] == 100.0 and single["p95"] == 100.0
    
    data_100 = [float(i) for i in range(1, 101)]
    p_100 = t.compute_percentiles(data_100)
    print(f'  100-item percentiles: min={p_100["min"]}, p50={p_100["p50"]}, p90={p_100["p90"]}, p95={p_100["p95"]}, max={p_100["max"]}')
    assert p_100["min"] == 1.0
    assert p_100["max"] == 100.0
    assert p_100["p50"] == 50.5
    assert p_100["p90"] == 90.1
    assert p_100["p95"] == 95.05

    print('>>> ALL ADVERSARIAL & EDGE CASE STRESS TESTS PASSED <<<\n')

async def main():
    await test_live_services()
    await test_edge_cases_and_adversarial()

if __name__ == '__main__':
    asyncio.run(main())
