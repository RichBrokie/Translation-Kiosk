# Scope: Milestone 1 — Core Audio Pipeline & API Integrations

## Architecture
- **Audio Buffer**: In-memory PCM rolling buffer handling 16kHz 16-bit mono stream, slicing 4.0s windows with 2.0s stride.
- **WAV Packaging**: Encapsulates raw PCM bytes with valid RIFF/WAV header (16kHz, 16-bit, 1 channel).
- **Text Alignment**: Overlap text reconciliation via SequenceMatcher / Longest Common Subsequence (LCS) to merge window transcripts without duplication or stutter.
- **Whisper Client**: Async HTTP client targeting Faster-Whisper server at `http://localhost:8001/transcribe` with language detection.
- **Qwen Client**: Async HTTP client targeting vLLM Qwen 2.5 72B Instruct server at `http://localhost:8000/v1/chat/completions` with single-call JSON prompt (grammar correction + translation) & English bypass handler.
- **Telemetry**: Step-by-step latency tracking, rolling statistics, and structured logging.
- **Unit Test Suite**: `tests/test_pipeline.py` exercising buffer, alignment, WAV packaging, client mocking, and end-to-end audio pipeline flow.

## Implementation Targets (on VM: /home/ubuntu/translation_kiosk/)
1. `config.py`
2. `audio_pipeline.py`
3. `whisper_client.py`
4. `qwen_client.py`
5. `telemetry.py`
6. `tests/test_pipeline.py`

## Verification Criteria
- Python syntax, imports, and type annotations valid under `/home/ubuntu/ai_kiosk/bin/python`.
- `pytest tests/test_pipeline.py` passes 100% on VM.
- Live connectivity checks to Whisper (8001) and vLLM (8000) pass or gracefully handle service availability with mock fallbacks during tests.
