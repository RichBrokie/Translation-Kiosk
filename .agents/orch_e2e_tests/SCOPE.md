# Scope: E2E Testing Track

## Architecture
- **Target System**: Translation Kiosk (FastAPI, WebSockets, Whisper ASR :8001, Qwen 72B LLM :8000, Web GUI & Admin Panel :8080)
- **Environment**: Ubuntu 26.04 VM (`100.109.43.41`) via `plink.exe` with Python 3.14 virtualenv `/home/ubuntu/ai_kiosk/bin/python`
- **Test Locations**: `/home/ubuntu/translation_kiosk/tests/`
- **Test Infrastructure Files**: `c:\Work\TEST_INFRA.md`, `c:\Work\TEST_READY.md`, `/home/ubuntu/translation_kiosk/tests/verify_kiosk_pipeline.py`, `/home/ubuntu/translation_kiosk/tests/test_e2e_tiers.py`, `/home/ubuntu/translation_kiosk/tests/conftest.py`, audio fixtures.

## Feature Inventory (Derived from ORIGINAL_REQUEST.md & PROJECT.md)
| # | Feature | Requirement Source | Tier 1 Target (>=5) | Tier 2 Target (>=5) | Tier 3 Target | Tier 4 Target |
|---|---------|-------------------|---------------------|---------------------|---------------|---------------|
| F1 | PCM Audio Capture & WebSocket Streaming (`/ws/audio`) | R1, R3 | 5 | 5 | Pairwise | ✓ |
| F2 | In-Memory Audio Buffer & Window Slicing (4s win / 2s overlap) | R3 | 5 | 5 | Pairwise | ✓ |
| F3 | Whisper ASR Async Client (`:8001/transcribe`) & Latency (<5s) | R3, Acceptance | 5 | 5 | Pairwise | ✓ |
| F4 | Language Auto-Detection & Code Propagation | R4 | 5 | 5 | Pairwise | ✓ |
| F5 | Sliding-Window Overlap Re-Transcription & Error Correction | R3, Acceptance | 5 | 5 | Pairwise | ✓ |
| F6 | Text Alignment & Stitching Engine (SequenceMatcher) | R3 | 5 | 5 | Pairwise | ✓ |
| F7 | Qwen 72B Post-Correction & Translation (`:8000`) & Latency (<8s) | R3, Acceptance | 5 | 5 | Pairwise | ✓ |
| F8 | English Language Bypass Logic (0ms LLM Latency for 'en') | R4 | 5 | 5 | Pairwise | ✓ |
| F9 | Dual-Pipeline Comparative Engine (Sliding vs Non-overlap) | R3, Acceptance | 5 | 5 | Pairwise | ✓ |
| F10| FastAPI Server Core, Lifecycle & Static Routes | R1, R2 | 5 | 5 | Pairwise | ✓ |
| F11| Admin WebSocket Telemetry (`/ws/admin`) & Diff Streaming | R2 | 5 | 5 | Pairwise | ✓ |
| F12| Audio File Playback Simulation Endpoint (`/api/test/audio_file`) | Acceptance | 5 | 5 | Pairwise | ✓ |
| F13| Public Kiosk UI HTML/CSS/JS Touchscreen Display | R1 | 5 | 5 | Pairwise | ✓ |
| F14| Admin Monitoring Dashboard HTML/CSS/JS & Gauges | R2 | 5 | 5 | Pairwise | ✓ |
| F15| Systemd Service Unit Lifecycle & Multi-Service Coexistence | R5 | 5 | 5 | Pairwise | ✓ |

Total Features N = 15
Target Minimums:
- Tier 1: >= 75 tests
- Tier 2: >= 75 tests
- Tier 3: >= 15 cross-feature pairwise tests
- Tier 4: >= 8 real-world multilingual audio workload scenarios

## Milestones for E2E Testing Track
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M_E2E_1 | Survey & Test Infrastructure Specification | Investigate VM environment, audio samples in `/mnt/models/* Talks/*.wav`, service endpoints (:8000, :8001, :8080), generate `TEST_INFRA.md` | none | IN_PROGRESS |
| M_E2E_2 | Test Runner & Tier 1/2 Test Suite Implementation | Build modular test harness, audio generator fixtures, Tier 1 (Feature Coverage) and Tier 2 (Boundary/Corner) test suites in `/home/ubuntu/translation_kiosk/tests/` | M_E2E_1 | PLANNED |
| M_E2E_3 | Tier 3/4 Test Suites & Comprehensive Pipeline Runner | Build Tier 3 (Cross-Feature Combinations) and Tier 4 (Real-World Multilingual Scenarios), `verify_kiosk_pipeline.py`, live audio replay tests | M_E2E_2 | PLANNED |
| M_E2E_4 | Verification, Audit & TEST_READY.md Publication | Run full test suite on VM, execute independent Reviewers, Challengers, Forensic Auditor, and publish `TEST_READY.md` | M_E2E_3 | PLANNED |
