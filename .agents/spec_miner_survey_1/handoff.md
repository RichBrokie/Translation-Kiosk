# Handoff Report: UI & System Specification Mining (Spec Miner 1)

## 1. Observation

1. **User Request and Constraints**:
   - `c:\Work\.agents\ORIGINAL_REQUEST.md`:
     - Line 15: `Working directory: /home/ubuntu/translation_kiosk`
     - Line 18-20: `Backend API endpoints are already running and must NOT be modified:`
       - `Whisper ASR: POST http://localhost:8001/transcribe` (multipart `file` upload, returns `{"text": "...", "language": "..."}`)
       - `Qwen LLM: POST http://localhost:8000/v1/chat/completions` (OpenAI chat completions, model `/mnt/models/qwen2.5-72b-instruct-awq`)
     - Line 22-26: Ubuntu 24.04 VM with Python 3.14 virtualenv at `/home/ubuntu/ai_kiosk`, app binds to `0.0.0.0:8080`, `ffmpeg` available.
     - Line 30-32 (R1): Public View on port 8080 `/` with fullscreen capability, detected source language badge, live transcription updating in real-time, completed sentence English translation, large readable fonts, high contrast, 1920x1080 touchscreen design, visible Start/Stop recording control.
     - Line 33-35 (R2): Admin Monitoring Panel at `/admin` showing real-time pipeline diagnostics, audio buffer status, Whisper latency per chunk, Qwen latency, detected source language confidence, raw transcription before and after sliding-window correction, and running API log with timestamps.
     - Line 39-41 (R4): Language auto-detection; if English, bypass Qwen and display directly.
     - Line 42-44 (R5): Systemd service unit starting automatically on boot, `Restart=on-failure` or `Restart=always`, coexisting with `vllm.service` (port 8000) and `audio-kiosk.service` (port 8001).
     - Line 72-74 (Acceptance Criteria): Test script playing back WAV audio through system, verifying transcription and translation output, reporting Whisper latency (<5s), Qwen latency, and E2E latency (<8s).

2. **Existing System Configuration**:
   - `c:\Work\audio-kiosk.service`:
     - Line 10: `ExecStart=/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/audio_server.py`
     - Line 11-12: `Restart=on-failure`, `RestartSec=15`
     - Line 7: `User=ubuntu`
   - `c:\Work\audio_server.py`:
     - Line 10: `whisper_model = WhisperModel("/mnt/models/whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")`
     - Line 12-20: FastAPI endpoint `POST /transcribe` accepting `UploadFile = File(...)` returning `{"text": text, "language": info.language}`.
   - `c:\Work\script.sh`:
     - Line 1: `sed -i 's/--port 8000/--port 8000 --max-model-len 8192/' /etc/systemd/system/vllm.service` confirming vLLM runs on port 8000.

---

## 2. Logic Chain

1. **UI Layout and Touchscreen Design (R1)**:
   - *Premise*: Public museum visitors interact via a 1920x1080 touchscreen under varied lighting conditions at standing distances (1.5-3m).
   - *Inference*: UI must feature WCAG AAA compliant contrast (dark obsidian canvas `#0b0f19` vs pure white `#ffffff`, contrast ratio 17.8:1), oversized touch targets ($\ge 96\times 96\text{px}$), fluid clamp-scaled typography (`2.2rem - 3.2rem`), and a responsive 2-column card layout displaying original live transcription alongside final English translations.
   - *Inference*: Recording lifecycle requires a deterministic 4-state machine (`IDLE` $\to$ `RECORDING` $\to$ `PROCESSING` $\to$ `ERROR`) with instant visual feedback (pulsing mic visualizer, audio level wave).

