# Handoff Report — Backend API Services Investigation

**Agent**: `explorer_api_services`  
**Milestone**: `orch_e2e_tests / survey`  
**Target Environment**: Ubuntu 26.04 VM (`100.109.43.41`)  
**Date**: 2026-08-19  

---

## 1. Observation

1. **System Services & Listening Ports**:
   - `systemctl status audio-kiosk.service`: Loaded and active (running) with PID 2053 (`/home/ubuntu/ai_kiosk/bin/python /home/ubuntu/audio_server.py`), listening on `0.0.0.0:8001`.
   - `systemctl status vllm.service`: Loaded and active (running) with PID 2071 (`vllm.entrypoints.openai.api_server --model /mnt/models/qwen2.5-72b-instruct-awq --quantization awq --host 0.0.0.0 --port 8000 --max-model-len 4096 --enforce-eager --gpu-memory-utilization 0.88`), listening on `0.0.0.0:8000`.
   - `ss -tulpn | grep 8080`: No process is listening on port `8080`.
   - `systemctl is-active translation-kiosk.service`: Output is `inactive`.

2. **Faster-Whisper ASR Service (`:8001/transcribe`)**:
   - Inspecting `/home/ubuntu/audio_server.py`:
     ```python
     whisper_model = WhisperModel("/mnt/models/whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")
     @app.post("/transcribe")
     async def transcribe(file: UploadFile = File(...)):
         ...
         return {"text": text, "language": info.language}
     ```
   - Performance on 4.0-second WAV audio chunks:
     - Spanish: Latency = `368.03 ms`, Status = `200`, Payload = `{"text": "podrán encontrar una colección de cartas de amor que jamás se enviaran.", "language": "es"}`
     - French: Latency = `352.03 ms`, Status = `200`, Payload = `{"text": "se trouvait, une personne que je ne voulais pas être.", "language": "fr"}`
     - German: Latency = `377.34 ms`, Status = `200`, Payload = `{"text": "auf der einen Seite oder so ganz hochtabend auf die schönen Künste.", "language": "de"}`
     - Japanese: Latency = `396.16 ms`, Status = `200`, Payload = `{"text": "皆さんに時間を借りてお話を聞いてもらえます それは思うは真似口お話です", "language": "ja"}`
     - English: Latency = `320.37 ms`, Status = `200`, Payload = `{"text": "Sounded simple enough.  Yet I'd sit ...", "language": "en"}`
   - Edge Cases:
     - 0-byte file: Status `500` (Internal Server Error) in 14.12 ms.
     - Missing `file` form-data key: Status `422` (Unprocessable Entity).

3. **vLLM Qwen 2.5 72B Instruct AWQ (`:8000/v1/chat/completions`)**:
   - `GET http://localhost:8000/v1/models`: Status `200`, Model ID = `"/mnt/models/qwen2.5-72b-instruct-awq"`.
   - Single-call post-correction + English translation with `response_format: {"type": "json_object"}`:
     - Spanish (`es`): Latency = `3984.36 ms`, Tokens = `212` (Prompt: 161, Comp: 51). Output = `{"corrected_text": "En el segundo piso, de las cosas que se quedan a medias, podrán encontrar", "english_translation": "On the second floor, you will find things that were left unfinished."}`
     - French (`fr`): Latency = `4292.09 ms`, Tokens = `218` (Prompt: 162, Comp: 56). Output = `{"corrected_text": "ne s'est jamais donné les moyens de ses ambitions, un homme qui s'est oublié", "english_translation": "has never given himself the means to achieve his ambitions, a man who has forgotten himself"}`
     - German (`de`): Latency = `3183.75 ms`, Tokens = `199` (Prompt: 158, Comp: 41). Output = `{"corrected_text": "Weil es oft leider reduziert wird auf attraktive Menschen", "english_translation": "Because it is often unfortunately reduced to attractive people"}`
     - Japanese (`ja`): Latency = `3521.72 ms`, Tokens = `205` (Prompt: 158, Comp: 47). Output = `{"corrected_text": "美術館へようこそ。本日の特別展をご案内いたします。", "english_translation": "Welcome to the museum. I will guide you through today's special exhibition."}`
     - Mandarin (`zh`): Latency = `3657.89 ms`, Tokens = `203` (Prompt: 155, Comp: 48). Output = `{"corrected_text": "欢迎来到自然历史博物馆。今天，我们将探索古代恐龙的世界。", "english_translation": "Welcome to the Natural History Museum. Today, we will explore the world of ancient dinosaurs."}`
     - Russian (`ru`): Latency = `3388.99 ms`, Tokens = `205` (Prompt: 161, Comp: 44). Output = `{"corrected_text": "Добро пожаловать в наш музей науки и технологий", "english_translation": "Welcome to our museum of science and technology"}`
     - Arabic (`ar`): Latency = `3636.67 ms`, Tokens = `213` (Prompt: 164, Comp: 49). Output = `{"corrected_text": "صباح الخير ومرحباً بكم في متحف الفنون الجميلة", "english_translation": "Good morning and welcome to the Museum of Fine Arts"}`
     - English typo correction (`en`): Latency = `3710.76 ms`, Tokens = `216` (Prompt: 166, Comp: 50). Output = `{"corrected_text": "I want to welcome you to our museum of modern art. Today we see paintings.", "english_translation": "I want to welcome you to our museum of modern art. Today we see paintings."}`

