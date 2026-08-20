# Translation Kiosk — Environment & Runtime Survey Analysis

## Executive Summary

The runtime environment for the **Translation Kiosk** application is an Ubuntu 26.04 LTS VM with an NVIDIA RTX 6000 Ada Generation GPU (48 GB VRAM). Both required backend AI services (`vllm.service` running Qwen 2.5 72B Instruct AWQ on port 8000 and `audio-kiosk.service` running Faster-Whisper Large-v3-Turbo on port 8001) are active, healthy, and accessible locally and over Tailscale. The virtual environment `/home/ubuntu/ai_kiosk` has Python 3.14.4 with all required dependencies (FastAPI, Uvicorn, httpx, aiohttp, websockets, Jinja2, OpenAI SDK) pre-installed. The application working directory `/home/ubuntu/translation_kiosk` has been provisioned.

---

## 1. Host and VM Access Architecture

### 1.1 Host Environment (Windows)
- **OS**: Windows 11 / Server x64
- **Working Root**: `C:\Work`
- **Tailscale IP**: `100.73.107.116`
- **Local Network IP**: `172.16.3.134`
- **SSH Tools**:
  - `plink.exe` at `C:\Work\plink.exe` (PuTTY CLI)
  - `OpenSSH` at `C:\windows\System32\OpenSSH\ssh.exe`
- **WSL Status**: Not installed on host. All Linux execution is performed on the remote Ubuntu VM.

### 1.2 Ubuntu VM Environment
- **Tailscale IP**: `100.109.43.41`
- **Internal IP**: `192.168.200.2` (`eth0`)
- **SSH User**: `ubuntu`
- **SSH Password**: `Metropolis0!`
- **Hostkey**: `SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM`
- **Sudo Access**: `(ALL : ALL) ALL`

### 1.3 Recommended Execution Command Pattern
From Windows PowerShell/CMD to execute commands on the Ubuntu VM:
```powershell
c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "<command>"
```

---

## 2. Hardware and Operating System Specifications

| Component | Specification | Notes |
|---|---|---|
| **OS Distribution** | Ubuntu 26.04 LTS (Resolute Raccoon) | Linux kernel 7.0.0-14-generic x86_64 |
| **GPU** | NVIDIA RTX 6000 Ada Generation | 48 GB GDDR6 ECC VRAM (49,140 MiB total) |
| **NVIDIA Driver** | 580.173.02 | CUDA 13.0 support |
| **Current GPU Allocation** | ~45.7 GB allocated / ~3.4 GB free | vLLM: 43.1 GB, Faster-Whisper: 2.5 GB |
| **System Storage** | `/dev/sda2`: 124 GB (84 GB available) | Root filesystem |
| **Model Storage** | `/dev/sdb1`: 3.5 TB mounted at `/mnt/models` | 254 GB used, 3.3 TB available |
| **Python Virtualenv** | `/home/ubuntu/ai_kiosk` | Python 3.14.4 |
| **Target Project Dir** | `/home/ubuntu/translation_kiosk` | Directory created and verified |
| **FFmpeg** | `/usr/bin/ffmpeg` version 8.0.1-3ubuntu2 | Installed and on system PATH |

---

## 3. Pre-Installed Python Virtualenv Packages (`/home/ubuntu/ai_kiosk`)

The virtual environment contains modern, production-grade libraries:
- **Web Frameworks**: `fastapi==0.136.3`, `uvicorn==0.52.3`, `starlette==1.6.0`, `sse-starlette==3.4.8`
- **Async HTTP & WebSockets**: `httpx==0.28.1`, `aiohttp==3.14.3`, `websockets==17.0.1`
- **LLM & ASR**: `openai==3.1.0`, `faster-whisper==1.3.1`, `vllm==0.27.1`, `transformers==5.15.0`, `torchaudio==2.11.0`
- **Data & Templates**: `pydantic==2.13.4`, `pydantic-settings==2.15.0`, `Jinja2==3.1.6`, `numpy==2.4.6`
- **Utilities**: `python-multipart==0.0.32`, `requests==2.34.2`

---

## 4. Backend AI Service Endpoints & Validation

### 4.1 Faster-Whisper ASR Service
- **Service Name**: `audio-kiosk.service`
- **Unit File**: `/etc/systemd/system/audio-kiosk.service`
- **Script**: `/home/ubuntu/audio_server.py`
- **Model Path**: `/mnt/models/whisper-large-v3-turbo-ct2` (device: `cuda`, compute_type: `float16`)
- **Port**: `8001` (bound to `0.0.0.0:8001`)
- **Endpoint**: `POST http://localhost:8001/transcribe`
- **Input**: `multipart/form-data` with field `file` containing raw WAV audio.
- **Output Schema**:
  ```json
  {
    "text": " En la planta baja del Museo de las Cosas que se quedaron a medias podrán encontrar nuestra colección.",
    "language": "es"
  }
  ```
- **Benchmark Observation**:
  - 5-second audio transcription took **0.536s**.
  - Returned correct transcription and language code (`es`, `en`, etc.).

