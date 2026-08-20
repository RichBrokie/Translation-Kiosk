# Comprehensive VM Environment & Audio Assets Investigation Report

**Date**: 2026-08-19  
**Target Environment**: Ubuntu 26.04 LTS (x86_64 Linux 7.0.0-29-generic)  
**Host IP**: `100.109.43.41`  
**Investigator Agent**: `explorer_vm_env_2`  
**Parent Orchestrator**: `cb00708b-db7f-4135-a44f-23edaa12c161`  
**Milestone**: `M_E2E_1: Survey & Test Infrastructure Specification`  

---

## Executive Summary

The remote virtual machine environment at `100.109.43.41` has been thoroughly cataloged and verified. The VM hosts an NVIDIA RTX 6000 Ada Generation GPU (48 GB VRAM), dual AI services (`vllm.service` on port 8000 and `audio-kiosk.service` on port 8001), and a comprehensive multilingual natural speech corpus consisting of **140 full-length TED Talk WAV audio files** (over **34 hours** total duration) across **14 distinct world languages**, accompanied by **105 matching SRT subtitle transcript files**.

The target deployment folder `/home/ubuntu/translation_kiosk` exists with full `ubuntu:ubuntu` read/write/execute permissions (0775), port `8080` is completely available, and the Python 3.14 virtual environment at `/home/ubuntu/ai_kiosk` possesses all core runtime libraries (FastAPI, Uvicorn, Pydantic, HTTPX, WebSockets, Faster-Whisper, PyTorch, SciPy, Torchaudio, vLLM, OpenAI SDK) with full PyPI connectivity to install `pytest`, `pytest-asyncio`, and `soundfile` as needed.

---

## 1. Directory Structure Analysis

### 1.1 `/mnt/` and Mount Architecture
- **Mount Point**: `/mnt/models` mounted on `/dev/sdb1`
- **Filesystem Capacity**: 3.5 TB Total | 254 GB Used (8%) | 3.3 TB Available
- **Root Filesystem (`/dev/sda2`)**: 124 GB Total | 34 GB Used (29%) | 84 GB Available
- **Root `/mnt/` permissions**: `drwxr-xr-x` (`root:root`)

### 1.2 `/mnt/models/` Directory Layout
The `/mnt/models/` directory (mode `drwxrwxrwx`, owner `ubuntu:ubuntu`) contains:

```
/mnt/models/
├── Bengali Talks/              # 10 WAV files, 2 SRT files (~2h 45m)
├── Dr Rabba Abduk/             # Medical lecture slides (PDF), recorded sessions (.mp4/.mkv/.mov)
├── English Talks/              # 10 WAV files, 10 SRT files (~2h 11m)
├── French Talks/               # 10 WAV files, 11 SRT files (~2h 31m)
├── German Talks/               # 10 WAV files, 8 SRT files (~2h 34m)
├── Hindi Talks/                # 10 WAV files, 4 SRT files (~2h 50m)
├── Indonesian Talks/           # 10 WAV files, 6 SRT files (~2h 29m)
├── Japanese Talks/             # 10 WAV files, 13 SRT files (~2h 21m)
├── Mandarin Chinese Talks/     # 10 WAV files, 12 SRT files (~1h 55m)
├── Portuguese Talks/           # 10 WAV files, 1 SRT file (~2h 46m)
├── Russian Talks/              # 10 WAV files, 10 SRT files (~2h 31m)
├── Spanish Talks/              # 10 WAV files, 10 SRT files (~2h 27m)
├── Standard Arabic Talks/      # 10 WAV files, 11 SRT files (~1h 11m)
├── Turkish Talks/              # 10 WAV files, 6 SRT files (~2h 49m)
├── Urdu Talks/                 # 10 WAV files, 1 SRT file (~2h 50m)
├── gpt-oss-120b/               # MXFP4 quantized GPT-OSS 120B model (60.79 GB)
├── gpt-oss-120b-awq/           # AWQ quantized GPT-OSS 120B model (31.08 GB)
├── pyannote-3.1/               # PyAnnote speaker diarization config & handler
├── qwen2.5-72b-instruct-awq/   # Qwen 2.5 72B AWQ model (38.75 GB, active in vLLM)
├── whisper-large-v3-turbo/     # HuggingFace Safetensors Whisper Large v3 Turbo (1.51 GB)
├── whisper-large-v3-turbo-ct2/ # CTranslate2 Whisper Large v3 Turbo model (1.51 GB, active in audio_server.py)
├── ubuntu-26.04-desktop-amd64.iso # Ubuntu ISO image (6.52 GB)
├── $RECYCLE.BIN/               # Windows recycle bin folder (16 deleted talk audio/srt files)
└── System Volume Information/  # NTFS volume metadata
```