4. **Resource Utilization**:
   - `nvidia-smi`: Total VRAM utilized is `45737MiB / 49140MiB` on NVIDIA RTX 6000 Ada (`vllm.service` = 43150 MiB, `audio-kiosk.service` = 2556 MiB). GPU temperature is `39°C`.

---

## 2. Logic Chain

1. From Observation 1 & 2: `audio-kiosk.service` is continuously running and accepts multipart POST requests to `:8001/transcribe`. Its response latency of ~320–396 ms for 4-second audio chunks is well within the 5,000 ms acceptance threshold.
2. From Observation 3: `vllm.service` operates as a fully compliant OpenAI-compatible API on `:8000/v1/chat/completions`. Combined correction and translation runs with structured JSON output within ~3.1–4.3 seconds, safely under the 8,000 ms acceptance requirement.
3. From Observation 1: Port `8080` is unbound, confirming that the new Translation Kiosk application can bind to `0.0.0.0:8080` without encountering port collisions or needing existing services stopped.
4. From Observation 4: GPU memory allocation is stable at 45.7 GB out of 48 GB. Both services run concurrently on the single RTX 6000 Ada GPU without OOM errors.
5. From Observation 2 (Edge Cases): Empty/0-byte audio chunks trigger HTTP 500 in `audio_server.py`. Therefore, the `audio_pipeline.py` buffer manager must include client-side validation to drop or pad 0-byte/sub-chunk buffers before calling Whisper.
6. From Observation 3 (English test): Bypassing Qwen when Whisper returns `language: "en"` saves ~3,700 ms per chunk, providing sub-500ms end-to-end latency for English speakers.

---

## 3. Caveats

- **No concurrent load tested**: Single-stream sequential requests were benchmarked. Under heavy concurrent kiosk sessions, vLLM batching throughput will increase total queue latency.
- **Microphone Hardware**: Audio testing used sliced real-world TED Talk WAV files from `/mnt/models/* Talks/` and synthetic sine waves; browser WebRTC / AudioWorklet input was simulated via WAV byte streams.

---

## 4. Conclusion

The remote environment is completely ready for development, testing, and deployment:
1. **Whisper ASR (`http://localhost:8001/transcribe`)**: Active, compliant, ~350ms latency for 4s chunks.
2. **Qwen 2.5 72B AWQ (`http://localhost:8000/v1/chat/completions`)**: Active, compliant, supports JSON output, ~3.5s latency per translation call.
3. **Port 8080**: Available for `translation-kiosk.service`.
4. Detailed investigation report and benchmark data are saved to `c:\Work\.agents\orch_e2e_tests\explorer_api_services\report.md`.

---

## 5. Verification Method

To independently verify these findings, execute the following commands on the remote VM:
```bash
# 1. Verify service statuses
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "systemctl is-active audio-kiosk.service vllm.service; ss -tulpn | grep -E '8000|8001|8080'"

# 2. Inspect recorded benchmark results
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "cat /tmp/api_investigation_results.json"
```