### 4.2 vLLM OpenAI-Compatible Inference Server (Qwen 2.5 72B AWQ)
- **Service Name**: `vllm.service`
- **Unit File**: `/etc/systemd/system/vllm.service`
- **Exec Command**:
  ```bash
  /home/ubuntu/ai_kiosk/bin/python -m vllm.entrypoints.openai.api_server \
    --model /mnt/models/qwen2.5-72b-instruct-awq \
    --quantization awq \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096 \
    --enforce-eager \
    --gpu-memory-utilization 0.88
  ```
- **Port**: `8000` (bound to `0.0.0.0:8000`)
- **Model ID**: `/mnt/models/qwen2.5-72b-instruct-awq`
- **Endpoint**: `POST http://localhost:8000/v1/chat/completions`
- **Standard Request Body**:
  ```json
  {
    "model": "/mnt/models/qwen2.5-72b-instruct-awq",
    "messages": [
      {
        "role": "system",
        "content": "You are a real-time speech translation assistant. Correct any minor transcription errors in the source text and translate it accurately and naturally into English. Return ONLY the English translation."
      },
      {
        "role": "user",
        "content": "En la planta baja del Museo de las Cosas que se quedaron a medias podrán encontrar nuestra colección."
      }
    ],
    "temperature": 0.2,
    "max_tokens": 128
  }
  ```
- **Output Schema**: Standard OpenAI format (`choices[0].message.content`).
- **Benchmark Observation**:
  - Non-streaming latency: **1.760s**
  - Streaming latency (`stream: true`): **Time to First Token: 0.208s**, Total generation: **1.408s**
  - Quality: Accurate contextual correction and translation:
    `"On the ground floor of the Museum of Things Left Halfway, you can find our collection."`

---

## 5. Port Bindings & Network Topology

| Port | Service | Process / Binding | Access Scope |
|---|---|---|---|
| `22` | OpenSSH Server | `sshd` on `0.0.0.0:22` | Host & Remote |
| `8000` | Qwen 2.5 72B vLLM | `python` on `0.0.0.0:8000` | Host & VM Internal |
| `8001` | Faster-Whisper ASR | `python` on `0.0.0.0:8001` | Host & VM Internal |
| `11434` | Ollama | `ollama` on `127.0.0.1:11434` | VM Local only |
| `8080` | **Translation Kiosk** *(Target)* | Unbound / Free for deployment | Target `0.0.0.0:8080` |

---

## 6. Test Datasets & Audio Assets Available On-Disk

In `/mnt/models/`, complete multilingual TED talk audio files (`.wav`) and synchronized ground-truth subtitles (`.srt`) are present:
- `English Talks/` (`A Simple Way to Break a Bad Habit`, `After watching this, your brain will not be the same`, `How to Make Learning as Addictive as Social Media`)
- `Spanish Talks/` (`Canaliza tu energía y termina tus proyectos`, `Cómo conocer a alguien en 30 segundos`, `Cómo hablar`)
- Additional languages: `French Talks/`, `German Talks/`, `Standard Arabic Talks/`, `Urdu Talks/`, `Hindi Talks/`, `Mandarin Chinese Talks/`, `Japanese Talks/`, `Russian Talks/`, `Portuguese Talks/`, `Turkish Talks/`, `Indonesian Talks/`, `Bengali Talks/`.

These files provide ideal test fixtures for the sliding-window chunk simulation test suite.

---

## 7. Operational Recommendations for Pipeline & Deployment

1. **Backend Architecture**:
   - Use FastAPI + Uvicorn binding to `0.0.0.0:8080`.
   - Utilize async `httpx.AsyncClient` for high-concurrency non-blocking calls to `http://127.0.0.1:8001/transcribe` and `http://127.0.0.1:8000/v1/chat/completions`.
   - WebSocket endpoint (e.g. `/ws/audio`) for streaming client microphone chunks from the browser.
   - Server-Sent Events (SSE) or WebSockets for pushing real-time transcription and translation to Kiosk (`/`) and Admin (`/admin`).
2. **Sliding-Window Correction Logic**:
   - Buffer incoming audio chunks (e.g., 2.0–3.0s new chunk + 1.0–2.0s overlap from previous buffer).
   - Audio concatenation/slicing in memory using Python standard `wave` module or `ffmpeg` / `pydub` / `numpy`.
   - Send sliding-window audio to Whisper -> extract current window text.
   - Text reconciliation: Combine recent transcribed tokens, send prompt to Qwen 72B for grammar refinement + translation in one pass.
   - Language bypass: If Whisper detects `en` (English), skip Qwen translation step and output transcription directly (per R4).
3. **Deployment**:
   - Systemd unit `/etc/systemd/system/translation-kiosk.service` with `User=ubuntu`, `WorkingDirectory=/home/ubuntu/translation_kiosk`, `ExecStart=/home/ubuntu/ai_kiosk/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080`, `Restart=on-failure`.
