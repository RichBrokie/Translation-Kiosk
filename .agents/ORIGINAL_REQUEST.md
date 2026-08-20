# Original User Request

## Initial Request — 2026-08-19T09:06:26Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Build a production-ready, web-based real-time Translation Kiosk application. The system captures audio from the user's microphone in the browser, streams it in buffered chunks to a backend, which transcribes it using a Whisper ASR API and translates it using a Qwen 72B LLM API. A sliding-window correction mechanism re-processes overlapping audio to let Whisper fix past transcription errors with future context, and Qwen post-corrects the combined text before translating to English.

The application must serve two views: a public-facing kiosk display (fullscreen, large text, designed for museum visitors) and an admin monitoring panel (showing pipeline metrics, latency, detected languages, and raw debug output). Both views are web pages served from the same backend.

Working directory: /home/ubuntu/translation_kiosk
Integrity mode: development

**Backend API endpoints are already running and must NOT be modified:**
- Whisper ASR: `POST http://localhost:8001/transcribe` — accepts multipart file upload (`file` field, WAV format), returns `{"text": "...", "language": "..."}`
- Qwen LLM: `POST http://localhost:8000/v1/chat/completions` — OpenAI-compatible chat completions API, model name: `/mnt/models/qwen2.5-72b-instruct-awq`

**Runtime environment:**
- Ubuntu 24.04 VM with Python 3.14 virtualenv at `/home/ubuntu/ai_kiosk`
- The application must install its own dependencies into this existing virtualenv
- The app should bind to `0.0.0.0:8080` so it's accessible from any device on the network
- `ffmpeg` is available on the system PATH

## Requirements

### R1. Web-Based Kiosk GUI (Public View)
A fullscreen-capable web page designed for public museum visitors. It must display: the detected source language, the live transcription updating in real-time as audio is processed, and the English translation appearing as sentences are completed. The design should use large readable fonts, high contrast, and work well on a touchscreen display. There should be a visible "Start / Stop" recording control.

### R2. Admin Monitoring Panel
A separate web page (e.g., `/admin`) that shows real-time pipeline diagnostics: current audio buffer status, Whisper processing latency per chunk, Qwen translation latency, detected source language confidence, raw transcription text before and after correction, and a running log of all API calls with timestamps.

### R3. Sliding-Window Audio Correction Pipeline
The audio capture must use a buffered chunking strategy with overlap. When a new audio chunk arrives, the system must re-transcribe a window that includes the tail of the previous chunk plus the new chunk, so that Whisper has future context to correct errors in the previous transcription. After Whisper produces the corrected transcription, the combined recent text must be sent to Qwen with a prompt that asks it to fix any remaining grammatical or contextual errors AND translate to English in a single call. The overlap duration and chunk size should be configurable.

### R4. Language Auto-Detection and Translation
The system must auto-detect the source language using Whisper's language detection (returned in the API response) and translate all input to English. If the detected source language is already English, display the transcription directly without calling Qwen for translation.

### R5. Deployment as a Systemd Service
The application must include a systemd service unit file that starts the web server automatically on boot, with proper restart-on-failure behavior. It should coexist with the existing `vllm.service` (port 8000) and `audio-kiosk.service` (port 8001) without conflicts.

## Acceptance Criteria

### Kiosk GUI
- [ ] The kiosk page loads in a browser at `http://<server-ip>:8080/` and displays a clean, fullscreen-ready interface
- [ ] Pressing "Start" begins capturing audio from the browser microphone
- [ ] Transcribed text appears on screen within 5 seconds of speech ending
- [ ] Translation to English appears within 8 seconds of speech ending
- [ ] The detected source language is displayed on screen
- [ ] The interface is usable on a 1920x1080 touchscreen (large fonts, high contrast)

### Admin Panel
- [ ] The admin page loads at `http://<server-ip>:8080/admin`
- [ ] It displays real-time latency metrics for Whisper and Qwen calls
- [ ] It shows the raw transcription before and after sliding-window correction
- [ ] It maintains a scrollable log of all API interactions

### Sliding-Window Correction
- [ ] Audio chunks overlap by a configurable amount (default: 2-3 seconds)
- [ ] Re-transcription of overlapping audio demonstrably corrects at least some errors compared to non-overlapping chunking (verifiable by comparing outputs in the admin panel)
- [ ] Qwen post-correction step runs before translation and produces cleaner text

### Deployment
- [ ] A systemd service file is provided that starts the application
- [ ] The service starts cleanly alongside vllm.service and audio-kiosk.service
- [ ] The service restarts automatically on failure

### Verification
- [ ] A test script is provided that plays back a WAV audio file through the system (simulating microphone input via file upload) and verifies that transcription and translation output appear correctly
- [ ] The test script reports Whisper latency, Qwen latency, and end-to-end latency per chunk

---
*Expecting this to run as a full project with multiple components (frontend, backend, audio pipeline, deployment). Ready to launch on user approval.*

## Follow-up — 2026-08-19T10:04:29Z

The system experienced a power outage and rebooted! The host, VM, and backend AI services (Qwen/Whisper) have successfully recovered and are running, but all your background processes and tasks were killed. Please resume your implementation of the GUI and streaming architecture!

## Follow-up — 2026-08-19T10:36:05Z

Hey team, there was another power outage! I have successfully revived the host server, cleared the Hyper-V DDA lock, and restarted the Ubuntu VM. Both the `vllm.service` and `audio-kiosk.service` are back online and healthy. Please resume your work on the Kiosk UI and streaming architecture!

## Follow-up — 2026-08-20T09:07:48Z

Good news! Our token quotas have reset for the day, and the system is fully operational. The Ubuntu VM, Qwen, and Whisper are all running flawlessly. Please reconnect and resume your work on the Kiosk UI and test infrastructure!

## Follow-up — 2026-08-20T09:19:23Z

CRITICAL DIRECTIVE: The user is highly concerned about API token quotas (which we exhausted yesterday). You MUST minimize your token usage for the remainder of this project. Do NOT over-engineer the remaining milestones. Keep agent-to-agent communication extremely concise, avoid dumping large files into context unless absolutely necessary, and prioritize getting a working MVP of the frontend out immediately rather than exhausting tokens on endless adversarial reviews.

## Follow-up — 2026-08-20T09:39:55Z

EMERGENCY DIRECTIVE: The user only has 16% of their daily token quota left! You MUST wrap up immediately. ABORT all remaining test suite construction (`worker_test_impl_3`), ABORT all adversarial validation. Output the simplest possible Frontend HTML/JS and Backend FastAPI server, wrap it in a systemd service, and mark the task as COMPLETE. We cannot afford any more testing loops!





