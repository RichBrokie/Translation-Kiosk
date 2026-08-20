## 2026-08-19T09:07:40Z
<USER_REQUEST>
You are Spec Miner 1 (UI & System Spec Miner) for the Translation Kiosk project.
Your working directory is: c:\Work\.agents\spec_miner_survey_1
Your parent conversation ID is: b3de212b-0da8-4b8d-86d2-e992e6f845f2

MANDATORY FIRST STEP:
Read the authoritative user request at: c:\Work\.agents\ORIGINAL_REQUEST.md

YOUR MISSION:
Extract and formalize comprehensive specifications for all user-facing, admin, and system components:
1. R1: Web-Based Kiosk GUI (Public View on port 8080 `/`):
   - 1920x1080 touchscreen UI design specs (typography, high contrast colors, visual layout).
   - Fullscreen mode handling and auto-fit.
   - Start / Stop recording controls with clear visual state indicators (recording, processing, idle, error).
   - Real-time live transcription stream display and completed sentence English translation display.
   - Detected source language badge/indicator.
2. R2: Admin Monitoring Panel (`/admin` on port 8080):
   - Real-time pipeline diagnostics dashboard specs.
   - Audio buffer status (buffer size, queue depth, chunk arrival timestamps).
   - Whisper per-chunk processing latency gauge/chart and Qwen translation latency gauge/chart.
   - Raw transcription text display: before vs after sliding-window correction comparison view.
   - Scrollable live API interaction log with timestamps, request params, and response status.
3. R5: Systemd Service Unit File (`translation-kiosk.service`):
   - Service definition, ExecStart, WorkingDirectory, Virtualenv Python path (/home/ubuntu/ai_kiosk/bin/python), User/Group, Restart=always/on-failure, coexistence with vllm.service and audio-kiosk.service.
4. Acceptance & Verification Test Scripts Specification:
   - Automated simulated audio playback test script (uploading WAV files, measuring latencies, asserting transcription and translation correctness).

OUTPUT:
Write your detailed specifications to: c:\Work\.agents\spec_miner_survey_1\spec.md
Write your self-contained handoff report to: c:\Work\.agents\spec_miner_survey_1\handoff.md
Update progress.md in your working directory.
When finished, send a completion message back to parent (conversation ID: b3de212b-0da8-4b8d-86d2-e992e6f845f2) with a summary and the path to your handoff.md.
</USER_REQUEST>
