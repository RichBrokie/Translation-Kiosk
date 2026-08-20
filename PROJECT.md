# Project: Translation Kiosk

## Architecture
- **Host / VM Environment**: Ubuntu 24.04/26.04 VM (`100.109.43.41`) accessed via `plink.exe`, running NVIDIA RTX 6000 Ada, Python 3.14 virtualenv at `/home/ubuntu/ai_kiosk`.
- **Backend Architecture**: Asynchronous FastAPI service running in `/home/ubuntu/translation_kiosk` on port `0.0.0.0:8080`.
  - `config.py`: 16kHz audio parameters, API URLs, language mappings, timeouts.
  - `audio_pipeline.py`: In-memory PCM rolling buffer (`AudioRollingBuffer`), sliding-window chunker (4.0s window / 2.0s overlap), RIFF WAV packager, `TextStitcher` with sequence matching, `ComparativeEngine`, and `AudioPipeline`.
  - `whisper_client.py`: Async HTTP client for Faster-Whisper ASR (`POST http://localhost:8001/transcribe`), language detection extractor.
  - `qwen_client.py`: Async HTTP client for Qwen 2.5 72B Instruct AWQ (`POST http://localhost:8000/v1/chat/completions`), single-call prompt for post-correction + translation, English bypass handler.
  - `telemetry.py`: Latency metrics collection, percentiles, API call logging.
  - `main.py`: FastAPI server, WebSocket handlers (`/ws/audio`, `/ws/admin`), REST endpoints (`/health`, `/api/config`, `/api/logs`, `/api/test/audio_file`), static file mounting, template rendering.
- **Frontend Architecture**:
  - Public Kiosk GUI (`/`): HTML5/CSS3/Vanilla JS, AudioWorklet PCM recorder (16kHz mono), WebSocket audio streamer, high-contrast WCAG AAA 1920x1080 touchscreen layout, live transcription display, translated English display, source language badge.
  - Admin Monitoring Panel (`/admin`): HTML5/CSS3/JS, WebSocket telemetry consumer (`/ws/admin`), real-time Whisper & Qwen latency gauges with sparklines, audio buffer monitor, 4-stage raw vs sliding-window diff viewer, searchable live API call log.
- **Deployment Architecture**: Systemd unit `/etc/systemd/system/translation-kiosk.service` running on boot, coexisting cleanly with `vllm.service` (8000) and `audio-kiosk.service` (8001).

## Feature Inventory
| # | Feature | Description | Milestone | Status |
|---|---------|-------------|-----------|--------|
| 1 | PCM Audio Capture & WebSocket Streaming | Browser AudioWorklet capturing 16kHz mono 16-bit PCM streaming over WebSocket | M3 | DONE |
| 2 | In-Memory Audio Buffer & Window Slicing | Buffer maintaining rolling audio frames and slicing into 4s windows with 2s overlap | M1 | DONE |
| 3 | Whisper ASR Async Integration | Async client calling `POST http://localhost:8001/transcribe` with WAV payload | M1 | DONE |
| 4 | Language Auto-Detection | Extract language code from Whisper response and propagate to UI/Admin | M1 | DONE |
| 5 | Sliding-Window Overlap Re-Transcription | Re-transcribe overlapping audio segments to utilize future acoustic context | M1 | DONE |
| 6 | Text Alignment & Stitching Engine | SequenceMatcher/LCS merging new overlap transcription into committed text | M1 | DONE |
| 7 | Qwen 72B Post-Correction & Translation | Single-call JSON chat completion prompt for grammar correction + English translation | M1 | DONE |
| 8 | English Language Bypass Logic | Automatic bypass of Qwen translation when detected language is 'en' | M1 | DONE |
| 9 | Dual-Pipeline Comparative Engine | Concurrent execution of non-overlapping vs sliding-window for verification | M1 | DONE |
| 10 | FastAPI Server Core & Lifecycle | App lifecycle, static routing, config management, graceful shutdown on port 8080 | M2 | DONE |
| 11 | Audio WebSocket Protocol (`/ws/audio`) | Binary PCM audio ingestion, session management, real-time response broadcast | M2 | DONE |
| 12 | Admin WebSocket Telemetry (`/ws/admin`)| Stream buffer metrics, latency measurements, diff data, and API logs | M2 | DONE |
| 13 | File Playback Simulation Endpoint | REST endpoint `POST /api/test/audio_file` for headless testing & audio replay | M2 | DONE |
| 14 | Public Kiosk GUI (1920x1080 Touchscreen) | Large readable fonts, high contrast (#0b0f19 / #ffffff), responsive layout | M3 | DONE |
| 15 | Kiosk Fullscreen & Audio Controls | Fullscreen toggle, Start/Stop recording button with 4-state lifecycle | M3 | DONE |
| 16 | Real-time Transcription & Translation Display | Dual cards for live transcription stream and completed English translation | M3 | DONE |
| 17 | Source Language Display Badge | Visual badge indicating detected language name and code | M3 | DONE |
| 18 | Admin Latency Gauges & Buffer Telemetry | Visual gauges for Whisper (<5s) and Qwen (<8s) latencies, buffer depth gauge | M3 | DONE |
| 19 | Admin 4-Stage Diff & API Interaction Log | Side-by-side comparison of raw vs sliding-window, scrollable API logs | M3 | DONE |
| 20 | Systemd Service Unit (`translation-kiosk.service`) | Auto-start on boot, Restart=always, multi-service coexistence | M4 | DONE |
| 21 | Automated E2E Verification Test Suite | Headless test runner testing WAV audio playback across languages & latencies | M5 | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Audio Pipeline & API Integrations | Audio buffer, sliding-window chunker, Whisper client, Qwen client, text stitching, English bypass | none | DONE |
| M2 | Backend Web Server & WebSocket Telemetry | FastAPI core, `/ws/audio`, `/ws/admin`, `/api/test/audio_file`, logging & metrics dispatcher | M1 | DONE |
| M3 | Frontend Public Kiosk UI & Admin Panel | Touchscreen Kiosk UI (`/`), Admin Dashboard (`/admin`), AudioWorklet, WebSocket clients | M2 | DONE |
| M4 | Systemd Service & Remote Deployment | Systemd unit file, service enablement, VM deployment, restart testing | M2, M3 | DONE |
| M5 | E2E Integration & Verification | E2E test execution (347 pytest tests, verify_kiosk_pipeline.py live verification) | M1, M2, M3, M4 | DONE |

## Verified System Status
- `translation-kiosk.service`: ACTIVE (Port 8080)
- `vllm.service`: ACTIVE (Port 8000)
- `audio-kiosk.service`: ACTIVE (Port 8001)
- Full Test Suite: 347/347 tests passed in 36.87s
- Live Spanish E2E: Whisper 458ms (<5000ms), Qwen 4993ms (<8000ms), E2E 5453ms
- Live English E2E: Whisper 462ms, Qwen bypass 0.0ms, E2E 462ms
