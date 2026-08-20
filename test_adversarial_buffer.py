"""
Adversarial Empirical Stress Suite for AudioRollingBuffer and pack_pcm_to_wav
Milestone 1 — Core Audio Pipeline & API Integrations
Agent: challenger_m1_1
"""
import io
import math
import os
import random
import struct
import sys
import time
import wave
import asyncio
import gc
import tracemalloc
import pytest

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from audio_pipeline import AudioRollingBuffer, pack_pcm_to_wav, create_wav_bytes
from config import SAMPLE_RATE, BYTES_PER_SAMPLE, CHANNELS, WINDOW_SEC, STRIDE_SEC


# ============================================================================
# 1. Chunk Size Jitter & Bit-Exact Reconstruction
# ============================================================================
@pytest.mark.asyncio
async def test_chunk_jitter_sample_integrity():
    """
    Streams synthetic audio in random chunk sizes (1 byte to 10,000 bytes),
    including odd-length chunks, and validates 100% bit-exact sample reconstruction.
    """
    sample_rate = 16000
    total_seconds = 20.0  # 320,000 samples = 640,000 bytes = 9 windows + flush
    total_samples = int(total_seconds * sample_rate)
    
    # Generate deterministic ground truth PCM: 16-bit triangle/counter waveform
    raw_samples = [(i * 7) % 32767 - 16384 for i in range(total_samples)]
    ground_truth_pcm = struct.pack(f'<{total_samples}h', *raw_samples)
    total_pcm_bytes = len(ground_truth_pcm)
    assert total_pcm_bytes == total_samples * 2

    buffer = AudioRollingBuffer(sample_rate=sample_rate)
    
    # Partition ground truth into random chunks from 1 to 10,000 bytes
    random.seed(42)
    chunks = []
    offset = 0
    while offset < total_pcm_bytes:
        chunk_size = random.choice([1, 2, 3, 7, 15, 127, 512, 1000, 3333, 7777, 10000, random.randint(1, 10000)])
        chunk = ground_truth_pcm[offset:offset + chunk_size]
        chunks.append(chunk)
        offset += len(chunk)

    # Stream chunks into buffer and collect sliced windows
    sliced_windows = []
    for chunk in chunks:
        await buffer.append_pcm(chunk)
        while await buffer.has_window():
            slice_res = await buffer.slice_next_window()
            if slice_res:
                sliced_windows.append(slice_res)

    flush_res = await buffer.flush()
    if flush_res:
        sliced_windows.append(flush_res)

    expected_regular_windows = 9
    assert len(sliced_windows) >= expected_regular_windows, f"Expected >= {expected_regular_windows} windows, got {len(sliced_windows)}"

    # Sample-level bit-exact verification for all regular windows
    for win_pcm, win_idx, start_sec in sliced_windows[:expected_regular_windows]:
        assert len(win_pcm) == 128000, f"Window {win_idx} length {len(win_pcm)} != 128000"
        expected_start_sample = win_idx * int(2.0 * sample_rate)
        expected_end_sample = expected_start_sample + int(4.0 * sample_rate)
        
        win_samples = struct.unpack(f'<{len(win_pcm)//2}h', win_pcm)
        gt_slice = raw_samples[expected_start_sample:expected_end_sample]
        assert list(win_samples) == gt_slice, f"Sample mismatch in window {win_idx}"

    # Verify flush window residual and zero-padding
    assert flush_res is not None
    flush_pcm, flush_idx, flush_start = flush_res
    assert len(flush_pcm) == 128000
    flush_samples = struct.unpack(f'<{len(flush_pcm)//2}h', flush_pcm)
    last_gt_slice = raw_samples[flush_idx * int(2.0 * sample_rate):]
    padding_samples = flush_samples[len(last_gt_slice):]
    
    assert list(flush_samples[:len(last_gt_slice)]) == last_gt_slice, "Flush residual sample mismatch"
    assert all(s == 0 for s in padding_samples), "Flush padding non-zero"


@pytest.mark.asyncio
async def test_odd_byte_chunk_streaming():
    """
    Stress test with strictly odd-sized chunks (1, 3, 5, 7, 9 bytes) to verify
    proper handling of sub-sample byte boundary alignment.
    """
    buffer = AudioRollingBuffer()
    raw_data = b'\x12\x34' * 80000  # 160,000 bytes = 80,000 samples
    
    # Split into 3-byte chunks
    chunks = [raw_data[i:i+3] for i in range(0, len(raw_data), 3)]
    for c in chunks:
        await buffer.append_pcm(c)
        
    assert await buffer.has_window()
    slice_data = await buffer.slice_next_window()
    assert slice_data is not None
    win_pcm, win_idx, start_sec = slice_data
    assert len(win_pcm) == 128000
    assert win_pcm == raw_data[:128000]


