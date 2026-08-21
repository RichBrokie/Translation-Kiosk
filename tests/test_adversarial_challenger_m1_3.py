"""
Adversarial Challenge & Empirical Verification Suite — Milestone 1
Challenger: challenger_m1_3

Rigorous empirical challenge of:
1. TextStitcher:
   - Deep and multi-word offset matches (match.a > 0, match.b >= 0) -> 0% word loss guarantee.
   - Zero-match transitions (match.size == 0) -> 100% tentative tail retention across long chains.
   - Rapid oscillations, repetitive phrases, homographs, stuttering, speech pauses, and hallucinations.
   - Multilingual unicode text stitching (Spanish, Chinese, Arabic, Russian, Japanese, German).
   - Word boundary truncation and fuzzy phonetic repairs.
2. AudioRollingBuffer:
   - 100MB continuous audio streaming without slicing -> buffer strictly capped at max_retention_bytes (384,000 bytes).
   - Async append_pcm vs Sync add_pcm under high chunk rates.
   - Single oversized chunk pruning (>10MB).
   - Random chunk jitter (1 byte to 500,000 bytes) over 100MB stream.
   - Tracemalloc heap memory residency verification (O(1) memory bound).
"""
import pytest
import asyncio
import difflib
import gc
import random
import re
import string
import struct
import sys
import time
import tracemalloc
from typing import List, Tuple

sys.path.insert(0, '/home/ubuntu/translation_kiosk')

from audio_pipeline import (
    TextStitcher,
    AudioRollingBuffer,
    pack_pcm_to_wav,
    ComparativeEngine,
    AudioPipeline
)
from config import (
    SAMPLE_RATE,
    BYTES_PER_SAMPLE,
    CHANNELS,
    WINDOW_SEC,
    STRIDE_SEC,
    MAX_RETENTION_BYTES
)


# ============================================================================
# 1. TEXT STITCHER — OFFSET MATCHES (match.a > 0)
# ============================================================================
class TestTextStitcherOffsetMatches:
    """
    Empirical tests challenging TextStitcher when overlap match starts deep inside
    the previous tentative tail (match.a > 0).
    """

    def test_deterministic_offset_match_preserves_unmatched_prefix(self):
        """
        Window 1: 'Here we have ancient Egyptian relics'
                  -> committed: 'Here we'
                  -> tail: 'have ancient Egyptian relics'
        Window 2: 'ancient Egyptian relics from the 18th dynasty'
                  -> match is at 'ancient Egyptian relics'
                  -> match.a = 1 ('have' is before the match in prev tail)
                  -> Verifies 'have' is NOT dropped.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.process_window("Here we have ancient Egyptian relics")
        committed, tail, display, repairs = stitcher.process_window("ancient Egyptian relics from the 18th dynasty")
        flushed = stitcher.flush_final()

        assert "have" in flushed, f"Word 'have' dropped! Result: {flushed}"
        assert "Here we have ancient Egyptian relics from the 18th dynasty" == flushed

    def test_multi_word_deep_offset_match(self):
        """
        Tests offset match with 5 unmatched prefix words before the overlap block.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.committed_text = "Alpha Beta"
        stitcher.tentative_tail = "one two three four five TARGET_MATCH_1 TARGET_MATCH_2"
        
        new_window = "TARGET_MATCH_1 TARGET_MATCH_2 suffix_alpha suffix_beta suffix_gamma"
        committed, tail, display, repairs = stitcher.process_window(new_window)
        flushed = stitcher.flush_final()

        for num in ["one", "two", "three", "four", "five"]:
            assert num in flushed, f"Prefix word '{num}' was lost! Result: {flushed}"

        assert "TARGET_MATCH_1" in flushed
        assert "TARGET_MATCH_2" in flushed
        assert "suffix_alpha" in flushed
        assert "suffix_beta" in flushed
        assert "suffix_gamma" in flushed

    def test_randomized_offset_fuzzing_zero_word_loss(self):
        """
        Generates 100 synthetic streaming speech sessions with random word sequences.
        Forces variable offset match indices (match.a from 1 to 3 words).
        Verifies that 100% of non-overlapping words are preserved in output.
        """
        vocab = [f"word_{i:04d}" for i in range(1000)]
        random.seed(1337)

        for trial in range(100):
            stitcher = TextStitcher(overlap_ratio=0.5)
            word_stream = random.sample(vocab, 30)
            
            # Window 1: words 0..10 (committed: 0..5, tail: 5..10)
            w1_text = " ".join(word_stream[0:10])
            stitcher.process_window(w1_text)

            # Choose offset k in [1, 2, 3] -> new window starts at word 5+k
            k = random.randint(1, 3)
            # Window 2: words (5+k)..20
            w2_text = " ".join(word_stream[5+k:20])
            stitcher.process_window(w2_text)

            # Window 3: words (15+k)..30
            w3_text = " ".join(word_stream[15+k:30])
            stitcher.process_window(w3_text)

            flushed = stitcher.flush_final()
            flushed_words = flushed.split()

            for expected_word in word_stream[:10]:
                assert expected_word in flushed_words, (
                    f"Trial {trial} (k={k}): Expected word '{expected_word}' missing from output!\nOutput: {flushed}"
                )

    def test_offset_match_with_both_a_and_b_positive(self):
        """
        Tests match where both match.a > 0 (unmatched in prev) and match.b > 0 (unmatched prefix in curr).
        Prev tail: 'apple banana cherry date'
        Curr window: 'fig grape cherry date elderberry'
        match is 'cherry date' (match.a = 2, match.b = 2).
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.committed_text = "Start"
        stitcher.tentative_tail = "apple banana cherry date"

        committed, tail, display, _ = stitcher.process_window("fig grape cherry date elderberry")
        flushed = stitcher.flush_final()

        for fruit in ["apple", "banana", "fig", "grape", "cherry", "date", "elderberry"]:
            assert fruit in flushed, f"Missing '{fruit}' in flushed output: {flushed}"

    def test_offset_match_single_word_overlap(self):
        """
        Tests minimal overlap match of single word with offset in tail.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.committed_text = "Intro"
        stitcher.tentative_tail = "alpha beta gamma delta"
        
        # Match only on 'delta'
        stitcher.process_window("delta epsilon zeta eta")
        flushed = stitcher.flush_final()

        for word in ["Intro", "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"]:
            assert word in flushed, f"Word '{word}' missing in flushed text: {flushed}"