### 1.3 `/home/ubuntu/` Directory Layout
The user home directory contains:

```
/home/ubuntu/
├── ai_kiosk/                   # Python 3.14 virtualenv with CUDA 13.0 PyTorch & vLLM
├── audio_server.py             # Faster-Whisper ASR FastAPI service script (port 8001)
├── translation_kiosk/          # Dedicated directory for Translation Kiosk application (port 8080)
├── whisper-large-v3-turbo-ct2/ # Local duplicate folder for CT2 Whisper model
├── vllm_error.log              # vLLM log file
├── .cache/, .config/, .local/  # User configuration and cache directories
├── .tilelang/, .triton/, .humming/ # GPU kernel compiler caches
└── Desktop, Documents, Downloads, Music, Pictures, Public, Templates, Videos
```

### 1.4 `/home/ubuntu/translation_kiosk/` Inspection
- **Existence**: Exists (`/home/ubuntu/translation_kiosk`)
- **Permissions**: `drwxrwxr-x` (mode `0775`)
- **Ownership**: `uid=1000 (ubuntu)`, `gid=1000 (ubuntu)`
- **Current State**: Empty directory
- **Access Verification**: Fully readable, writable, and executable by user `ubuntu`.
- **Git Status**: Uninitialized (ready for project scaffolding).

---

## 2. Multilingual Audio Corpus & Asset Catalog

A comprehensive search of the filesystem identified **196 audio files** total. The primary test asset repository is the `/mnt/models/* Talks` directory tree containing **140 natural human speech WAV files** across 14 languages, plus **105 SRT subtitle files**.

### 2.1 Multilingual Talks Summary Table

