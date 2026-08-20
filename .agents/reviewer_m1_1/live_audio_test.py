import sys
import os
import asyncio
import wave
import io

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from config import *
from telemetry import TelemetryCollector
from whisper_client import WhisperClient
from qwen_client import QwenClient
from audio_pipeline import AudioPipeline, pack_pcm_to_wav

async def test_live_audio_e2e():
    print("=== LIVE AUDIO E2E PIPELINE STRESS TEST ===")
    
    # Locate WAV files across different languages in /mnt/models
    categories = ['Spanish Talks', 'French Talks', 'German Talks', 'English Talks']
    test_files = []
    for cat in categories:
        cat_dir = os.path.join('/mnt/models', cat)
        if os.path.exists(cat_dir):
            wavs = [os.path.join(cat_dir, f) for f in os.listdir(cat_dir) if f.endswith('.wav')]
            if wavs:
                test_files.append((cat, wavs[0]))
                
    print(f"Found {len(test_files)} language sample files:")
    for cat, p in test_files:
        print(f" - {cat}: {os.path.basename(p)}")

    telemetry = TelemetryCollector()
    pipeline = AudioPipeline(
        whisper_client=WhisperClient(telemetry_collector=telemetry),
        qwen_client=QwenClient(telemetry_collector=telemetry),
        telemetry_collector=telemetry,
        window_sec=4.0,
        stride_sec=2.0
    )

    for cat, filepath in test_files:
        print(f"\n--- Testing Category: {cat} ---")
        pipeline.reset()
        
        # Read 10 seconds of audio, convert to 16kHz mono if needed using ffmpeg/wave
        import subprocess
        # Convert 10s clip to 16kHz mono 16-bit raw PCM using ffmpeg
        cmd = [
            "ffmpeg", "-y", "-ss", "30", "-t", "10", "-i", filepath,
            "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pcm_10s = proc.stdout
        print(f"Extracted 10s PCM: {len(pcm_10s)} bytes ({len(pcm_10s)/32000:.1f}s)")
        
        # Stream in 100ms chunks (3200 bytes per chunk)
        chunk_size = 3200
        results = []
        for offset in range(0, len(pcm_10s), chunk_size):
            chunk = pcm_10s[offset:offset+chunk_size]
            res = await pipeline.process_chunk(chunk)
            if res:
                results.append(res)
                print(f"  Window {len(results)}: lang=[{res.language}] ({res.language_name})")
                print(f"    Raw STT:      {res.raw_text}")
                print(f"    Stitched:     {res.stitched_text}")
                print(f"    Corrected:    {res.corrected_text}")
                print(f"    English:      {res.translated_text}")
                print(f"    Latencies:    Whisper={res.whisper_latency_ms:.1f}ms, Qwen={res.qwen_latency_ms:.1f}ms, E2E={res.e2e_latency_ms:.1f}ms")
                print(f"    Bypassed:     {res.is_english}")
                
        # Flush residual
        flush_res = await pipeline.flush()
        if flush_res:
            print(f"  Flush Result:")
            print(f"    Final Stitched:  {flush_res.stitched_text}")
            print(f"    Final English:   {flush_res.translated_text}")
            print(f"    Final Latencies: Whisper={flush_res.whisper_latency_ms:.1f}ms, Qwen={flush_res.qwen_latency_ms:.1f}ms")

    # Print summary telemetry
    stats = telemetry.get_summary_stats()
    print("\n=== AGGREGATE TELEMETRY METRICS ===")
    print(f"Total chunks processed: {stats['total_chunks_processed']}")
    print(f"Total audio seconds:    {stats['total_audio_seconds']}")
    print(f"Bypass rate:            {stats['bypass_rate_pct']}%")
    print(f"Whisper Latency (p50/p90/max): {stats['whisper_latency']['p50']}ms / {stats['whisper_latency']['p90']}ms / {stats['whisper_latency']['max']}ms")
    print(f"Qwen Latency (p50/p90/max):    {stats['qwen_latency']['p50']}ms / {stats['qwen_latency']['p90']}ms / {stats['qwen_latency']['max']}ms")
    print(f"E2E Latency (p50/p90/max):     {stats['e2e_latency']['p50']}ms / {stats['e2e_latency']['p90']}ms / {stats['e2e_latency']['max']}ms")
    print(f"Errors: {stats['errors']}")

    await pipeline.whisper_client.close()
    await pipeline.qwen_client.close()
    print("\n>>> LIVE AUDIO E2E STRESS TEST COMPLETE <<<")

if __name__ == '__main__':
    asyncio.run(test_live_audio_e2e())