# ============================================================================
# 2. Rapid Concurrent Appends & Slices (Async Safety Stress)
# ============================================================================
@pytest.mark.asyncio
async def test_rapid_concurrent_appends_and_slices():
    """
    Tests rapid concurrent async appends from 20 coroutines while 10 consumer
    coroutines concurrently slice windows and poll metrics.
    """
    buffer = AudioRollingBuffer()
    producers_count = 20
    chunks_per_producer = 100
    chunk_size = 640  # 20ms @ 16kHz 16-bit
    
    total_expected_bytes = producers_count * chunks_per_producer * chunk_size
    producers_done = False
    slices_collected = []
    metrics_collected = []

    async def producer(p_id: int):
        for i in range(chunks_per_producer):
            chunk = struct.pack('<h', p_id) * (chunk_size // 2)
            await buffer.append_pcm(chunk)
            if i % 10 == 0:
                await asyncio.sleep(0.0001)

    async def consumer(c_id: int):
        while not producers_done or await buffer.has_window():
            if await buffer.has_window():
                res = await buffer.slice_next_window()
                if res:
                    slices_collected.append(res)
            metrics = await buffer.get_buffer_metrics()
            metrics_collected.append(metrics)
            await asyncio.sleep(0.0002)

    producer_tasks = [asyncio.create_task(producer(i)) for i in range(producers_count)]
    consumer_tasks = [asyncio.create_task(consumer(i)) for i in range(10)]

    await asyncio.gather(*producer_tasks)
    producers_done = True
    await asyncio.gather(*consumer_tasks)

    flush_res = await buffer.flush()
    if flush_res:
        slices_collected.append(flush_res)

    final_metrics = await buffer.get_buffer_metrics()
    total_received = final_metrics["total_received_bytes"]

    assert total_received == total_expected_bytes, f"Expected {total_expected_bytes} bytes, got {total_received}"
    assert len(slices_collected) > 0, "No slices collected"
    assert len(metrics_collected) > 0, "No metrics snapshots collected"

    window_indices = [s[1] for s in slices_collected]
    assert window_indices == sorted(window_indices), "Window indices out of order"
    assert len(window_indices) == len(set(window_indices)), "Duplicate window indices observed"


# ============================================================================
# 3. WAV Header Byte Verification via Python wave Module
# ============================================================================
def test_wav_header_byte_verification_across_sample_sizes():
    """
    Exhaustive WAV header validation with standard wave module across
    sample sizes from 0 bytes to 5 MB.
    """
    test_sample_counts = [0, 1, 2, 22, 800, 16000, 64000, 500000, 2500000]

    for num_samples in test_sample_counts:
        pcm = os.urandom(num_samples * 2)
        wav_bytes = pack_pcm_to_wav(pcm, sample_rate=16000, channels=1, bits_per_sample=16)

        assert len(wav_bytes) == 44 + len(pcm), f"Header size mismatch for {num_samples} samples"

        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == num_samples
            read_pcm = wf.readframes(num_samples)
            assert read_pcm == pcm


def test_wav_header_multi_format_compliance():
    """
    Validates WAV header creation across standard sample rates, mono/stereo,
    and 8-bit/16-bit sample depths.
    """
    test_configs = [
        (8000, 1, 16),
        (11025, 1, 16),
        (16000, 1, 16),
        (22050, 1, 16),
        (44100, 1, 16),
        (48000, 1, 16),
        (96000, 1, 16),
        (16000, 2, 16),
        (44100, 2, 16),
        (16000, 1, 8),
    ]

    for rate, chans, bits in test_configs:
        bytes_per_sample = bits // 8
        frame_size = chans * bytes_per_sample
        frames = 1000
        pcm = os.urandom(frames * frame_size)
        wav_bytes = pack_pcm_to_wav(pcm, sample_rate=rate, channels=chans, bits_per_sample=bits)

        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            assert wf.getnchannels() == chans
            assert wf.getframerate() == rate
            assert wf.getsampwidth() == bytes_per_sample
            assert wf.getnframes() == frames
            assert wf.readframes(frames) == pcm


def test_wav_packaging_latency_microbenchmark():
    """
    Microbenchmark verifying that WAV packing takes < 10 microseconds per 128KB window.
    """
    iterations = 10000
    test_pcm = b'\x00\x01' * 64000
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = pack_pcm_to_wav(test_pcm)
    elapsed = time.perf_counter() - t0
    avg_latency_us = (elapsed / iterations) * 1_000_000
    assert avg_latency_us < 10.0, f"Average packaging latency {avg_latency_us:.3f} µs exceeded 10 µs"


# ============================================================================
# 4. Long-Duration Audio Stream Simulation (Memory & Drift)
# ============================================================================
@pytest.mark.asyncio
async def test_long_duration_stream_simulation_1000_windows():
    """
    Simulates 1,000 consecutive windows (2,000 seconds = ~33.3 minutes of
    streaming audio) to detect memory leaks, unbounded buffer growth, or sample drift.
    """
    tracemalloc.start()
    gc.collect()

    buffer = AudioRollingBuffer()
    target_windows = 1000
    chunk_samples = 800  # 50ms chunk @ 16kHz
    chunk_bytes = chunk_samples * 2
    chunk_data = b'\x12\x34' * chunk_samples

    total_windows_sliced = 0
    start_times = []
    max_observed_buffer_len = 0
    drift_errors = 0

    snap_start = tracemalloc.take_snapshot()

    while total_windows_sliced < target_windows:
        await buffer.append_pcm(chunk_data)
        
        buf_len = len(buffer._buffer)
        if buf_len > max_observed_buffer_len:
            max_observed_buffer_len = buf_len
            
        while await buffer.has_window() and total_windows_sliced < target_windows:
            slice_res = await buffer.slice_next_window()
            if slice_res:
                win_pcm, win_idx, start_sec = slice_res
                
                if win_idx != total_windows_sliced:
                    drift_errors += 1
                
                expected_sec = win_idx * 2.0
                if not math.isclose(start_sec, expected_sec, rel_tol=1e-9, abs_tol=1e-9):
                    drift_errors += 1
                    
                start_times.append(start_sec)
                total_windows_sliced += 1

    gc.collect()
    snap_end = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snap_end.compare_to(snap_start, 'lineno')
    total_memory_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

    assert total_windows_sliced == 1000, f"Expected 1000 windows, got {total_windows_sliced}"
    assert drift_errors == 0, f"Observed {drift_errors} index/timestamp drift errors"
    assert max_observed_buffer_len <= (128000 + chunk_bytes * 2), f"Buffer unbounded: {max_observed_buffer_len}B"
    assert abs(total_memory_diff_kb) < 500.0, f"Memory leak detected: {total_memory_diff_kb:+.2f} KB"


# ============================================================================
# 5. Boundary & Flush State Machine Adversarial Testing
# ============================================================================
@pytest.mark.asyncio
async def test_flush_boundaries_and_zero_padding():
    """
    Tests exact boundary conditions for flush(): empty buffer, below min_flush,
    exactly min_flush, and larger residuals.
    """
    # 1. Empty buffer flush
    b1 = AudioRollingBuffer()
    assert await b1.flush() is None
    assert len(b1._buffer) == 0

    # 2. Buffer below min_flush_bytes (< 16,000 bytes)
    b2 = AudioRollingBuffer()
    await b2.append_pcm(b'\x01\x02' * (15999 // 2))
    assert await b2.flush() is None
    assert len(b2._buffer) == 0

    # 3. Buffer exactly at min_flush_bytes (16,000 bytes = 0.5s)
    b3 = AudioRollingBuffer()
    sample_16k = b'\xaa\xbb' * 8000
    await b3.append_pcm(sample_16k)
    f3 = await b3.flush()
    assert f3 is not None
    pcm3, idx3, start3 = f3
    assert len(pcm3) == 128000
    assert pcm3[:16000] == sample_16k
    assert pcm3[16000:] == b'\x00' * 112000
    assert start3 == 0.0
    assert idx3 == 0
    assert len(b3._buffer) == 0


@pytest.mark.asyncio
async def test_multi_stride_buffer_drain():
    """
    Tests draining a buffer that accumulated multiple strides (e.g. 300,000 bytes).
    """
    b = AudioRollingBuffer()
    await b.append_pcm(b'\x55\x66' * 150000)  # 300,000 bytes
    
    s1 = await b.slice_next_window()
    assert s1 is not None and s1[1] == 0
    
    s2 = await b.slice_next_window()
    assert s2 is not None and s2[1] == 1
    
    s3 = await b.slice_next_window()
    assert s3 is not None and s3[1] == 2
    
    # Remaining: 300,000 - 3*64,000 = 108,000 bytes (< 128,000, >= 16,000)
    assert not await b.has_window()
    f = await b.flush()
    assert f is not None and f[1] == 3 and len(f[0]) == 128000
    assert len(b._buffer) == 0


@pytest.mark.asyncio
async def test_buffer_reset_recovery():
    """
    Tests buffer reset restores clean initial state after partial slicing.
    """
    b = AudioRollingBuffer()
    await b.append_pcm(b'\x11\x22' * 40000)
    _ = await b.slice_next_window()
    b.reset()
    m = await b.get_buffer_metrics()
    assert m["buffered_bytes"] == 0
    assert m["total_received_bytes"] == 0
    assert m["window_index"] == 0
    assert len(b._buffer) == 0


def test_synchronous_helper_methods():
    """
    Tests synchronous helper methods (add_pcm, has_full_window, get_current_window, advance_stride).
    """
    b = AudioRollingBuffer()
    b.add_pcm(b'\x99' * 130000)
    assert b.has_full_window()
    cur_win = b.get_current_window()
    assert len(cur_win) == 128000
    b.advance_stride()
    assert len(b._buffer) == 130000 - 64000


@pytest.mark.asyncio
async def test_slice_naive_chunk_baseline():
    """
    Tests slice_naive_chunk extracts non-overlapping 2.0s chunks for comparative baseline.
    """
    b = AudioRollingBuffer()
    await b.append_pcm(b'\x44\x55' * 32000)  # 64,000 bytes = 2.0s
    naive = await b.slice_naive_chunk()
    assert naive is not None
    assert len(naive) == 64000
    assert naive == b'\x44\x55' * 32000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
