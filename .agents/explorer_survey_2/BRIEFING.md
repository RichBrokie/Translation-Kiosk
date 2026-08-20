# BRIEFING — 2026-08-19T09:09:25Z

## Mission
Investigate and design technical architecture for real-time sliding-window audio correction, Whisper/Qwen pipeline, browser audio streaming, and latency optimization.

## 🔒 My Identity
- Archetype: explorer
- Roles: Pipeline & Architecture Explorer
- Working directory: c:\Work\.agents\explorer_survey_2
- Original parent: b3de212b-0da8-4b8d-86d2-e992e6f845f2
- Milestone: Step 0: Survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement in source code
- Strictly respect backend API endpoints: Whisper (POST http://localhost:8001/transcribe) and Qwen (POST http://localhost:8000/v1/chat/completions)
- Meet strict latency targets (<5s speech-to-transcription, <8s speech-to-translation)
- Output structured analysis.md and 5-component handoff.md

## Current Parent
- Conversation ID: b3de212b-0da8-4b8d-86d2-e992e6f845f2
- Updated: 2026-08-19T09:09:25Z

## Investigation State
- **Explored paths**: `c:\Work\.agents\ORIGINAL_REQUEST.md`, `c:\Work\audio_server.py`, `c:\Work\audio-kiosk.service`, `c:\Work\script.sh`, `c:\Work\fix2.sh`, `c:\Work\.agents\orchestrator_1\plan.md`
- **Key findings**: 
  - Complete audio streaming architecture designed: 16kHz mono PCM via AudioWorklet -> WebSocket binary frames -> in-memory WAV packaging.
  - Sliding-window math formalized: $W=4.0\text{s}$, $O=2.0\text{s}$, $H=2.0\text{s}$ (32,000 bytes/sec).
  - Robust word-level SequenceMatcher text alignment algorithm designed to replace tentative tails with re-transcribed overlap text.
  - Qwen 72B single-call prompt designed with JSON schema output (`corrected_text` and `english_translation`) + automatic English bypass.
  - Latency budget verified: ~2.35s speech-to-transcription (<5s requirement), ~3.02s speech-to-translation (<8s requirement).
  - Comparative verification framework designed: dual-pipeline execution for Admin UI diff view and automated test scripts.
- **Unexplored areas**: None for survey phase. Ready for synthesis into PROJECT.md.

## Key Decisions Made
- Recommended AudioWorklet capturing raw 16kHz 16-bit PCM streamed over WebSocket to avoid container decoding/re-encoding latency.
- Recommended single-call LLM prompt returning JSON schema for both source correction and English translation.
- Designed dual-pipeline comparative framework for Admin UI and tests.

## Artifact Index
- `c:\Work\.agents\explorer_survey_2\analysis.md` — Deep pipeline and architecture analysis
- `c:\Work\.agents\explorer_survey_2\handoff.md` — 5-component handoff report
