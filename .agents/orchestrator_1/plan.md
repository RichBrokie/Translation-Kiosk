# Streamlined Project Plan — Translation Kiosk (Token-Optimized)

## Directive
Minimize token usage, eliminate bloated review/adversarial cycles, and prioritize getting a working MVP of the backend server, frontend (Kiosk UI + Admin Panel), systemd service, and E2E verification running immediately.

## Streamlined Milestones
1. **M1 (Core Audio Pipeline)**: Completed/in-flight by sub_orch_m1 / worker_m1_1 (config.py, audio_pipeline.py, whisper_client.py, qwen_client.py, telemetry.py, test_pipeline.py).
2. **M2/M3/M4 Integrated MVP Deployment**:
   - Single focused Worker to implement `main.py` (FastAPI + WebSockets `/ws/audio`, `/ws/admin`, `/api/test/audio_file`), static assets (`static/css/`, `static/js/`, `templates/kiosk.html`, `templates/admin.html`), and systemd unit (`translation-kiosk.service`).
   - Start and verify systemd service on `0.0.0.0:8080` alongside vllm (8000) and audio-kiosk (8001).
3. **M5 Verification & Acceptance**:
   - Run verification test script (`verify_kiosk_pipeline.py`) simulating audio file playback, measuring latencies, and verifying full E2E operation.
   - Final audit and delivery report.
