# Test Infrastructure Specification: Translation Kiosk

## 1. Overview & Test Architecture

The Translation Kiosk test infrastructure provides a modular, multi-tier testing framework designed to validate all aspects of the real-time speech-to-speech translation kiosk system. The target application is an asynchronous FastAPI web service (`translation_kiosk`) deployed on an Ubuntu 26.04 VM with an NVIDIA RTX 6000 Ada GPU, integrating Faster-Whisper ASR (`http://localhost:8001/transcribe`), vLLM Qwen 2.5 72B Instruct AWQ (`http://localhost:8000/v1/chat/completions`), WebSocket audio capture & telemetry streams, and responsive touchscreen interfaces.

### Core Testing Objectives
- Verify all 15 system features (F1–F15) in isolation (Tier 1).
- Verify resilience against boundary conditions, starvation, malformed payloads, clipping, and rapid reconnections (Tier 2).
- Verify multi-component pairwise integration flows across the full pipeline (Tier 3).
- Verify real-world multilingual audio workloads across 8 natural human speech recordings with ground-truth validation (Tier 4).
- Provide a standalone CLI verification tool (`verify_kiosk_pipeline.py`) capable of streaming arbitrary WAV files, auditing per-chunk latency budgets, and validating the sliding-window correction improvement against a non-overlapping baseline.

