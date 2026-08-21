import asyncio
import os
import sys
import time
import json
import glob
import math
import struct
import subprocess
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from difflib import SequenceMatcher

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from config import SAMPLE_RATE, WINDOW_SEC, STRIDE_SEC, get_language_name
from audio_pipeline import AudioPipeline, AudioRollingBuffer, TextStitcher, pack_pcm_to_wav, PipelineResult
from whisper_client import WhisperClient, TranscriptionResult
from qwen_client import QwenClient, TranslationResult
from telemetry import TelemetryCollector

def compute_wer(reference: str, hypothesis: str) -> float:
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1), dtype=int)
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + 1)
    return float(d[len(ref_words)][len(hyp_words)]) / len(ref_words)

def compute_cer(reference: str, hypothesis: str) -> float:
    ref_chars = list(reference.strip().lower().replace(" ", ""))
    hyp_chars = list(hypothesis.strip().lower().replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    d = np.zeros((len(ref_chars) + 1, len(hyp_chars) + 1), dtype=int)
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j
    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i - 1] == hyp_chars[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + 1)
    return float(d[len(ref_chars)][len(hyp_chars)]) / len(ref_chars)

def load_audio_slice(file_path: str, start_sec: float = 15.0, duration_sec: float = 16.0) -> bytes:
    cmd = [
        'ffmpeg', '-y', '-ss', str(start_sec), '-t', str(duration_sec),
        '-i', file_path,
        '-ar', '16000', '-ac', '1', '-f', 's16le', 'pipe:1'
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return res.stdout

def add_noise(pcm_bytes: bytes, snr_db: float = 15.0) -> bytes:
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    signal_power = np.mean(arr ** 2)
    if signal_power == 0:
        return pcm_bytes
    noise_power = signal_power / (10 ** (snr_db / 10.0))
    noise = np.random.normal(0, np.sqrt(noise_power), len(arr))
    noisy_signal = np.clip(arr + noise, -32768, 32767).astype(np.int16)
    return noisy_signal.tobytes()

class EmpiricalChallenger:
    def __init__(self):
        self.results = {}
        self.whisper = WhisperClient(base_url="http://localhost:8001")
        self.qwen = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)

    async def challenge_1_english_bypass(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(">>> CHALLENGE 1: ENGLISH AUDIO STRICT QWEN BYPASS (qwen_latency_ms == 0.0)")
        print("="*70)

        en_talks = sorted(glob.glob("/mnt/models/English Talks/*.wav"))
        if not en_talks:
            raise FileNotFoundError("No English talks found in /mnt/models/English Talks/")

        test_files = en_talks[:3]
        file_results = []
        all_passed = True

        for idx, file_path in enumerate(test_files):
            talk_name = os.path.basename(file_path)
            print(f"\n[*] Testing File {idx+1}/{len(test_files)}: {talk_name[:50]}...")
            
            pcm_data = load_audio_slice(file_path, start_sec=20.0, duration_sec=16.0)
            telemetry = TelemetryCollector()
            pipeline = AudioPipeline(
                whisper_client=self.whisper,
                qwen_client=self.qwen,
                telemetry_collector=telemetry
            )

            chunk_size = 16000 # 0.5s chunks
            chunks_processed = 0
            file_passed = True
            latencies = []
            languages = []

            for offset in range(0, len(pcm_data), chunk_size):
                frame = pcm_data[offset:offset+chunk_size]
                res = await pipeline.process_chunk(frame)
                if res:
                    chunks_processed += 1
                    languages.append(res.language)
                    latencies.append(res.qwen_latency_ms)
                    
                    if res.is_english:
                        if res.qwen_latency_ms != 0.0:
                            print(f"  [FAIL] Chunk {chunks_processed}: Qwen latency was {res.qwen_latency_ms}ms (expected 0.0ms)")
                            file_passed = False
                            all_passed = False
                        else:
                            print(f"  [PASS] Chunk {chunks_processed}: Lang={res.language} | Qwen Latency={res.qwen_latency_ms}ms | Whisper={res.whisper_latency_ms:.1f}ms | ASR='{res.raw_text[:40]}...'")
                    else:
                        print(f"  [WARN] Chunk {chunks_processed}: Non-English detected: {res.language}")

            flush_res = await pipeline.flush()
            if flush_res and flush_res.is_english:
                if flush_res.qwen_latency_ms != 0.0:
                    file_passed = False
                    all_passed = False
                print(f"  [PASS] Flush Chunk: Lang={flush_res.language} | Qwen Latency={flush_res.qwen_latency_ms}ms")

            file_results.append({
                "file": talk_name,
                "chunks_processed": chunks_processed,
                "languages": languages,
                "qwen_latencies": latencies,
                "passed": file_passed
            })

        # Test 1B: Noisy English Speech (20dB, 10dB, 5dB SNR)
        print("\n[*] Testing Noisy English Speech under synthetic background noise...")
        noise_results = []
        base_pcm = load_audio_slice(test_files[0], start_sec=25.0, duration_sec=8.0)
        for snr in [20.0, 10.0, 5.0]:
            noisy_pcm = add_noise(base_pcm, snr_db=snr)
            pipeline = AudioPipeline(
                whisper_client=self.whisper,
                qwen_client=self.qwen
            )
            # Feed 4.0s
            res = await pipeline.process_chunk(noisy_pcm[:128000])
            if res:
                passed_noise = (res.is_english and res.qwen_latency_ms == 0.0)
                status_str = "PASS" if passed_noise else "FAIL"
                print(f"  [{status_str}] SNR {snr:2.0f}dB | Lang={res.language} | Qwen Latency={res.qwen_latency_ms}ms | ASR='{res.raw_text[:40]}...'")
                noise_results.append({"snr": snr, "lang": res.language, "qwen_latency_ms": res.qwen_latency_ms, "passed": passed_noise})
                if not passed_noise:
                    all_passed = False

        # Test 1C: Direct QwenClient unit bypass edge cases
        print("\n[*] Testing Direct QwenClient Language String Variations...")
        unit_cases = ["en", "EN", "English", "english", " en "]
        unit_passed = True
        for lang_str in unit_cases:
            t_res = await self.qwen.post_correct_and_translate("Hello world, this is a test.", source_language=lang_str)
            case_ok = (t_res.latency_ms == 0.0 and t_res.bypassed is True and t_res.english_translation == "Hello world, this is a test.")
            status_str = "PASS" if case_ok else "FAIL"
            print(f"  [{status_str}] Lang='{lang_str}' -> latency={t_res.latency_ms}ms, bypassed={t_res.bypassed}")
            if not case_ok:
                unit_passed = False
                all_passed = False

        outcome = {
            "all_passed": all_passed,
            "file_tests": file_results,
            "noise_tests": noise_results,
            "unit_tests_passed": unit_passed
        }
        self.results["challenge_1"] = outcome
        return outcome

    async def challenge_2_sliding_window_improvement(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(">>> CHALLENGE 2: SLIDING-WINDOW CORRECTION IMPROVEMENT VS NON-OVERLAPPING BASELINE")
        print("="*70)

        languages_to_test = [
            ("Spanish", "Spanish Talks/*.wav", "es", 20.0, 16.0),
            ("German", "German Talks/*.wav", "de", 25.0, 16.0),
            ("French", "French Talks/*.wav", "fr", 20.0, 16.0),
            ("English", "English Talks/*.wav", "en", 20.0, 16.0),
        ]

        comparison_results = []
        overall_wer_improvement = []

        for lang_name, pattern, lang_code, start_s, dur_s in languages_to_test:
            matches = sorted(glob.glob(f"/mnt/models/{pattern}"))
            if not matches:
                print(f"[!] No audio found for {lang_name}, skipping.")
                continue
            audio_file = matches[0]
            talk_name = os.path.basename(audio_file)
            print(f"\n[*] Evaluating {lang_name} Audio: {talk_name[:50]}...")
            pcm_data = load_audio_slice(audio_file, start_sec=start_s, duration_sec=dur_s)

            # Ground Truth Reference: Run full uninterrupted audio through Whisper
            full_wav = pack_pcm_to_wav(pcm_data, sample_rate=16000)
            full_res = await self.whisper.transcribe_wav(full_wav)
            reference_text = full_res.text.strip()
            print(f"  [REF Ground Truth] : \"{reference_text}\"")

            # Strategy A: Non-overlapping 2.0s chunks
            naive_chunks_text = []
            chunk_bytes = 32000 # 2.0 seconds @ 16kHz 16-bit
            for offset in range(0, len(pcm_data), chunk_bytes):
                sub_pcm = pcm_data[offset:offset+chunk_bytes]
                if len(sub_pcm) >= 16000: # at least 0.5s
                    sub_wav = pack_pcm_to_wav(sub_pcm, sample_rate=16000)
                    sub_res = await self.whisper.transcribe_wav(sub_wav)
                    if sub_res.text.strip():
                        naive_chunks_text.append(sub_res.text.strip())
            naive_full_text = " ".join(naive_chunks_text)
            print(f"  [Strategy A Naive] : \"{naive_full_text}\"")

            # Strategy B: Sliding Window 4.0s with 2.0s overlap + TextStitcher
            pipeline = AudioPipeline(
                whisper_client=self.whisper,
                qwen_client=self.qwen,
                window_sec=4.0,
                stride_sec=2.0
            )
            step_size = 16000 # 0.5s chunks
            total_repairs = 0
            for offset in range(0, len(pcm_data), step_size):
                frame = pcm_data[offset:offset+step_size]
                chunk_res = await pipeline.process_chunk(frame)
                if chunk_res:
                    total_repairs += chunk_res.repairs_detected
            flush_res = await pipeline.flush()
            if flush_res:
                total_repairs += flush_res.repairs_detected
            sliding_full_text = pipeline.stitcher.committed_text.strip()
            if not sliding_full_text and flush_res:
                sliding_full_text = flush_res.stitched_text.strip()
            print(f"  [Strategy B Slide] : \"{sliding_full_text}\"")

            # Metrics Computation
            wer_naive = compute_wer(reference_text, naive_full_text)
            cer_naive = compute_cer(reference_text, naive_full_text)

            wer_sliding = compute_wer(reference_text, sliding_full_text)
            cer_sliding = compute_cer(reference_text, sliding_full_text)

            wer_diff = wer_naive - wer_sliding
            cer_diff = cer_naive - cer_sliding

            print(f"  --> Naive WER   : {wer_naive*100:.2f}% | CER: {cer_naive*100:.2f}%")
            print(f"  --> Sliding WER : {wer_sliding*100:.2f}% | CER: {cer_sliding*100:.2f}%")
            print(f"  --> WER Delta   : {wer_diff*100:+.2f}% (Positive means Sliding is superior)")
            print(f"  --> CER Delta   : {cer_diff*100:+.2f}%")
            print(f"  --> Boundary Repairs Detected: {total_repairs}")

            is_improved = (wer_sliding <= wer_naive or cer_sliding <= cer_naive)
            comparison_results.append({
                "language": lang_name,
                "file": talk_name,
                "reference_text": reference_text,
                "naive_text": naive_full_text,
                "sliding_text": sliding_full_text,
                "wer_naive": wer_naive,
                "cer_naive": cer_naive,
                "wer_sliding": wer_sliding,
                "cer_sliding": cer_sliding,
                "wer_reduction": wer_diff,
                "cer_reduction": cer_diff,
                "repairs": total_repairs,
                "improved": is_improved
            })
            overall_wer_improvement.append(is_improved)

        # Synthetic Seam Stress Test
        print("\n[*] Stress-testing TextStitcher with adversarial synthetic boundary cases...")
        stitcher = TextStitcher(overlap_ratio=0.5)
        # Case 1: Word boundary repair
        stitcher.process_window("El presidente de la repu")
        c1, t1, s1, rep1 = stitcher.process_window("la republica anuncio hoy")
        print(f"  Boundary repair test: committed='{c1}', tail='{t1}', repairs={rep1}")
        
        # Case 2: Repetitive stutter deduplication
        stitcher.reset()
        stitcher.process_window("we need to to solve")
        c2, t2, s2, rep2 = stitcher.process_window("to solve this problem now")
        print(f"  Stutter dedup test  : committed='{c2}', full='{s2}', repairs={rep2}")

        outcome = {
            "comparison_results": comparison_results,
            "all_improved_or_equal": all(overall_wer_improvement),
            "total_repairs": sum(c["repairs"] for c in comparison_results)
        }
        self.results["challenge_2"] = outcome
        return outcome

    async def challenge_3_edge_cases(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(">>> CHALLENGE 3: ADVERSARIAL AUDIO EDGE CASES (0-Byte, Silence, Clipping, Starvation)")
        print("="*70)

        edge_tests = []
        all_passed = True

        # 3.1: 0-Byte Audio Ingestion
        print("\n[*] Test 3.1: 0-Byte Audio Ingestion & Empty Pipeline Flush")
        pipeline = AudioPipeline(whisper_client=self.whisper, qwen_client=self.qwen)
        r0 = await pipeline.process_chunk(b"")
        r_flush0 = await pipeline.flush()
        asr0 = await self.whisper.transcribe_wav(b"")
        qwen0 = await self.qwen.post_correct_and_translate("", "es")
        
        p31 = (r0 is None and r_flush0 is None and asr0.is_empty and qwen0.latency_ms == 0.0)
        status_str = "PASS" if p31 else "FAIL"
        print(f"  [{status_str}] 0-byte stream: process_chunk -> {r0}, flush -> {r_flush0}, whisper -> text='{asr0.text}', qwen -> '{qwen0.english_translation}'")
        edge_tests.append({"name": "0_byte_ingestion", "passed": p31})
        if not p31: all_passed = False

        # 3.2: Pure Silence (All 0x00 PCM)
        print("\n[*] Test 3.2: 4.0s of Pure Silence (128,000 bytes 0x00)")
        silence_pcm = b"\x00" * 128000
        pipeline.reset()
        t0 = time.perf_counter()
        r_silence = await pipeline.process_chunk(silence_pcm)
        lat_silence = (time.perf_counter() - t0) * 1000.0
        
        p32 = (r_silence is not None and r_silence.whisper_latency_ms < 5000.0 and len(r_silence.raw_text.strip()) == 0)
        status_str = "PASS" if p32 else "FAIL"
        print(f"  [{status_str}] Pure silence: text='{r_silence.raw_text if r_silence else 'None'}', latency={lat_silence:.1f}ms")
        edge_tests.append({"name": "pure_silence_4s", "passed": p32})
        if not p32: all_passed = False

        # 3.3: Extreme Amplitude Clipping & Full-Scale Square Wave
        print("\n[*] Test 3.3: Extreme Amplitude Clipping (Full-scale 0x7FFF / 0x8000 square wave)")
        half_period_samples = 160
        square_samples = []
        for i in range(64000):
            val = 32767 if (i // half_period_samples) % 2 == 0 else -32768
            square_samples.append(val)
        square_pcm = struct.pack(f"<{len(square_samples)}h", *square_samples)
        
        pipeline.reset()
        r_square = await pipeline.process_chunk(square_pcm)
        p33 = (r_square is not None and r_square.whisper_latency_ms < 5000.0)
        status_str = "PASS" if p33 else "FAIL"
        print(f"  [{status_str}] Extreme square wave: text='{r_square.raw_text[:40] if r_square else ''}', Whisper Latency={r_square.whisper_latency_ms if r_square else 0:.1f}ms")
        edge_tests.append({"name": "extreme_amplitude_clipping", "passed": p33})
        if not p33: all_passed = False

        # 3.4: Non-Even Odd Byte Lengths
        print("\n[*] Test 3.4: Non-Even Odd Byte Lengths (1, 3, 127999 bytes)")
        pipeline.reset()
        odd_passed = True
        try:
            await pipeline.process_chunk(b"\x12")
            await pipeline.process_chunk(b"\x34\x56\x78")
            await pipeline.process_chunk(b"\x00" * 127996)
            r_odd = await pipeline.process_chunk(b"\x00" * 32000)
            print("  [PASS] Odd byte slicing handled cleanly without unpack exception.")
        except Exception as e:
            print(f"  [FAIL] Odd byte length caused exception: {e}")
            odd_passed = False
            all_passed = False
        edge_tests.append({"name": "odd_byte_handling", "passed": odd_passed})

        # 3.5: Starvation & Jumbo Frame Overload
        print("\n[*] Test 3.5: Starvation (50x 10-byte chunks) & Jumbo Frame (2MB chunk)")
        pipeline.reset()
        for _ in range(50):
            await pipeline.process_chunk(b"\x00" * 10)
        jumbo_pcm = b"\x00" * 2000000
        r_jumbo = await pipeline.process_chunk(jumbo_pcm)
        p35 = (r_jumbo is not None)
        status_str = "PASS" if p35 else "FAIL"
        print(f"  [{status_str}] Starvation and 2MB jumbo frame handled cleanly.")
        edge_tests.append({"name": "starvation_and_jumbo_frame", "passed": p35})
        if not p35: all_passed = False

        # 3.6: Dynamic Mid-Stream Language Switching (Spanish -> English)
        print("\n[*] Test 3.6: Dynamic Language Switching (Spanish 4s -> English 4s)")
        sp_matches = sorted(glob.glob("/mnt/models/Spanish Talks/*.wav"))
        en_matches = sorted(glob.glob("/mnt/models/English Talks/*.wav"))
        if sp_matches and en_matches:
            sp_pcm = load_audio_slice(sp_matches[0], start_sec=20.0, duration_sec=4.0)
            en_pcm = load_audio_slice(en_matches[0], start_sec=20.0, duration_sec=4.0)
            
            pipeline.reset()
            r_sp = await pipeline.process_chunk(sp_pcm)
            r_en = await pipeline.process_chunk(en_pcm)
            
            sp_ok = (r_sp is not None and r_sp.language == "es" and r_sp.qwen_latency_ms > 0.0)
            en_ok = (r_en is not None and r_en.language == "en" and r_en.qwen_latency_ms == 0.0)
            p36 = sp_ok and en_ok
            status_str = "PASS" if p36 else "FAIL"
            print(f"  Chunk 1 (Spanish): Lang={r_sp.language if r_sp else ''} | Qwen Latency={r_sp.qwen_latency_ms if r_sp else 0:.1f}ms | OK={sp_ok}")
            print(f"  Chunk 2 (English): Lang={r_en.language if r_en else ''} | Qwen Latency={r_en.qwen_latency_ms if r_en else 0:.1f}ms | OK={en_ok}")
            print(f"  [{status_str}] Dynamic bilingual transition verified.")
            edge_tests.append({"name": "dynamic_language_switch", "passed": p36})
            if not p36: all_passed = False

        outcome = {
            "all_passed": all_passed,
            "edge_tests": edge_tests
        }
        self.results["challenge_3"] = outcome
        return outcome

    async def run_all(self):
        t_all_start = time.perf_counter()
        print("="*80)
        print("EMPIRICAL ADVERSARIAL CHALLENGER SUITE")
        print("="*80)

        c1 = await self.challenge_1_english_bypass()
        c2 = await self.challenge_2_sliding_window_improvement()
        c3 = await self.challenge_3_edge_cases()

        total_time = time.perf_counter() - t_all_start

        verdict = "APPROVE" if (c1["all_passed"] and c2["all_improved_or_equal"] and c3["all_passed"]) else "REJECT"

        final_summary = {
            "verdict": verdict,
            "total_execution_time_sec": total_time,
            "challenge_1_english_bypass": c1,
            "challenge_2_sliding_window": c2,
            "challenge_3_edge_cases": c3
        }

        print("\n" + "="*80)
        print(f"FINAL CHALLENGER VERDICT: {verdict}")
        print(f"Total Execution Time: {total_time:.2f}s")
        print("="*80)

        output_path = "/home/ubuntu/translation_kiosk/tests/adversarial_challenge_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_summary, f, indent=2)
        print(f"[*] Full Challenge Results saved to: {output_path}")

        await self.whisper.close()
        await self.qwen.close()
        return final_summary

if __name__ == "__main__":
    challenger = EmpiricalChallenger()
    summary = asyncio.run(challenger.run_all())
    sys.exit(0 if summary["verdict"] == "APPROVE" else 1)