2. **Admin Telemetry and Sliding-Window Verification (R2)**:
   - *Premise*: Admins require diagnostic verification of audio buffer state, per-chunk Whisper latency, Qwen latency, and proof that the sliding-window algorithm repairs audio boundaries.
   - *Inference*: The `/admin` dashboard must stream real-time telemetry over a dedicated WebSocket (`/ws/admin`), displaying dual latency gauges (0-5000ms Whisper, 0-8000ms Qwen), a buffer duration meter, a 4-stage diff comparison viewer (Raw chunk $\to$ Overlapped window re-transcription $\to$ Qwen post-correction $\to$ Translation), and a searchable, scrollable API interaction terminal table.

3. **Systemd Service Unit & Multi-Process Coexistence (R5)**:
   - *Premise*: The system operates 3 daemon services on a single Ubuntu host: vLLM (port 8000), Faster-Whisper (port 8001), and Kiosk Web Server (port 8080).
   - *Inference*: `translation-kiosk.service` must specify `After=network.target vllm.service audio-kiosk.service` and `Wants=vllm.service audio-kiosk.service` so services initialize properly on boot. ExecStart must target `/home/ubuntu/ai_kiosk/bin/python server.py` in `/home/ubuntu/translation_kiosk`, with `Restart=on-failure` and `RestartSec=5s`.

4. **Automated Verification Test Framework**:
   - *Premise*: Rigorous verification requires automated simulation of microphone audio chunking without manual human speech input.
   - *Inference*: A test runner (`verify_kiosk_pipeline.py`) must stream multi-lingual WAV test files (ES, FR, DE, ZH, AR, EN) in 2.0s overlapping chunks to test transcription fidelity, translation accuracy, English bypass verification, and enforce strict SLA assertions ($T_{whisper} < 5\text{s}$, $T_{e2e} < 8\text{s}$).

---

## 3. Caveats

1. **Backend Service Latency Under Load**: Whisper Large-v3-Turbo typically executes in 200-400ms on CUDA, and Qwen 2.5 72B AWQ in 800-1500ms on vLLM. If system GPU memory or compute is saturated, Qwen may approach the 8-second SLA threshold; the frontend must implement graceful progressive rendering and non-blocking asynchronous streaming.
2. **Microphone Permissions in Web Browsers**: Modern web browsers restrict `getUserMedia()` to HTTPS origins or `localhost`. When deploying to `http://<server-ip>:8080`, kiosk client browsers must be configured with appropriate Chrome flags (e.g. `--unsafely-treat-insecure-origin-as-secure`) or served behind TLS/local kiosk mode.

---

## 4. Conclusion

All specifications for R1 (Public Kiosk GUI), R2 (Admin Monitoring Panel), R5 (Systemd Service Unit), REST/WebSocket Interface Contracts, and Automated Verification Test Scripts have been formally defined in `c:\Work\.agents\spec_miner_survey_1\spec.md`. The design is completely aligned with `ORIGINAL_REQUEST.md`, fully specifying 20 discovered features, 12 edge cases, complete wireframes, styling tokens, state machines, protocol payloads, unit file directives, and test fixtures.

---

## 5. Verification Method

To verify the mined specifications:
1. **Inspect Specification Artifact**:
   - Read `c:\Work\.agents\spec_miner_survey_1\spec.md`.
   - Verify Section 2 (Features Discovered Table) and Section 3 (Edge Cases Table).
   - Verify Section 4 (Public Kiosk GUI design tokens, typography scale, wireframe, and 4-state lifecycle).
   - Verify Section 5 (Admin Monitoring Panel telemetry, latency gauges, diff viewer, and API interaction log schema).
   - Verify Section 6 (WebSocket `/ws/audio`, `/ws/admin` and REST contracts).
   - Verify Section 7 (Systemd `translation-kiosk.service` unit file specification and dependency graph).
   - Verify Section 8 (Acceptance & Verification test script design, SLA thresholds, and multilingual fixtures).
2. **Check Original Request Consistency**:
   - Cross-check each requirement R1, R2, R4, R5 and Acceptance Criteria in `c:\Work\.agents\ORIGINAL_REQUEST.md` against Section 2 and Sections 4-8 in `spec.md`.