### System Test Topology
```
+-----------------------------------------------------------------------------------------------+
|                                      Ubuntu 26.04 VM                                          |
|                                                                                               |
|  +---------------------------------------+         +---------------------------------------+  |
|  |       Faster-Whisper ASR (:8001)       |         |          vLLM Qwen 72B (:8000)        |  |
|  |     Model: whisper-large-v3-turbo     |         |  Model: qwen2.5-72b-instruct-awq      |  |
|  |        audio-kiosk.service            |         |            vllm.service               |  |
|  +---------------------------------------+         +---------------------------------------+  |
|                      ^                                                 ^                      |
|                      | HTTP Multipart                                  | HTTP JSON            |
|                      +------------------------+  +---------------------+                      |
|                                               |  |                                            |
|                                     +--------------------+                                    |
|                                     | Translation Kiosk  |                                    |
|                                     |  FastAPI (:8080)   |                                    |
|                                     | audio_pipeline.py  |                                    |
|                                     +--------------------+                                    |
|                                       ^         ^      ^                                      |
|                       WebSocket /ws/audio   REST /api  WebSocket /ws/admin                    |
|                                       |         |      |                                      |
|  +------------------------------------+---------+------+-----------------------------------+  |
|  |                                  Test Suite & Runner                                     |  |
|  |  - Pytest Framework (conftest.py, fixtures, async event loops)                          |  |
|  |  - Tier 1: test_tier1_feature_coverage.py (75 tests, 5 per feature F1-F15)               |  |
|  |  - Tier 2: test_tier2_boundary_corner.py (75 tests, edge/corner/adversarial)            |  |
|  |  - Tier 3: test_tier3_cross_feature.py (15 pairwise interaction tests)                   |  |
|  |  - Tier 4: test_tier4_real_world_scenarios.py (8 multilingual audio workloads)          |  |
|  |  - Standalone Runner: verify_kiosk_pipeline.py (CLI audio streamer & benchmark auditor) |  |
|  +------------------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Four-Tier Testing Methodology

The test suite is structured into 4 distinct verification tiers totaling **173 test cases**:

```
+------------------------------------------------------------------------------------------+
|  Tier 1: Feature Coverage (75 tests)      | 5 isolated unit/functional tests per feature |
|  Tier 2: Boundary & Corner (75 tests)     | 5 adversarial/stress tests per feature       |
|  Tier 3: Cross-Feature (15 tests)         | Pairwise integration across subsystems       |
|  Tier 4: Real-World Scenarios (8 tests)   | Full audio streaming across 8 languages      |
+------------------------------------------------------------------------------------------+
```

### Feature Inventory & Mapping (F1–F15)

| # | Feature Code | Feature Name | Description | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|--------------|--------------|-------------|--------|--------|--------|--------|
| 1 | `F1` | PCM Audio Capture & WebSocket Streaming | 16kHz mono 16-bit PCM binary ingestion via `/ws/audio` | 5 | 5 | Pairwise | ✓ |
| 2 | `F2` | In-Memory Audio Buffer & Window Slicing | Ring buffer slicing 4.0s windows with 2.0s overlap | 5 | 5 | Pairwise | ✓ |
| 3 | `F3` | Whisper ASR Async Integration | Faster-Whisper `:8001/transcribe` multipart client (<5s latency) | 5 | 5 | Pairwise | ✓ |
| 4 | `F4` | Language Auto-Detection | Language code extraction (`es`, `fr`, `de`, etc.) and name mapping | 5 | 5 | Pairwise | ✓ |
| 5 | `F5` | Sliding-Window Overlap Re-Transcription | 2.0s overlap re-transcription for acoustic boundary correction | 5 | 5 | Pairwise | ✓ |
| 6 | `F6` | Text Alignment & Stitching Engine | SequenceMatcher / LCS overlap alignment and deduplication | 5 | 5 | Pairwise | ✓ |
| 7 | `F7` | Qwen 72B Post-Correction & Translation | Single-call JSON chat completion at `:8000` (<8s latency) | 5 | 5 | Pairwise | ✓ |
| 8 | `F8` | English Language Bypass Logic | 0ms LLM latency bypass when detected language is `en` | 5 | 5 | Pairwise | ✓ |
| 9 | `F9` | Dual-Pipeline Comparative Engine | Concurrent sliding-window vs non-overlapping baseline | 5 | 5 | Pairwise | ✓ |
| 10| `F10`| FastAPI Server Core & Lifecycle | Web routing, health endpoints, static assets on port 8080 | 5 | 5 | Pairwise | ✓ |
| 11| `F11`| Admin WebSocket Telemetry | Real-time latency, buffer depth, and diff streaming via `/ws/admin`| 5 | 5 | Pairwise | ✓ |
| 12| `F12`| Audio File Playback Simulation Endpoint | REST `POST /api/test/audio_file` replay and latency reporting | 5 | 5 | Pairwise | ✓ |
| 13| `F13`| Public Kiosk UI Touchscreen Layout | High-contrast WCAG AAA 1920x1080 UI and button lifecycle | 5 | 5 | Pairwise | ✓ |
| 14| `F14`| Admin Monitoring Dashboard & Gauges | Whisper (<5s) & Qwen (<8s) latency gauges, diff visualizer | 5 | 5 | Pairwise | ✓ |
| 15| `F15`| Systemd Service Unit Lifecycle | Auto-start, `Restart=on-failure`, coexistence with daemons | 5 | 5 | Pairwise | ✓ |

---

### Tier Breakdown

#### Tier 1: Feature Coverage (75 Test Cases — 5 per feature)
- `TC-T1-F01-01` to `TC-T1-F01-05`: WebSocket handshake, 16kHz PCM streaming, transcription events, translation events, clean teardown.
- `TC-T1-F02-01` to `TC-T1-F02-05`: 4.0s window trigger (128,000 bytes), 2.0s sliding step, RIFF WAV header compliance, buffer reset, short-audio flush.
- `TC-T1-F03-01` to `TC-T1-F03-05`: Standard Whisper transcription, latency check (<5s), async non-blocking execution, response dataclass serialization, connection pooling.
- `TC-T1-F04-01` to `TC-T1-F04-05`: Spanish (`es`), French (`fr`), German (`de`), Japanese (`ja`) detection, language mapping table lookup.
- `TC-T1-F05-01` to `TC-T1-F05-05`: Overlap re-transcription, boundary phoneme recovery, configurable window parameters, timestamp tracking, memory stability.
- `TC-T1-F06-01` to `TC-T1-F06-05`: Exact overlap stitching, fuzzy phonetic alignment, punctuation normalization, disjoint concatenation, cumulative history.
- `TC-T1-F07-01` to `TC-T1-F07-05`: Structured JSON prompt execution, latency check (<8s), grammatical correction, json_object mode, temperature determinism.
- `TC-T1-F08-01` to `TC-T1-F08-05`: Automatic Qwen bypass for `en`, sub-second E2E latency, UI translation card bypass, zero LLM API call invocation audit, mixed chunk routing.
- `TC-T1-F09-01` to `TC-T1-F09-05`: Concurrent baseline + sliding execution, diff generation, WER / distance metric calculation, telemetry dispatch, comparison toggle.
- `TC-T1-F10-01` to `TC-T1-F10-05`: Port 8080 binding (`/`), admin route (`/admin`), static asset MIME types, `/api/health` status, graceful shutdown.
- `TC-T1-F11-01` to `TC-T1-F11-05`: Admin WS connection, latency metrics broadcast, buffer size telemetry, 4-stage diff payload, API interaction log broadcast.
- `TC-T1-F12-01` to `TC-T1-F12-05`: WAV file upload replay, per-chunk metrics breakdown, comparison diff output, sample rate auto-conversion, full summary report.
- `TC-T1-F13-01` to `TC-T1-F13-05`: High-contrast styles, Start/Stop 4-state machine, dual cards DOM update, language badge DOM update, fullscreen toggle.
- `TC-T1-F14-01` to `TC-T1-F14-05`: Gauge needle rendering, buffer progress bar, 4-stage diff columns, searchable API log table, latency sparkline.
- `TC-T1-F15-01` to `TC-T1-F15-05`: Service unit syntax validation, service start & port check, multi-service coexistence, restart-on-failure recovery, multi-user boot enablement.

#### Tier 2: Boundary & Corner Cases (75 Test Cases — 5 per feature)
- `TC-T2-F01-01` to `TC-T2-F01-05`: 0-byte frame ping flood, abrupt client disconnect mid-frame, 1MB jumbo frame overload, odd byte count (non-divisible by 2), rapid reconnect storm (20 connects/s).
- `TC-T2-F02-01` to `TC-T2-F02-05`: Sub-chunk starvation (<0.5s), maximum buffer cap & backpressure, exact 128,000-byte boundary slicing, pure digital silence (`0x00`), extreme amplitude clipping (`0x7FFF`).
- `TC-T2-F03-01` to `TC-T2-F03-05`: 0-byte payload guard (prevents HTTP 500 on :8001), corrupt WAV header handling, client timeout simulation (>5s), 10-request concurrency burst, heavy background noise (5dB SNR).
- `TC-T2-F04-01` to `TC-T2-F04-05`: Spanglish/mixed-language speech, rapid language switching per chunk (`es` -> `fr` -> `de`), rare language code mapping (`la`), empty language string fallback (`unknown`), case-insensitive code handling (`ES` vs `es`).
- `TC-T2-F05-01` to `TC-T2-F05-05`: Zero-overlap mode (`overlap_sec=0.0`), maximum overlap mode (`overlap_sec=3.5s`), repeated identical audio frames, noise spike at seam, frame arrival jitter (5ms–200ms).
- `TC-T2-F06-01` to `TC-T2-F06-05`: Completely disjoint overlap fallback, multi-byte Unicode UTF-8 seam alignment (Chinese/Japanese/Arabic), repetitive stutter merging, empty transcript preservation, 1,000-word history sliding performance.
- `TC-T2-F07-01` to `TC-T2-F07-05`: Markdown-fenced JSON stripping (````json ... ````), truncated JSON repair/fallback, 4096-token prompt overflow truncation, 8s LLM timeout fallback, prompt injection containment.
- `TC-T2-F08-01` to `TC-T2-F08-05`: Spanish loanwords in English speech, alternating language stream, configurable English grammar correction flag, empty English chunk handling, punctuation-only transcript filtering.
- `TC-T2-F09-01` to `TC-T2-F09-05`: Baseline crash isolation, zero-diff handling, out-of-order dual pipeline completion, 5-minute continuous stress test, extreme edit distance calculation.
- `TC-T2-F10-01` to `TC-T2-F10-05`: Port 8080 collision handling, missing static asset HTTP 404, 100-request parallel HTTP flood, malformed headers handling, rapid SIGINT handling during active stream.
- `TC-T2-F11-01` to `TC-T2-F11-05`: 50 concurrent admin WebSocket subscribers, slow consumer backpressure isolation, invalid JSON frame rejection, reconnection state recovery, 1000-entry log queue FIFO eviction.
- `TC-T2-F12-01` to `TC-T2-F12-05`: Non-audio file upload rejection (HTTP 400), oversized 150MB WAV rejection (HTTP 413), 0-sample header-only WAV rejection, 5 simultaneous simulation uploads, multi-channel (5.1 surround) auto-downmixing.
- `TC-T2-F13-01` to `TC-T2-F13-05`: Extreme responsive viewports (4K down to mobile), record button spam debouncing, 1,000-event DOM leak prevention, microphone permission denied handling, automatic WebSocket reconnect.
- `TC-T2-F14-01` to `TC-T2-F14-05`: >10s latency spike red alert rendering, RTL Arabic/Hebrew typography, regex token search safety in log table, 60Hz telemetry flood throttling (`requestAnimationFrame`), log export to JSON.
- `TC-T2-F15-01` to `TC-T2-F15-05`: SIGKILL (`kill -9`) recovery within 5s, vLLM daemon restart recovery, Whisper daemon restart recovery, journald structured logging, virtualenv environment variable isolation.

#### Tier 3: Cross-Feature Multi-Component Interactions (15 Test Cases)
- `TC-T3-PAIR-01` (F1+F2+F3): WebSocket PCM Ingestion -> Audio Ring Buffer -> Whisper ASR (<5s latency).
- `TC-T3-PAIR-02` (F2+F5+F6): Buffer Window Slicing -> Overlap Re-Transcription -> SequenceMatcher Stitching.
- `TC-T3-PAIR-03` (F3+F4+F8): Whisper ASR -> Language Auto-Detection (`en`) -> English Bypass (0ms LLM latency).
- `TC-T3-PAIR-04` (F3+F4+F7): Whisper ASR -> Non-English Detection -> Qwen 72B JSON Translation (<8s latency).
- `TC-T3-PAIR-05` (F5+F6+F9): Sliding Window -> SequenceMatcher -> Dual Pipeline Comparator & Diff Reporting.
- `TC-T3-PAIR-06` (F1+F11+F14): Live Audio WebSocket Stream -> Admin Telemetry Broadcast -> Admin UI Dashboard.
- `TC-T3-PAIR-07` (F12+F2+F3+F7): REST Audio File Playback Simulation -> Full Pipeline Trace & Summary.
- `TC-T3-PAIR-08` (F1+F10+F13): FastAPI Web Server -> WebSocket Audio -> Public Kiosk Touchscreen Lifecycle.
- `TC-T3-PAIR-09` (F7+F8+F11): Qwen Translation -> English Bypass Transition -> Admin Telemetry Gauges.
- `TC-T3-PAIR-10` (F10+F15+F3+F7): Systemd Service Boot -> FastAPI Server -> Backend AI Daemons (:8000, :8001).
- `TC-T3-PAIR-11` (F1+F3+F7+F13): Full End-to-End Latency Verification (Whisper <5s, Qwen <8s, Total <8.5s).
- `TC-T3-PAIR-12` (F6+F7+F11+F14): Stitched Text + Qwen Post-Correction -> 4-Stage Diff Visualization.
- `TC-T3-PAIR-13` (F1+F2+F12): Concurrent Live WebSocket Streaming + REST File Simulation Execution.
- `TC-T3-PAIR-14` (F3+F7+F11): Backend AI Service Degradation / Outage -> Graceful Fallback & Admin Logging.
- `TC-T3-PAIR-15` (F4+F6+F7): Mid-Stream Multilingual Language Switching (Bilingual Dialogue).

#### Tier 4: Real-World Multilingual Audio Workload Scenarios (8 Scenarios)
Using real TED Talk recordings from `/mnt/models/* Talks/*.wav`:
1. **Spanish (`es`)**: `Spanish Talks/Canaliza tu energía y termina tus proyectos...wav` (16.0s). Verified: detected `es`, Whisper <5s, Qwen <8s, boundary correction verified.
2. **French (`fr`)**: `French Talks/Choisir sa vie plutôt que la subir...wav` (16.0s). Verified: detected `fr`, elision apostrophe restoration (`ne s'est jamais donné les moyens`).
3. **German (`de`)**: `German Talks/Schluss mit dem Schönheitswahn...wav` (16.0s). Verified: detected `de`, compound noun stitching across 2s boundary.
4. **Mandarin (`zh`)**: `Mandarin Chinese Talks/不要被「主流」綁架你的人生...wav` (16.0s). Verified: detected `zh`, Chinese character boundary alignment without stutter.
5. **Standard Arabic (`ar`)**: `Standard Arabic Talks/العربية فصحى أم لهجات...wav` (16.0s). Verified: detected `ar`, RTL rendering & accurate English translation.
6. **Russian (`ru`)**: `Russian Talks/Искусство очаровывать незнакомцев...wav` (16.0s). Verified: detected `ru`, UTF-8 Cyrillic preservation and fluent translation.
7. **Japanese (`ja`)**: `Japanese Talks/Hope invites...wav` (16.0s). Verified: detected `ja`, honorific verb inflection alignment and translation.
8. **English with Noise (`en`)**: `English Talks/...wav` mixed with ambient crowd babble at 15dB SNR (16.0s). Verified: detected `en`, strictly **0.0 ms** Qwen latency (bypass enforced), total E2E < 1,000 ms.

---

## 3. Latency & Accuracy Budgets

| Metric | Authoritative Requirement | Baseline Observed | Strict Failure Threshold |
| :--- | :--- | :--- | :--- |
| **Whisper ASR Chunk Latency** | Within 5.0 seconds of speech | ~320–396 ms | `>= 5,000 ms` |
| **Qwen 72B Translation Latency** | Within 8.0 seconds of speech | ~3,100–4,300 ms | `>= 8,000 ms` |
| **English Language LLM Bypass** | Complete bypass for `en` | 0.0 ms | `> 0.0 ms` |
| **English Total E2E Latency** | Sub-second real-time | ~350 ms | `>= 1,000 ms` |
| **Non-English Total E2E Latency**| Sub-8.5s real-time | ~3,800–4,800 ms | `>= 8,500 ms` |
| **Server Startup & Recovery** | Systemd auto-restart | ~3.0 s | `>= 5.0 s` |

---

## 4. Test Harness & Fixture Design (`conftest.py`)

The test harness provides comprehensive fixtures supporting both **isolated mock mode** (for rapid CI / offline unit testing) and **live service mode** (connecting to ports 8000, 8001, and 8080):

### Synthetic Audio Generators
- `generate_sine_wave(freq_hz=440, duration_sec=4.0, sample_rate=16000, amplitude=0.5) -> bytes` (16-bit PCM)
- `generate_silence(duration_sec=4.0, sample_rate=16000) -> bytes` (All `0x00` PCM)
- `generate_clipped_audio(duration_sec=4.0, sample_rate=16000) -> bytes` (Full scale `0x7FFF` / `0x8000`)
- `generate_noise_audio(duration_sec=4.0, sample_rate=16000, snr_db=15.0) -> bytes` (Gaussian white noise)
- `pcm_to_wav(pcm_bytes: bytes, sample_rate=16000, channels=1, sampwidth=2) -> bytes` (Standard 44-byte RIFF WAV)

### Multilingual Audio Slicer & Loader
- `load_multilingual_speech_sample(language: str, duration_sec: float = 4.0, start_sec: float = 0.0) -> Tuple[bytes, bytes, str]`:
  - Dynamically searches `/mnt/models/<Language> Talks/*.wav`.
  - Automatically downsamples from 44.1kHz stereo to 16kHz mono 16-bit PCM.
  - Returns `(raw_pcm_bytes, riff_wav_bytes, ground_truth_text)`.

### Client & Server Fixtures
- `live_whisper_client`: Async HTTPX client pointing to `http://localhost:8001`.
- `live_qwen_client`: Async OpenAI/HTTPX client pointing to `http://localhost:8000`.
- `mock_whisper_client`: In-memory simulated Whisper ASR client for isolated testing.
- `mock_qwen_client`: In-memory simulated Qwen 2.5 72B client with structured JSON responses.
- `fastapi_test_client`: `httpx.AsyncClient` wrapped with `ASGITransport` targeting FastAPI `app`.

---

## 5. Standalone CLI Verification Runner (`verify_kiosk_pipeline.py`)

`verify_kiosk_pipeline.py` is a standalone CLI tool that simulates real microphone streaming from any WAV file through the Translation Kiosk pipeline.

### CLI Syntax & Options
```bash
/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/translation_kiosk/tests/verify_kiosk_pipeline.py [OPTIONS]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--audio` | String | `None` (or built-in sample) | Path to input WAV file to stream through pipeline |
| `--endpoint` | String | `http://localhost:8080` | Target FastAPI server base URL |
| `--live-services` | Flag | `True` (auto-detect) | Connect directly to active Whisper (:8001) and Qwen (:8000) daemons |
| `--window-sec` | Float | `4.0` | Sliding window duration in seconds |
| `--overlap-sec` | Float | `2.0` | Sliding window overlap duration in seconds |
| `--fast` | Flag | `False` | Fast-forward mode (no real-time chunk interval delays) |
| `--strict-latency` | Flag | `False` | Exit with code 1 if Whisper > 5s or Qwen > 8s |
| `--output-json` | String | `None` | Path to export detailed JSON benchmark results |
| `--compare` | Flag | `True` | Run dual pipeline comparison (sliding vs non-overlapping baseline) |

### Key Execution Verifications
1. **Streaming Audio Ingestion**: Slices input WAV into sequential frames, sends to pipeline.
2. **Per-Chunk Latency Breakdown**: Measures Whisper latency, Qwen latency, and E2E latency per window.
3. **English Bypass Audit**: Asserts that `qwen_latency_ms == 0.0` when detected language is `en`.
4. **Dual Pipeline WER Comparison**: Compares non-overlapping baseline transcript against sliding-window stitched transcript, reporting character and word error reduction.

---

## 6. Test Execution Guide

### 6.1 Running the Full Pytest Suite on the VM
```bash
# Run all 4 test tiers
/home/ubuntu/ai_kiosk/bin/python -m pytest /home/ubuntu/translation_kiosk/tests/ -v

# Run individual tiers
/home/ubuntu/ai_kiosk/bin/python -m pytest /home/ubuntu/translation_kiosk/tests/test_tier1_feature_coverage.py -v
/home/ubuntu/ai_kiosk/bin/python -m pytest /home/ubuntu/translation_kiosk/tests/test_tier2_boundary_corner.py -v
/home/ubuntu/ai_kiosk/bin/python -m pytest /home/ubuntu/translation_kiosk/tests/test_tier3_cross_feature.py -v
/home/ubuntu/ai_kiosk/bin/python -m pytest /home/ubuntu/translation_kiosk/tests/test_tier4_real_world_scenarios.py -v
```

### 6.2 Running Standalone Verification on Multilingual Audio Files
```bash
# Spanish Talk Verification with Strict Latency Check
/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/translation_kiosk/tests/verify_kiosk_pipeline.py \
    --audio "/mnt/models/Spanish Talks/Canaliza tu energía y termina tus proyectos ｜ Stefany Cohen ｜ TEDxPanamaCity.wav" \
    --fast \
    --strict-latency \
    --output-json /tmp/report_spanish.json

# English Talk Verification (Confirm 0ms Bypass)
/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/translation_kiosk/tests/verify_kiosk_pipeline.py \
    --audio "/mnt/models/English Talks/The secrets of learning a new language ｜ Lýdia Machová ｜ TED.wav" \
    --fast \
    --strict-latency \
    --output-json /tmp/report_english.json
```
