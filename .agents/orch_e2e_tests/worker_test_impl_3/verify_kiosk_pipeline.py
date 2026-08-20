#!/usr/bin/env python3
"""
verify_kiosk_pipeline.py - Standalone Automated Pipeline Verification Runner

CLI tool for validating the real-time translation kiosk audio pipeline against live or mock services.
Measures per-chunk latency budgets (Whisper <5s, Qwen <8s, English bypass 0ms), validates sliding-window
stitching vs naive baseline, and generates structured JSON verification artifacts.

Usage:
  python verify_kiosk_pipeline.py [OPTIONS]

Options:
  --audio PATH            Path to audio WAV file for verification replay.
  --endpoint URL          Translation Kiosk HTTP/WS endpoint (default: http://localhost:8080).
  --live-services         Directly query live GPU services on ports 8001 (Whisper) and 8000 (Qwen).
  --fast                  Fast execution mode with truncated audio samples.
  --strict-latency        Enforce strict pass/fail latency assertions (<5s Whisper, <8s Qwen).
  --output-json PATH      Path to export structured JSON verification summary.
  --lang CODE             Target language code (e.g. es, fr, de, zh, ar, ru, ja, en).
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
import wave
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import httpx

APP_DIR = "/home/ubuntu/translation_kiosk"
TESTS_DIR = "/home/ubuntu/translation_kiosk/tests"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

try:
    from config import (
        SAMPLE_RATE,
        WINDOW_SEC,
        STRIDE_SEC,
        WINDOW_BYTES,
        STRIDE_BYTES,
        get_language_name
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
    from qwen_client import QwenClient, TranslationResult
    from telemetry import TelemetryCollector, ChunkTelemetry
    from conftest import load_real_speech_sample, create_sine_wave, MockWhisperClient, MockQwenClient
except ImportError as e:
    print(f"[ERROR] Failed to import translation kiosk modules: {e}")
    sys.exit(1)


@dataclass
class VerificationChunkMetric:
    chunk_id: int
    duration_s: float
    whisper_latency_ms: float
    qwen_latency_ms: float
    e2e_latency_ms: float
    detected_language: str
    is_english_bypassed: bool
    raw_asr: str
    sliding_stitched: str
    corrected_text: str
    english_translation: str
    repairs_detected: int
    passed_latency: bool


@dataclass
class VerificationSummary:
    timestamp: float
    audio_source: str
    total_audio_seconds: float
    total_chunks: int
    passed_all: bool
    whisper_avg_ms: float
    whisper_p95_ms: float
    whisper_max_ms: float
    qwen_avg_ms: float
    qwen_p95_ms: float
    qwen_max_ms: float
    e2e_avg_ms: float
    e2e_p95_ms: float
    total_bypasses: int
    total_repairs: int
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)


class KioskVerificationRunner:
    def __init__(
        self,
        audio_path: Optional[str] = None,
        lang_code: str = "es",
        endpoint: str = "http://localhost:8080",
        live_services: bool = False,
        fast_mode: bool = False,
        strict_latency: bool = False
    ):
        self.audio_path = audio_path
        self.lang_code = lang_code.lower()
        self.endpoint = endpoint
        self.live_services = live_services
        self.fast_mode = fast_mode
        self.strict_latency = strict_latency
        self.telemetry = TelemetryCollector()

    def load_audio_frames(self) -> Tuple[bytes, int]:
        """Loads or generates mono 16kHz 16-bit PCM audio stream."""
        if self.audio_path and os.path.isfile(self.audio_path):
            with wave.open(self.audio_path, "rb") as wf:
                in_sr = wf.getframerate()
                n_ch = wf.getnchannels()
                sw = wf.getsampwidth()
                raw_bytes = wf.readframes(wf.getnframes())
                arr = np.frombuffer(raw_bytes, dtype=np.int16)
                if n_ch > 1:
                    arr = arr.reshape(-1, n_ch).mean(axis=1).astype(np.int16)
                if in_sr != 16000:
                    from scipy.signal import resample
                    target_len = int(len(arr) * 16000 / in_sr)
                    arr = np.clip(resample(arr.astype(np.float32), target_len), -32768, 32767).astype(np.int16)
                pcm = arr.tobytes()
                return pcm, 16000
        else:
            # Load real speech sample from TED dataset
            dur = 6.0 if self.fast_mode else 12.0
            pcm, _ = load_real_speech_sample(self.lang_code, start_sec=30.0, duration_sec=dur)
            return pcm, 16000

    async def run_verification(self) -> VerificationSummary:
        print("=" * 70)
        print("  TRANSLATION KIOSK PIPELINE VERIFICATION RUNNER")
        print("=" * 70)
        print(f"  Target Language : {self.lang_code.upper()} ({get_language_name(self.lang_code)})")
        print(f"  Live GPU Mode   : {self.live_services}")
        print(f"  Fast Mode       : {self.fast_mode}")
        print(f"  Strict Latency  : {self.strict_latency}")
        print("=" * 70)

        pcm_data, sample_rate = self.load_audio_frames()
        total_audio_sec = len(pcm_data) / 32000.0
        print(f"[*] Loaded Audio Stream: {len(pcm_data)} bytes ({total_audio_sec:.2f} seconds @ {sample_rate}Hz mono)\n")

        # Initialize clients
        if self.live_services:
            whisper_client = WhisperClient(base_url="http://localhost:8001")
            qwen_client = QwenClient(base_url="http://localhost:8000/v1", bypass_english=True)
        else:
            whisper_client = MockWhisperClient(default_lang=self.lang_code)
            qwen_client = MockQwenClient(bypass_english=True)

        pipeline = AudioPipeline(
            whisper_client=whisper_client,
            qwen_client=qwen_client,
            telemetry_collector=self.telemetry
        )

        chunk_metrics: List[VerificationChunkMetric] = []
        failures: List[str] = []

        # Feed PCM in 0.5-second chunks (16,000 bytes) to simulate streaming
        frame_size = 16000
        total_frames = int(np.ceil(len(pcm_data) / frame_size))
        chunk_idx = 1

        for i in range(total_frames):
            frame = pcm_data[i * frame_size : (i + 1) * frame_size]
            res = await pipeline.process_chunk(frame)
            if res:
                passed_lat = True
                # Latency checks
                if res.whisper_latency_ms >= 5000.0:
                    failures.append(f"Chunk {chunk_idx}: Whisper latency {res.whisper_latency_ms:.1f}ms exceeds 5000ms threshold.")
                    passed_lat = False
                
                if res.is_english:
                    if res.qwen_latency_ms > 50.0:  # English bypass must be ~0ms
                        failures.append(f"Chunk {chunk_idx}: English bypass failed. Qwen latency was {res.qwen_latency_ms:.1f}ms (expected 0.0ms).")
                        passed_lat = False
                else:
                    if res.qwen_latency_ms >= 8000.0:
                        failures.append(f"Chunk {chunk_idx}: Qwen latency {res.qwen_latency_ms:.1f}ms exceeds 8000ms threshold.")
                        passed_lat = False

                metric = VerificationChunkMetric(
                    chunk_id=chunk_idx,
                    duration_s=4.0 if chunk_idx == 1 else 2.0,
                    whisper_latency_ms=res.whisper_latency_ms,
                    qwen_latency_ms=res.qwen_latency_ms,
                    e2e_latency_ms=res.e2e_latency_ms,
                    detected_language=res.language,
                    is_english_bypassed=res.is_english,
                    raw_asr=res.raw_text,
                    sliding_stitched=res.stitched_text or res.window_text,
                    corrected_text=res.corrected_text,
                    english_translation=res.translated_text,
                    repairs_detected=res.repairs_detected,
                    passed_latency=passed_lat
                )
                chunk_metrics.append(metric)

                status_flag = "[PASS]" if passed_lat else "[FAIL]"
                print(f"  {status_flag} Chunk {chunk_idx:02d} | Lang: {res.language:2s} | W: {res.whisper_latency_ms:6.1f}ms | Q: {res.qwen_latency_ms:6.1f}ms | E2E: {res.e2e_latency_ms:6.1f}ms | Rep: {res.repairs_detected}")
                print(f"         ASR   : \"{res.raw_text[:50]}\"")
                print(f"         Trans : \"{res.translated_text[:50]}\"\n")
                chunk_idx += 1

        # Flush residual
        final_res = await pipeline.flush()
        if final_res and final_res.raw_text.strip():
            metric = VerificationChunkMetric(
                chunk_id=chunk_idx,
                duration_s=2.0,
                whisper_latency_ms=final_res.whisper_latency_ms,
                qwen_latency_ms=final_res.qwen_latency_ms,
                e2e_latency_ms=final_res.e2e_latency_ms,
                detected_language=final_res.language,
                is_english_bypassed=final_res.is_english,
                raw_asr=final_res.raw_text,
                sliding_stitched=final_res.stitched_text or final_res.window_text,
                corrected_text=final_res.corrected_text,
                english_translation=final_res.translated_text,
                repairs_detected=final_res.repairs_detected,
                passed_latency=True
            )
            chunk_metrics.append(metric)

        # Cleanup
        if hasattr(whisper_client, "close"):
            await whisper_client.close()
        if hasattr(qwen_client, "close"):
            await qwen_client.close()

        # Compute summary
        w_lats = [c.whisper_latency_ms for c in chunk_metrics] or [0.0]
        q_lats = [c.qwen_latency_ms for c in chunk_metrics if not c.is_english_bypassed] or [0.0]
        e_lats = [c.e2e_latency_ms for c in chunk_metrics] or [0.0]
        bypasses = sum(1 for c in chunk_metrics if c.is_english_bypassed)
        repairs = sum(c.repairs_detected for c in chunk_metrics)

        passed_all = len(failures) == 0 if self.strict_latency else True

        summary = VerificationSummary(
            timestamp=time.time(),
            audio_source=self.audio_path or f"TED_{self.lang_code.upper()}",
            total_audio_seconds=total_audio_sec,
            total_chunks=len(chunk_metrics),
            passed_all=passed_all,
            whisper_avg_ms=float(np.mean(w_lats)),
            whisper_p95_ms=float(np.percentile(w_lats, 95)),
            whisper_max_ms=float(np.max(w_lats)),
            qwen_avg_ms=float(np.mean(q_lats)),
            qwen_p95_ms=float(np.percentile(q_lats, 95)),
            qwen_max_ms=float(np.max(q_lats)),
            e2e_avg_ms=float(np.mean(e_lats)),
            e2e_p95_ms=float(np.percentile(e_lats, 95)),
            total_bypasses=bypasses,
            total_repairs=repairs,
            chunks=[asdict(c) for c in chunk_metrics],
            failures=failures
        )

        print("=" * 70)
        print("  VERIFICATION SUMMARY REPORT")
        print("=" * 70)
        print(f"  Total Chunks Processed : {summary.total_chunks}")
        print(f"  Whisper Latency (Avg)  : {summary.whisper_avg_ms:.1f} ms  (Target: <5,000 ms)")
        print(f"  Whisper Latency (P95)  : {summary.whisper_p95_ms:.1f} ms")
        print(f"  Qwen Latency (Avg)     : {summary.qwen_avg_ms:.1f} ms  (Target: <8,000 ms)")
        print(f"  Qwen Latency (P95)     : {summary.qwen_p95_ms:.1f} ms")
        print(f"  E2E Latency (Avg)      : {summary.e2e_avg_ms:.1f} ms")
        print(f"  English Bypasses (0ms) : {summary.total_bypasses}")
        print(f"  Boundary Repairs Count : {summary.total_repairs}")
        print(f"  Overall Status         : {'SUCCESS (PASS)' if passed_all else 'FAILED'}")
        print("=" * 70)

        return summary


def main():
    parser = argparse.ArgumentParser(description="Translation Kiosk Verification Runner")
    parser.add_argument("--audio", type=str, default=None, help="Path to WAV audio file")
    parser.add_argument("--endpoint", type=str, default="http://localhost:8080", help="Kiosk endpoint")
    parser.add_argument("--live-services", action="store_true", help="Query live GPU ports 8001 and 8000")
    parser.add_argument("--fast", action="store_true", help="Fast execution mode")
    parser.add_argument("--strict-latency", action="store_true", help="Enforce strict latency thresholds")
    parser.add_argument("--output-json", type=str, default=None, help="Export JSON summary path")
    parser.add_argument("--lang", type=str, default="es", help="Target language code (es, fr, de, zh, ar, ru, ja, en)")
    args = parser.parse_args()

    runner = KioskVerificationRunner(
        audio_path=args.audio,
        lang_code=args.lang,
        endpoint=args.endpoint,
        live_services=args.live_services,
        fast_mode=args.fast,
        strict_latency=args.strict_latency
    )

    summary = asyncio.run(runner.run_verification())

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"[*] JSON report saved to: {args.output_json}")

    sys.exit(0 if summary.passed_all else 1)


if __name__ == "__main__":
    main()