| # | Language Folder | Lang Code | WAV Count | SRT Count | Total Duration | Sample Rate | Channels | Bit Depth | Total Audio Size |
|---|-----------------|-----------|-----------|-----------|----------------|-------------|----------|-----------|------------------|
| 1 | `Bengali Talks` | `bn` | 10 | 2 | 2h 45m 25s (9,925s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.63 GB |
| 2 | `English Talks` | `en` | 10 | 10 | 2h 11m 10s (7,870s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.29 GB |
| 3 | `French Talks` | `fr` | 10 | 11 | 2h 30m 57s (9,057s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.49 GB |
| 4 | `German Talks` | `de` | 10 | 8 | 2h 34m 19s (9,259s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.52 GB |
| 5 | `Hindi Talks` | `hi` | 10 | 4 | 2h 49m 32s (10,172s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.67 GB |
| 6 | `Indonesian Talks` | `id` | 10 | 6 | 2h 29m 06s (8,946s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.47 GB |
| 7 | `Japanese Talks` | `ja` | 10 | 13 | 2h 21m 14s (8,474s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.39 GB |
| 8 | `Mandarin Chinese Talks` | `zh` | 10 | 12 | 1h 55m 04s (6,904s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.13 GB |
| 9 | `Portuguese Talks` | `pt` | 10 | 1 | 2h 45m 58s (9,958s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.64 GB |
| 10 | `Russian Talks` | `ru` | 10 | 10 | 2h 30m 45s (9,045s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.49 GB |
| 11 | `Spanish Talks` | `es` | 10 | 10 | 2h 26m 54s (8,814s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.45 GB |
| 12 | `Standard Arabic Talks` | `ar` | 10 | 11 | 1h 11m 05s (4,265s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 0.70 GB |
| 13 | `Turkish Talks` | `tr` | 10 | 6 | 2h 48m 39s (10,119s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.66 GB |
| 14 | `Urdu Talks` | `ur` | 10 | 1 | 2h 50m 07s (10,207s) | 44,100 Hz | 2 (Stereo) | 16-bit PCM | 1.68 GB |
| **TOTAL** | **14 Languages** | — | **140 WAVs** | **105 SRTs** | **34h 10m 22s** | **44,100 Hz** | **2 (Stereo)** | **16-bit PCM** | **20.21 GB** |

### 2.2 Audio Format Specifications & Conversion Needs
- **Raw File Properties**: All 140 talk files are formatted as `RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, stereo 44100 Hz`.
- **Kiosk Processing Expectation**: The Translation Kiosk pipeline (`audio_pipeline.py`) accepts 16,000 Hz (16 kHz), 16-bit little-endian, mono PCM audio.
- **Conversion Utility in Python**: Python's built-in `scipy.signal.resample` / `scipy.io.wavfile` or `ffmpeg` / `torchaudio` can resample 44.1kHz stereo to 16kHz mono in memory in <15ms without disk overhead.

### 2.3 Sample Audio Assets Per Language (Selected Examples)

1. **English (`en`)**:
   - `English Talks/The secrets of learning a new language ｜ Lýdia Machová ｜ TED.wav` (10m 45s, 108.58 MB) — Matching `.en.srt`
   - `English Talks/How to speak so that people want to listen ｜ Julian Treasure ｜ TED.wav` (9m 58s, 100.73 MB) — Matching `.en.srt`
2. **Spanish (`es`)**:
   - `Spanish Talks/Canaliza tu energía y termina tus proyectos ｜ Stephie Flechas ｜ TEDxColegioSanMateo.wav` (12m 12s, 123.30 MB) — Matching `.es.srt`
   - `Spanish Talks/Dime cómo hablas y te diré quién eres ｜ Jousin Palafox ｜ TEDxTijuana.wav` (13m 06s, 132.35 MB) — Matching `.es.srt`
3. **French (`fr`)**:
   - `French Talks/Choisir sa vie plutôt que la subir ｜ Yann DELPLANQUE ｜ TEDxNeoma BS Paris.wav` (12m 55s, 130.43 MB) — Matching `.fr.srt` and `.en.srt`
   - `French Talks/Transformer le négatif en positif ｜ Christophe Haag ｜ TEDxEMLYON.wav` (17m 40s, 178.43 MB) — Matching `.fr.srt` and `.en.srt`
4. **German (`de`)**:
   - `German Talks/Schluss mit dem Schönheitswahn ｜ Silja Steinbrecher ｜ TEDxUniPotsdam.wav` (13m 22s, 135.03 MB) — Matching `.de.srt` and `.en.srt`
   - `German Talks/Die Kunst der Selbstmotivation ｜ Michael Ehlers ｜ TEDxHHL.wav` (15m 12s, 153.25 MB) — Matching `.de.srt`
5. **Mandarin Chinese (`zh`)**:
   - `Mandarin Chinese Talks/不要被「主流」綁架你的人生 ｜ 萬芳 Wan Fang ｜ TEDxTaipei.wav` (17m 14s, 173.99 MB) — Matching `.zh-TW.srt` and `.en.srt`
   - `Mandarin Chinese Talks/為什麼你該停止追求完美？ ｜ 蘇予昕 ｜ TEDxTaoyuan.wav` (14m 02s, 141.77 MB) — Matching `.zh-TW.srt`
6. **Japanese (`ja`)**:
   - `Japanese Talks/Hope invites ｜ Tsutomu Uematsu ｜ TEDxSapporo.wav` (20m 52s, 210.66 MB) — Matching `.ja.srt` and `.en.srt`
   - `Japanese Talks/The power of pride： George Takei at TEDxKyoto.wav` (17m 13s, 173.91 MB) — Matching `.ja.srt` and `.en.srt`
7. **Russian (`ru`)**:
   - `Russian Talks/Искусство очаровывать незнакомцев ｜ Айнур Зиннатуллин ｜ TEDxBaumanSt.wav` (20m 38s, 208.38 MB) — Matching `.ru.srt`
   - `Russian Talks/Разреши Вселенной сделать тебе хорошо ｜ Татьяна Мужицкая ｜ TEDxNovosibirsk.wav` (22m 15s, 224.72 MB) — Matching `.ru.srt`
8. **Arabic (`ar`)**:
   - `Standard Arabic Talks/العربية فصحى أم لهجات؟ ｜ Safaa Belhasawi ｜ TEDxDoha.wav` (8m 52s, 89.49 MB) — Matching `.ar.srt`
   - `Standard Arabic Talks/صوتك مصدر قوتك ｜ Lubaba Yousef ｜ TEDxQatarUniversity.wav` (13m 14s, 133.69 MB) — Matching `.ar.srt`

### 2.4 Other Audio Files on VM
- `/home/ubuntu/ai_kiosk/lib/python3.14/site-packages/pyannote/audio/sample/sample.wav`: 16kHz mono speech sample (960 KB).
- `/home/ubuntu/ai_kiosk/lib/python3.14/site-packages/scipy/io/tests/data/*.wav`: 23 micro WAV fixtures testing edge cases (corrupt headers, 24-bit, 32-bit float, 64-bit float, RF64, u-law).
- `/tmp/speech_*_4s.wav` and `/tmp/synth_*s.wav`: 16 pre-sliced 16kHz mono WAV benchmark chunks (Spanish, French, German, Japanese, Mandarin, Russian, Arabic, Portuguese, Turkish, English).

---

## 3. Python Environment & System Tools Analysis

### 3.1 Python Runtime Details
- **Interpreter**: `/home/ubuntu/ai_kiosk/bin/python`
- **Version**: Python 3.14.0 (`v3.14.0:ebf928e`, GNU/Linux)
- **Virtualenv Path**: `/home/ubuntu/ai_kiosk`

### 3.2 Key Installed Packages Status

| Category | Package | Version | Status | Notes |
|----------|---------|---------|--------|-------|
| **Web & API** | `fastapi` | 0.136.3 | INSTALLED | Core ASGI web framework |
| | `uvicorn` | 0.52.3 | INSTALLED | ASGI web server (supports `--host 0.0.0.0 --port 8080`) |
| | `starlette` | 1.6.0 | INSTALLED | Underlying ASGI toolkit & WebSocket protocol |
| | `pydantic` | 2.13.4 | INSTALLED | Data validation & schema serialization |
| | `pydantic-settings`| 2.15.0 | INSTALLED | Application environment settings |
| | `python-multipart`| 0.0.32 | INSTALLED | Required for multipart file uploads in FastAPI |
| | `jinja2` | 3.1.6 | INSTALLED | Template engine for `kiosk.html` and `admin.html` |
| **HTTP & WS Clients** | `httpx` | 0.28.1 | INSTALLED | Async HTTP client for Whisper & Qwen APIs |
| | `websockets` | 17.0.1 | INSTALLED | WebSocket client & protocol toolkit |
| | `aiohttp` | 3.14.3 | INSTALLED | High-performance async HTTP client |
| | `requests` | 2.34.2 | INSTALLED | Synchronous HTTP client |
| **Audio & DSP** | `scipy` | 1.18.0 | INSTALLED | Includes `scipy.signal` (resampling) & `scipy.io.wavfile` |
| | `torchaudio` | 2.11.0+cu130 | INSTALLED | PyTorch GPU/CPU audio processing |
| | `wave` | Built-in | INSTALLED | Standard Python RIFF WAV header packager |
| | `faster-whisper` | 1.2.1 | INSTALLED | CTranslate2 Whisper inference library |
| | `soundfile` | — | MISSING | *Optional* (PyPI installable: `pip install soundfile` -> 0.14.0) |
| **AI / LLM** | `openai` | 3.1.0 | INSTALLED | Async client for OpenAI chat completions |
| | `vllm` | 0.27.1 | INSTALLED | High-throughput LLM serving engine |
| | `transformers` | 5.15.0 | INSTALLED | Hugging Face transformer models |
| | `tokenizers` | 0.22.2 | INSTALLED | Fast subword tokenization |
| **Testing & Infra** | `unittest` | Built-in | INSTALLED | Standard test runner |
| | `pytest` | — | MISSING | *Installable*: `pip install pytest pytest-asyncio` -> 9.1.1 |
| | `pytest-asyncio` | — | MISSING | *Installable*: `pip install pytest-asyncio` -> 1.4.0 |
| | `psutil` | 7.2.2 | INSTALLED | System & process resource monitoring |
| | `loguru` | 0.7.3 | INSTALLED | Structured logging |
| | `rich` | 15.0.0 | INSTALLED | Terminal formatting |
| | `prometheus_client`| 0.26.0 | INSTALLED | Prometheus telemetry & metrics |

*Note on Testing Packages*: While `pytest` is not pre-installed in the virtualenv, PyPI connectivity is active and `pip install pytest pytest-asyncio soundfile` succeeded in dry-run simulation. Alternatively, standard library `unittest` + custom async test runners can run with zero extra installs.

### 3.3 System Utilities & Hardware
- **FFmpeg**: `/usr/bin/ffmpeg` (Version `7.1.3-1ubuntu1`, built with libx264, libx265, libopus, libvpx, libmp3lame, libvorbis).
- **FFprobe**: `/usr/bin/ffprobe` (Version `7.1.3-1ubuntu1`).
- **GPU Hardware**: NVIDIA RTX 6000 Ada Generation (49,140 MiB total VRAM, Driver 610.43, CUDA 13.0).
- **CPU / Memory**: 32 vCPUs (AMD EPYC / Intel Xeon equivalent), 128 GB RAM.
- **Systemd**: `systemctl` present and running; user `ubuntu` has `sudo` access.

---

## 4. Pre-existing Backend AI Services Status

| Service Unit | Port | Model / Process | Status | Memory (VRAM / RAM) | P95 Latency (4s chunk) |
|--------------|------|-----------------|--------|---------------------|------------------------|
| `audio-kiosk.service` | `8001` | Faster-Whisper Large v3 Turbo (CT2) | `active (running)` | 2.5 GB VRAM / 2.6 GB RAM | ~350 ms |
| `vllm.service` | `8000` | Qwen 2.5 72B Instruct AWQ (vLLM) | `active (running)` | 43.1 GB VRAM / 44.5 GB RAM | ~3,600 ms |
| `translation-kiosk.service` | `8080` | *Target Application* | `not installed` | Available | Target: <5s Whisper, <8s Qwen |

---

## 5. Synthesis & Guidance for E2E Test Strategy

1. **Audio Slicing & Test Harness**:
   - The 140 TED Talk WAV files in `/mnt/models/* Talks` provide rich, natural acoustic material across 14 languages for Tier 1 through Tier 4 testing.
   - A lightweight slicing fixture (`slice_audio(talk_path, start_sec=0, duration_sec=4.0, target_sr=16000)`) can slice exact test segments on the fly using `wave` or `scipy.signal`.
2. **Ground Truth Validation**:
   - The 105 matching `.srt` files provide authoritative human reference transcriptions for measuring Character Error Rate (CER) / Word Error Rate (WER) and confirming the sliding-window correction effect.
3. **Multilingual Coverage**:
   - Tier 4 real-world testing can test at least 8 primary languages: English (`en`), Spanish (`es`), French (`fr`), German (`de`), Mandarin (`zh`), Japanese (`ja`), Russian (`ru`), and Arabic (`ar`).
4. **Package Management**:
   - The implementation/testing agents can run `/home/ubuntu/ai_kiosk/bin/python -m pip install pytest pytest-asyncio soundfile` to enable standard pytest execution, or execute tests using `unittest` and standalone scripts.
