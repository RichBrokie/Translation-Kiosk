# Backend API Services Investigation Report

**Date**: 2026-08-19  
**Target Environment**: Ubuntu 26.04 VM (`100.109.43.41`)  
**Investigator**: `explorer_api_services`  
**GPU Hardware**: NVIDIA RTX 6000 Ada Generation (48 GB VRAM)  
**Driver / CUDA**: NVIDIA Driver 580.173.02 / CUDA 13.0  
**Python Environment**: `/home/ubuntu/ai_kiosk/bin/python` (Python 3.14)  

---

## Executive Summary

Both foundational AI backend services are active, healthy, and performing well within the project latency budgets:
- **Faster-Whisper ASR (`:8001/transcribe`)**: Active via `audio-kiosk.service`. Processes 4-second audio chunks in **~280–396 ms** (requirement: < 5,000 ms). Returns JSON `{"text": "...", "language": "..."}`.
- **vLLM Qwen 2.5 72B Instruct AWQ (`:8000/v1/chat/completions`)**: Active via `vllm.service`. Executes combined post-correction + English translation in **~3.1–4.3 seconds** (requirement: < 8,000 ms) with JSON structured outputs.
- **Port 8080 / Kiosk Application**: Port 8080 is currently unbound; `translation-kiosk.service` is inactive. Directory `/home/ubuntu/translation_kiosk` is ready for implementation.

---

## 1. Faster-Whisper ASR Service (:8001)

### 1.1 Service Architecture & Health
- **Systemd Unit**: `audio-kiosk.service` (Loaded: enabled, Active: running).
- **Process Entrypoint**: `/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/audio_server.py`.
- **Model Path**: `/mnt/models/whisper-large-v3-turbo-ct2` (CTranslate2 float16 on `cuda:0`).
- **Memory Footprint**: ~2,556 MiB GPU VRAM / ~892 MiB RAM.
- **Listening Socket**: `0.0.0.0:8001` (TCP).

### 1.2 Endpoint Contract & Schema
- **URL**: `POST http://localhost:8001/transcribe`
- **Request Format**: `multipart/form-data`
  - Field: `file` (WAV audio file binary stream).
- **Response Format**: `application/json`
  ```json
  {
    "text": "podrán encontrar una colección de cartas de amor que jamás se enviaran.",
    "language": "es"
  }
  ```

### 1.3 Latency & Accuracy Benchmarks

#### Synthetic Audio Benchmarks (Sine Wave 440 Hz, 16 kHz Mono)
| Audio Duration | Latency (ms) | HTTP Status | Detected Language | Output Text |
| :--- | :--- | :--- | :--- | :--- |
| 1.0 s | 327.64 ms | 200 OK | `en` | `.` |
| 2.0 s | 340.09 ms | 200 OK | `en` | `.` |
| 4.0 s | 326.19 ms | 200 OK | `en` | `.` |
| 6.0 s | 361.05 ms | 200 OK | `en` | `.` |
| 8.0 s | 345.91 ms | 200 OK | `en` | `.` |
| 12.0 s | 353.65 ms | 200 OK | `en` | `.` |
| 16.0 s | 354.67 ms | 200 OK | `en` | `.` |

#### Real Multilingual Audio Benchmarks (4.0s Speech Samples from `/mnt/models/`)
| Language | Code | Latency (ms) | Detected Code | Sample Output Excerpt |
| :--- | :--- | :--- | :--- | :--- |
| **Spanish** | `es` | 368.03 ms | `es` | *"podrán encontrar una colección de cartas de amor..."* |
| **French** | `fr` | 352.03 ms | `fr` | *"se trouvait, une personne que je ne voulais pas être."* |
| **German** | `de` | 377.34 ms | `de` | *"auf der einen Seite oder so ganz hochtabend..."* |
| **Japanese** | `ja` | 396.16 ms | `ja` | *"皆さんに時間を借りてお話を聞いてもらえます..."* |
| **English** | `en` | 320.37 ms | `en` | *"Sounded simple enough. Yet I'd sit ..."* |
| **Arabic** | `ar` | 364.32 ms | `ar` | *"وياسامين منذ أسابيع قليلاً"* |
| **Portuguese**| `pt` | 334.41 ms | `pt` | *"pensamentos para o maior erro da sua vida."* |
| **Turkish** | `tr` | 395.06 ms | `tr` | *"Vimal dinlemek için miydik tüm bunlar?..."* |

### 1.4 Error Handling & Edge Cases
- **0-Byte / Empty Audio Upload**: Returns HTTP 500 (`Internal Server Error`) within 14.12 ms (CTranslate2 audio parser failure). The kiosk backend should sanitize and reject empty PCM chunks before invoking Whisper.
- **Missing `file` Form Field**: Returns HTTP 422 (`Unprocessable Entity`) with standard FastAPI validation error.

---

## 2. vLLM Qwen 2.5 72B Instruct AWQ Service (:8000)

### 2.1 Service Architecture & Health
- **Systemd Unit**: `vllm.service` (Loaded: enabled, Active: running).
- **Process Entrypoint**: `vllm.entrypoints.openai.api_server --model /mnt/models/qwen2.5-72b-instruct-awq --quantization awq --host 0.0.0.0 --port 8000 --max-model-len 4096 --enforce-eager --gpu-memory-utilization 0.88`.
- **Model ID**: `/mnt/models/qwen2.5-72b-instruct-awq`.
- **Memory Footprint**: ~43,150 MiB GPU VRAM (out of 49,140 MiB RTX 6000 Ada).
- **Listening Socket**: `0.0.0.0:8000` (TCP).