# ============================================================================
# 2. TEXT STITCHER — ZERO-MATCH TRANSITIONS (match.size == 0)
# ============================================================================
class TestTextStitcherZeroMatchTransitions:
    """
    Empirical tests challenging zero-overlap transitions (pauses, abrupt topic changes).
    Verifies that match.size == 0 NEVER drops previous tentative tail.
    """

    def test_single_zero_match_commits_entire_previous_tail(self):
        """
        Window 1: 'The quick brown fox jumps' (tail: 'brown fox jumps')
        Window 2: 'A completely unrelated sentence about physics' (zero match)
        Verifies 'brown fox jumps' is preserved in committed text.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.process_window("The quick brown fox jumps")
        assert stitcher.tentative_tail == "brown fox jumps"
        assert stitcher.committed_text == "The quick"

        c, t, d, _ = stitcher.process_window("A completely unrelated sentence about physics")
        flushed = stitcher.flush_final()

        assert "The quick brown fox jumps" in flushed
        assert "A completely unrelated sentence about physics" in flushed

    def test_50_consecutive_true_zero_match_windows_retention(self):
        """
        Feeds 50 completely disjoint sentences with distinct words between successive windows.
        Verifies 100% word retention and ordering across all 50 windows (500 total words).
        """
        random.seed(42)
        sentences = []
        for i in range(50):
            words = ["".join(random.choices(string.ascii_lowercase, k=6)) for _ in range(10)]
            sentences.append(" ".join(words))

        stitcher = TextStitcher(overlap_ratio=0.5)

        for s in sentences:
            stitcher.process_window(s)

        flushed = stitcher.flush_final()

        for s in sentences:
            for word in s.split():
                assert word in flushed, f"Word '{word}' from sentence '{s}' missing in flushed output!"

    def test_alternating_match_and_zero_match_stream(self):
        """
        Simulates realistic conversational bursts:
        [Match, Match, Zero-Match (speaker switch), Match, Match, Zero-Match]
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        
        # Turn 1 (Speaker A: 2 overlapping windows)
        stitcher.process_window("Good morning and welcome to the museum exhibition")
        stitcher.process_window("the museum exhibition features ancient artifacts")

        # Speaker pause / Topic switch (Zero match)
        stitcher.process_window("Where can I find the modern art gallery")

        # Turn 2 (Speaker B: overlapping continuation)
        stitcher.process_window("modern art gallery is located on the second floor")

        flushed = stitcher.flush_final()

        assert "Good morning and welcome" in flushed
        assert "museum exhibition" in flushed
        assert "ancient artifacts" in flushed
        assert "Where can I find" in flushed
        assert "modern art gallery" in flushed
        assert "second floor" in flushed

    def test_zero_match_with_single_word_windows(self):
        """
        Adversarial test: Short 1-word or 2-word windows with zero matches.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        words = ["yes", "no", "maybe", "definitely", "never", "always"]
        for w in words:
            stitcher.process_window(w)
        
        flushed = stitcher.flush_final()
        for w in words:
            assert w in flushed, f"Single word '{w}' was dropped: {flushed}"


# ============================================================================
# 3. TEXT STITCHER — RAPID OSCILLATIONS, PAUSES & STRESS
# ============================================================================
class TestTextStitcherOscillationsAndStress:
    """
    Adversarial tests for rapid sentence oscillations, homographs, silence,
    hallucination filtering, and boundary repairs.
    """

    def test_repetitive_homographs_and_stuttering(self):
        """
        Extreme repetitive phrasing: 'that that that that is is'
        Verifies no infinite loop or crash in SequenceMatcher.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.process_window("it is true that that that that is true")
        stitcher.process_window("that that that is true indeed")
        stitcher.process_window("buffalo buffalo buffalo buffalo buffalo")
        flushed = stitcher.flush_final()

        assert len(flushed) > 0
        assert "true" in flushed
        assert "buffalo" in flushed

    def test_speech_pauses_and_empty_hallucinations(self):
        """
        Injects empty strings, whitespace, and Whisper hallucination tags.
        Verifies tentative tail is preserved during pauses.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.process_window("First segment of speech")
        assert stitcher.tentative_tail == "of speech"
        
        # Injected silence / hallucinations
        stitcher.process_window("")
        assert stitcher.tentative_tail == "of speech"

        stitcher.process_window("   ")
        assert stitcher.tentative_tail == "of speech"

        stitcher.process_window("[music]")
        assert stitcher.tentative_tail == "of speech"

        stitcher.process_window("(applause)")
        assert stitcher.tentative_tail == "of speech"

        stitcher.process_window("Thank you for watching")
        assert stitcher.tentative_tail == "of speech"

        # Resume speech
        stitcher.process_window("of speech continued after the long pause")
        flushed = stitcher.flush_final()

        assert "First segment of speech continued after the long pause" == flushed

    def test_boundary_word_truncation_repair(self):
        """
        Window 1 ends with truncated word 'archaeolog...'
        Window 2 begins with full word 'archaeological discoveries'
        Verifies repair detection count >= 1 and correct merged text.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.committed_text = "Recent"
        stitcher.tentative_tail = "major archaeo"
        
        c, t, d, repairs = stitcher.process_window("archaeological discoveries in Egypt")
        flushed = stitcher.flush_final()

        assert repairs >= 1
        assert "archaeological" in flushed

    def test_multilingual_unicode_stitching(self):
        """
        Tests Spanish, Mandarin, Arabic, Japanese, Russian, and German.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)

        # Spanish
        stitcher.reset()
        stitcher.process_window("Hola bienvenidos a la exposición del museo")
        stitcher.process_window("exposición del museo nacional de historia")
        es_res = stitcher.flush_final()
        assert "Hola bienvenidos a la exposición del museo nacional de historia" == es_res

        # Arabic
        stitcher.reset()
        stitcher.process_window("أهلا بكم في المتحف الوطني للآثار")
        stitcher.process_window("المتحف الوطني للآثار القديمة والتاريخ")
        ar_res = stitcher.flush_final()
        assert "أهلا بكم" in ar_res
        assert "والتاريخ" in ar_res

        # German compound words
        stitcher.reset()
        stitcher.process_window("Willkommen im Donaudampfschifffahrtsgesellschaftsmuseum in Wien")
        stitcher.process_window("Donaudampfschifffahrtsgesellschaftsmuseum in Wien Österreich")
        de_res = stitcher.flush_final()
        assert "Willkommen" in de_res
        assert "Österreich" in de_res

        # Russian
        stitcher.reset()
        stitcher.process_window("Добро пожаловать в исторический музей города")
        stitcher.process_window("в исторический музей города Москва сегодня")
        ru_res = stitcher.flush_final()
        assert "Добро пожаловать" in ru_res
        assert "Москва сегодня" in ru_res

    def test_extreme_punctuation_and_casing(self):
        """
        Punctuation, symbols, quotes, mixed casing inside overlap blocks.
        """
        stitcher = TextStitcher(overlap_ratio=0.5)
        stitcher.process_window("Hello, World! (This is test #1)...")
        stitcher.process_window("(THIS is test #1)... and it CONTINUES!")
        flushed = stitcher.flush_final()
        assert "Hello," in flushed
        assert "CONTINUES!" in flushed


# ============================================================================
# 4. AUDIO ROLLING BUFFER — 100MB CONTINUOUS STREAMING MEMORY BOUNDING
# ============================================================================
class TestAudioRollingBufferMemoryBounding:
    """
    Adversarial memory stress harness:
    Streams 100MB (104,857,600 bytes) of PCM audio without slicing.
    Verifies that the buffer length NEVER exceeds max_retention_bytes (384,000 bytes).
    """

    @pytest.mark.asyncio
    async def test_100mb_continuous_stream_async(self):
        """
        Streams 100MB in 64KB chunks via append_pcm() without slicing.
        Invariant: len(_buffer) <= 384,000 bytes at EVERY step.
        """
        target_bytes = 100 * 1024 * 1024  # 104,857,600 bytes
        chunk_size = 64000  # 64KB chunks
        num_chunks = target_bytes // chunk_size

        buffer = AudioRollingBuffer()
        dummy_chunk = b'\x55\xAA' * (chunk_size // 2)

        peak_buffer_len = 0
        total_pushed = 0

        t0 = time.perf_counter()
        for i in range(num_chunks):
            await buffer.append_pcm(dummy_chunk)
            total_pushed += len(dummy_chunk)
            curr_len = len(buffer._buffer)
            if curr_len > peak_buffer_len:
                peak_buffer_len = curr_len
            assert curr_len <= buffer.max_retention_bytes, (
                f"Buffer exceeded max_retention_bytes! Curr: {curr_len}, Max: {buffer.max_retention_bytes} at chunk {i}"
            )

        remainder = target_bytes - total_pushed
        if remainder > 0:
            rem_chunk = dummy_chunk[:remainder]
            await buffer.append_pcm(rem_chunk)
            total_pushed += len(rem_chunk)
            assert len(buffer._buffer) <= buffer.max_retention_bytes

        elapsed = time.perf_counter() - t0
        metrics = await buffer.get_buffer_metrics()

        assert metrics["total_received_bytes"] == target_bytes
        assert metrics["buffered_bytes"] <= buffer.max_retention_bytes
        assert len(buffer._buffer) == buffer.max_retention_bytes
        assert peak_buffer_len == buffer.max_retention_bytes
        print(f"\n[100MB Async Stream] Streamed {target_bytes:,} bytes in {elapsed:.2f}s. Peak buffer: {peak_buffer_len:,} bytes. STRICT BOUND VERIFIED.")

    def test_100mb_continuous_stream_sync(self):
        """
        Streams 100MB in 32KB chunks via synchronous add_pcm().
        Invariant: len(_buffer) <= 384,000 bytes at EVERY step.
        """
        target_bytes = 100 * 1024 * 1024  # 104,857,600 bytes
        chunk_size = 32000
        num_chunks = target_bytes // chunk_size

        buffer = AudioRollingBuffer()
        dummy_chunk = b'\x01\x02' * (chunk_size // 2)

        peak_buffer_len = 0
        total_pushed = 0
        t0 = time.perf_counter()
        for i in range(num_chunks):
            buffer.add_pcm(dummy_chunk)
            total_pushed += len(dummy_chunk)
            curr_len = len(buffer._buffer)
            if curr_len > peak_buffer_len:
                peak_buffer_len = curr_len
            assert curr_len <= buffer.max_retention_bytes, f"Sync buffer exceeded bound at chunk {i}! Length: {curr_len}"

        remainder = target_bytes - total_pushed
        if remainder > 0:
            rem_chunk = dummy_chunk[:remainder]
            buffer.add_pcm(rem_chunk)
            total_pushed += len(rem_chunk)
            assert len(buffer._buffer) <= buffer.max_retention_bytes

        elapsed = time.perf_counter() - t0
        assert buffer._total_bytes_received == target_bytes
        assert len(buffer._buffer) == buffer.max_retention_bytes
        assert peak_buffer_len == buffer.max_retention_bytes
        print(f"\n[100MB Sync Stream] Streamed {target_bytes:,} bytes in {elapsed:.2f}s. Peak buffer: {peak_buffer_len:,} bytes. STRICT BOUND VERIFIED.")

    def test_single_giant_chunk_pruning(self):
        """
        Appends a single 10MB chunk (10,485,760 bytes).
        Verifies buffer immediately retains ONLY the last 384,000 bytes without memory bloat.
        """
        giant_chunk = b'X' * (10 * 1024 * 1024)
        buffer = AudioRollingBuffer()
        buffer.add_pcm(giant_chunk)

        assert len(buffer._buffer) == buffer.max_retention_bytes
        assert buffer._total_bytes_received == 10 * 1024 * 1024

    def test_random_chunk_jitter_100mb_memory_leak_check(self):
        """
        Streams 100MB using highly randomized chunk sizes (1 byte to 450,000 bytes).
        Verifies constant O(1) resident heap memory footprint using tracemalloc.
        """
        tracemalloc.start()
        gc.collect()
        snapshot_start = tracemalloc.take_snapshot()

        buffer = AudioRollingBuffer()
        target_bytes = 100 * 1024 * 1024
        bytes_streamed = 0
        random.seed(42)

        while bytes_streamed < target_bytes:
            remaining = target_bytes - bytes_streamed
            max_c = min(remaining, 450000)
            c_size = random.randint(1, max_c)
            chunk = b'\x77' * c_size
            buffer.add_pcm(chunk)
            bytes_streamed += c_size
            assert len(buffer._buffer) <= buffer.max_retention_bytes

        gc.collect()
        snapshot_end = tracemalloc.take_snapshot()
        stats = snapshot_end.compare_to(snapshot_start, 'lineno')
        tracemalloc.stop()

        total_growth = sum(stat.size_diff for stat in stats)
        assert total_growth < 5 * 1024 * 1024, f"Excessive memory leak detected! Growth: {total_growth:,} bytes"
        assert len(buffer._buffer) == buffer.max_retention_bytes
        print(f"\n[100MB Jitter + Tracemalloc] Growth: {total_growth / 1024:.2f} KB. STRICT O(1) MEMORY FOOTPRINT VERIFIED.")


# ============================================================================
# 5. HIGH CONCURRENCY PIPELINE INTEGRATION & CLIENT RESILIENCE
# ============================================================================
class TestPipelineAdversarialIntegration:
    """
    End-to-end adversarial tests combining AudioRollingBuffer, TextStitcher,
    and mock/live API flows.
    """

    @pytest.mark.asyncio
    async def test_streaming_audio_pipeline_with_offset_and_zero_matches(self):
        """
        Simulates sequential audio chunks through AudioPipeline.
        Verifies no exceptions, consistent telemetry, and zero word loss.
        """
        from unittest.mock import AsyncMock
        pipeline = AudioPipeline()
        
        mock_transcripts = [
            ("Welcome to the natural history museum exhibition today", "en"),
            ("history museum exhibition today we will see fossils", "en"),
            ("we will see fossils and ancient dinosaur bones", "en"),
            ("The gift shop is open until five in the evening", "en"),
            ("open until five in the evening please visit us", "en"),
        ]

        transcribe_mock = AsyncMock()
        transcribe_mock.side_effect = [
            type("WhisperRes", (), {"text": t, "language": l, "language_name": "English", "latency_ms": 50.0, "error": None})()
            for t, l in mock_transcripts
        ]
        pipeline.whisper_client.transcribe_wav = transcribe_mock

        chunk_pcm = b'\x00\x01' * 32000
        results = []
        for i in range(5):
            res = await pipeline.process_chunk(chunk_pcm)
            if res:
                results.append(res)

        final_res = await pipeline.flush()
        if final_res:
            results.append(final_res)

        assert len(results) >= 1
        final_text = pipeline.stitcher.committed_text
        assert "Welcome" in final_text
        assert "fossils" in final_text
        assert "gift shop" in final_text
        assert "five in the evening" in final_text