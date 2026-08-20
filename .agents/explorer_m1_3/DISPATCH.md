## 2026-08-19T09:13:25Z
You are explorer_m1_3 (Client & Test Strategy Explorer) for Milestone 1 of the Translation Kiosk project.
Your working directory is: c:\Work\.agents\explorer_m1_3

MANDATORY INPUTS TO READ:
- Authoritative User Request: c:\Work\.agents\ORIGINAL_REQUEST.md
- Master Project Specification: c:\Work\PROJECT.md
- Milestone 1 Scope: c:\Work\.agents\sub_orch_m1\SCOPE.md
- Explorer Hand-offs:
  - c:\Work\.agents\explorer_survey_1\handoff.md
  - c:\Work\.agents\explorer_survey_2\handoff.md

TASK & OBJECTIVE:
Analyze and design the HTTP clients (`whisper_client.py`, `qwen_client.py`), telemetry system (`telemetry.py`), and comprehensive unit test suite (`tests/test_pipeline.py`):
1. `whisper_client.py` Design:
   - Async client (`httpx.AsyncClient`) calling Faster-Whisper at `http://localhost:8001/transcribe`.
   - Data structures (dataclass / Pydantic) for TranscriptionResult (text, language, language_prob, duration, segments, latency_ms).
   - Timeout and connection pooling configurations, error handling & retries.
2. `qwen_client.py` Design:
   - Async client calling vLLM Qwen 2.5 72B Instruct at `http://localhost:8000/v1/chat/completions`.
   - Single-call structured JSON prompt design: instruct model to correct ASR grammar and translate to English (and target language) in a single turn.
   - English bypass logic: if detected language is 'en', skip full translation pipeline or run minimal grammar polish.
   - Robust JSON parser that handles code fence blocks (```json ... ```) or plain text fallbacks.
3. `telemetry.py` Design:
   - Real-time latency tracking: ASR latency, LLM latency, chunk processing time, end-to-end latency.
   - Aggregated metrics (rolling averages, p50, p95, min, max, total tokens, error count).
4. `tests/test_pipeline.py` Strategy:
   - Unit tests covering:
     a) PCM buffer accumulation, window slicing, stride math, overflow/underflow.
     b) RIFF WAV binary header validity (checking 44-byte header, sample rate, channels).
     c) SequenceMatcher / LCS text alignment with synthetic overlapping sentences, partial words, duplicate phrases, punctuation mismatch.
     d) Whisper client with mock HTTP responses (200 OK, 500 error, network timeout).
     e) Qwen client with mock chat completions (valid JSON, markdown wrapped JSON, malformed response, English bypass).
     f) Telemetry recording and stats computation.
     g) Integration test running synthetic audio through buffer -> mock whisper -> mock qwen -> alignment -> telemetry.

Write your detailed design and test plan to: `c:\Work\.agents\explorer_m1_3\handoff.md`.
Use `send_message` to notify caller (ID: da36c33c-618d-4a51-81f7-80e99cb0754e) when done.