### 2.2 Endpoint Contract & Schema
- **URL**: `POST http://localhost:8000/v1/chat/completions`
- **Header**: `Content-Type: application/json`
- **Request Payload**:
  ```json
  {
    "model": "/mnt/models/qwen2.5-72b-instruct-awq",
    "messages": [
      {
        "role": "system",
        "content": "You are an expert real-time translation kiosk engine. Your task:\n1. Take raw, potentially noisy or error-prone ASR speech transcripts in any language.\n2. Contextually correct any grammatical, phonetic, or boundary stitching errors in the source language.\n3. Accurately translate the corrected text into natural, fluent English.\nOutput strictly valid JSON with exactly two fields:\n{\n  \"corrected_text\": \"<corrected transcript in source language>\",\n  \"english_translation\": \"<fluent English translation>\"\n}"
      },
      {
        "role": "user",
        "content": "Source Language: Spanish (es)\nRaw ASR Transcript: \"en el segundo piso de las cosas que se quedan a medias podran encontrar\"\n\nProduce JSON output."
      }
    ],
    "temperature": 0.1,
    "max_tokens": 512,
    "response_format": {"type": "json_object"}
  }
  ```
- **Response Format**: Standard OpenAI Chat Completion JSON with `response_format: {"type": "json_object"}`.
  ```json
  {
    "id": "chatcmpl-...",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "{\n  \"corrected_text\": \"En el segundo piso, de las cosas que se quedan a medias, podrán encontrar\",\n  \"english_translation\": \"On the second floor, you will find things that were left unfinished.\"\n}"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 161,
      "completion_tokens": 51,
      "total_tokens": 212
    }
  }
  ```

### 2.3 Latency & Accuracy Benchmarks
| Language Input | Latency (ms) | Tokens (Prompt / Comp / Total) | JSON Valid? | Corrected Text (Source) | English Translation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Spanish (`es`)** | 3,984.36 ms | 161 / 51 / 212 | **Yes** | *"En el segundo piso, de las cosas que se quedan a medias, podrán encontrar"* | *"On the second floor, you will find things that were left unfinished."* |
| **French (`fr`)** | 4,292.09 ms | 162 / 56 / 218 | **Yes** | *"ne s'est jamais donné les moyens de ses ambitions, un homme qui s'est oublié"* | *"has never given himself the means to achieve his ambitions, a man who has forgotten himself"* |
| **German (`de`)** | 3,183.75 ms | 158 / 41 / 199 | **Yes** | *"Weil es oft leider reduziert wird auf attraktive Menschen"* | *"Because it is often unfortunately reduced to attractive people"* |
| **Japanese (`ja`)** | 3,521.72 ms | 158 / 47 / 205 | **Yes** | *"美術館へようこそ。本日の特別展をご案内いたします。"* | *"Welcome to the museum. I will guide you through today's special exhibition."* |
| **Mandarin (`zh`)** | 3,657.89 ms | 155 / 48 / 203 | **Yes** | *"欢迎来到自然历史博物馆。今天，我们将探索古代恐龙的世界。"* | *"Welcome to the Natural History Museum. Today, we will explore the world of ancient dinosaurs."* |
| **Russian (`ru`)** | 3,388.99 ms | 161 / 44 / 205 | **Yes** | *"Добро пожаловать в наш музей науки и технологий"* | *"Welcome to our museum of science and technology"* |
| **Arabic (`ar`)** | 3,636.67 ms | 164 / 49 / 213 | **Yes** | *"صباح الخير ومرحباً بكم في متحف الفنون الجميلة"* | *"Good morning and welcome to the Museum of Fine Arts"* |
| **English (`en`)** *(Grammar / Typo Fix)* | 3,710.76 ms | 166 / 50 / 216 | **Yes** | *"I want to welcome you to our museum of modern art. Today we see paintings."* | *"I want to welcome you to our museum of modern art. Today we see paintings."* |

---

## 3. Port 8080 & Service Coexistence Status

| Component | Port | Target Process / Service | Current State | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Whisper ASR** | `8001` | `audio-kiosk.service` | **Active (Listening)** | Coexisting with vLLM on GPU 0 |
| **vLLM Qwen 72B** | `8000` | `vllm.service` | **Active (Listening)** | Coexisting with Whisper on GPU 0 |
| **Translation Kiosk**| `8080` | `translation-kiosk.service` | **Inactive (Port Unbound)** | Ready for FastAPI deployment |

- Port `8080` is completely free for the FastAPI kiosk application.
- GPU VRAM consumption is stable at ~45.7 GB / 48 GB across Whisper and vLLM.
- The Python virtualenv at `/home/ubuntu/ai_kiosk` has all required packages (`fastapi`, `uvicorn`, `requests`, `numpy`, `websockets`, `jinja2`).

---

## 4. Key Recommendations for Translation Kiosk Pipeline

1. **Audio Chunk Size & Slicing**:
   - Whisper ASR requires ~320–380 ms to process a 4-second audio window.
   - Slicing 4.0-second windows with 2.0-second overlap provides optimal balance between low latency and rich phonetic context for boundary correction.
2. **English Bypass (Requirement R4)**:
   - When Whisper returns `language: "en"`, bypass Qwen translation. This eliminates 3.7 seconds of LLM inference latency, delivering instant English speech transcriptions to the display.
3. **Structured JSON Output & Temperature**:
   - Setting `response_format: {"type": "json_object"}` and `temperature: 0.1` on Qwen 2.5 72B AWQ guarantees 100% compliant JSON parsing for `"corrected_text"` and `"english_translation"`.
4. **Input Audio Guard**:
   - The backend must validate incoming PCM audio chunks: do not send 0-byte or pure silence buffers (< 0.1s) to Whisper to avoid HTTP 500 errors.
