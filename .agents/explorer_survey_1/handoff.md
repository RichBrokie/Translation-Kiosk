# Handoff Report — Explorer 1 (Environment & Runtime)

## 1. Observation

Direct observations from tool executions:
- **SSH Connectivity**:
  - Host VM accessible at `100.109.43.41` via PuTTY Plink (`c:\Work\plink.exe`) using user `ubuntu` and password `Metropolis0!`.
  - Hostkey fingerprint: `SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM`.
  - Verified remote OS: Ubuntu 26.04 LTS (`Linux ubuntu-Virtual-Machine 7.0.0-14-generic #14-Ubuntu SMP x86_64`).
- **Hardware & Accelerators**:
  - GPU: NVIDIA RTX 6000 Ada Generation (48 GB GDDR6 VRAM, Driver: 580.173.02, CUDA: 13.0).
  - VRAM state: ~43.1 GB allocated to vLLM, ~2.5 GB allocated to Faster-Whisper, ~3.4 GB free.
- **Python Virtualenv & Tools**:
  - Python virtualenv at `/home/ubuntu/ai_kiosk` (Python 3.14.4).
  - Pre-installed libraries: `fastapi==0.136.3`, `uvicorn==0.52.3`, `httpx==0.28.1`, `aiohttp==3.14.3`, `websockets==17.0.1`, `jinja2==3.1.6`, `openai==3.1.0`, `faster-whisper==1.3.1`, `vllm==0.27.1`.
  - FFmpeg located at `/usr/bin/ffmpeg` (version 8.0.1-3ubuntu2).
  - Project directory `/home/ubuntu/translation_kiosk` created with ownership `ubuntu:ubuntu`.
- **Whisper ASR Service (`audio-kiosk.service`)**:
  - Unit file: `/etc/systemd/system/audio-kiosk.service` running `/home/ubuntu/audio_server.py`.
  - Active status: running (PID 85704), listening on `0.0.0.0:8001`.
  - Tested `POST http://localhost:8001/transcribe` with 5s audio chunk: latency 0.536s, response: `{"text": "...", "language": "es"}`.
- **vLLM Qwen 72B Service (`vllm.service`)**:
  - Unit file: `/etc/systemd/system/vllm.service` running `vllm.entrypoints.openai.api_server` with `--model /mnt/models/qwen2.5-72b-instruct-awq --quantization awq --port 8000 --max-model-len 4096`.
  - Active status: running (PID 83994), listening on `0.0.0.0:8000`.
  - Tested `POST http://localhost:8000/v1/chat/completions`: latency 1.760s (non-streaming), streaming TTFT 0.208s. Output: `"On the ground floor of the Museum of Things Left Halfway, you can find our collection."`
- **Network Ports**:
  - Ports 22 (SSH), 8000 (vLLM), 8001 (ASR) active.
  - Port 8080 is free and available for binding.
- **Audio Datasets**:
  - Located in `/mnt/models/` across 14 language folders (`English Talks/`, `Spanish Talks/`, `French Talks/`, etc.) with paired `.wav` and `.srt` files.

---

## 2. Logic Chain

1. *Observation*: `plink.exe` with `-hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM"` successfully executes remote commands on `100.109.43.41`.
   *Inference*: All implementation, testing, and deployment commands can be orchestrated reliably from Windows via plink.
2. *Observation*: `/home/ubuntu/ai_kiosk` already contains `fastapi`, `uvicorn`, `httpx`, `websockets`, `jinja2`, and `openai`.
   *Inference*: No complex dependency compilation is required; the team can immediately start building the FastAPI application.
3. *Observation*: Whisper ASR and Qwen 72B respond within 0.5s and 0.2s (TTFT streaming) respectively.
   *Inference*: The 5-second transcription latency budget (Acceptance Criteria) and 8-second translation latency budget are readily achievable with asynchronous pipelining.
4. *Observation*: Port 8080 is unbound, and systemd is available with user sudo rights.
   *Inference*: Creating `/etc/systemd/system/translation-kiosk.service` binding to `0.0.0.0:8080` will cleanly fulfill R5 and coexist with existing services without port collisions.

---

## 3. Caveats

- **No Local WSL**: The Windows host does not have WSL. All bash scripts and Python code for the backend must run on the remote VM via plink / SSH.
- **GPU Memory Headroom**: GPU VRAM is ~93% utilized (~45.7 GB of 48 GB) by vLLM (43.1 GB) and Whisper (2.5 GB). The application web server itself must run purely in CPU/RAM mode without attempting to allocate CUDA memory.
- **Model Context Window**: vLLM is configured with `--max-model-len 4096`. Prompts sent for post-correction and translation should remain concise (well within 4096 tokens).

---

## 4. Conclusion

The runtime environment is healthy, operational, and fully prepared for the implementation of the Translation Kiosk application. All necessary prerequisites, GPU services, libraries, audio test fixtures, and network access points have been validated.

---

## 5. Verification Method

To independently verify the environment and services:

1. **Verify SSH Connectivity**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "uptime"
   ```
2. **Verify Systemd Services**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "systemctl is-active vllm.service audio-kiosk.service"
   ```
3. **Verify Whisper ASR API**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "curl -s -F 'file=@/tmp/test_es.wav' http://localhost:8001/transcribe"
   ```
4. **Verify Qwen LLM API**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "curl -s http://localhost:8000/v1/models"
   ```
