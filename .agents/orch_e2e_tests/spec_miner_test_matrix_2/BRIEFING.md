# BRIEFING — 2026-08-19T10:10:00Z

## Mission
Mine and structure the comprehensive E2E test matrix (Tier 1-4) and test infrastructure design (TEST_INFRA.md) for the Translation Kiosk project.

## 🔒 My Identity
- Archetype: spec_miner
- Roles: Specification Miner & E2E Test Architect
- Working directory: c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix_2\
- Original parent: cb00708b-db7f-4135-a44f-23edaa12c161
- Milestone: M_E2E_1 (Survey & Test Infrastructure Specification)

## 🔒 Key Constraints
- Mine comprehensive test matrix across 15 features for all 4 Tiers:
  - Tier 1: Feature Coverage (>=5 test cases per feature for 15 features = >=75 test cases)
  - Tier 2: Boundary & Corner Cases (>=5 test cases per feature for 15 features = >=75 test cases)
  - Tier 3: Cross-Feature Combinations (pairwise interaction matrix)
  - Tier 4: Real-World Multilingual Audio Workload Scenarios (>=8 languages: Spanish, French, German, Mandarin, Arabic, Russian, Japanese, English with accents/noise)
- Test architecture and runner specs: pytest harness, CLI runner verify_kiosk_pipeline.py, real-time latency measurement (<5s Whisper, <8s Qwen, E2E), sliding-window vs non-overlapping verification, English bypass (0ms LLM latency), REST/WebSocket harnesses.
- Do NOT implement production kiosk code (read-only specification mining and test architecture).
- Draft complete TEST_INFRA.md content and save comprehensive report to report.md.

## Current Parent
- Conversation ID: cb00708b-db7f-4135-a44f-23edaa12c161
- Updated: 2026-08-19T10:10:00Z

## Task Summary
- **What to build**: Comprehensive 4-Tier E2E Test Matrix, Test Architecture & Infrastructure specification, CLI runner specifications (`verify_kiosk_pipeline.py`), and `TEST_INFRA.md` draft.
- **Success criteria**: Exhaustive >=75 Tier 1, >=75 Tier 2, pairwise Tier 3, >=8 Tier 4 real-world test cases, latency verification mechanisms, sliding window comparison verification, English bypass verification.
- **Interface contracts**: PROJECT.md, SCOPE.md, explorer_api_services handoff.
- **Code layout**: PROJECT.md § Code Layout

## Key Decisions Made
- Use exact 15 features defined in SCOPE.md (F1 to F15).
- Structure Tier 1 with at least 5 distinct test cases per feature (75+ total).
- Structure Tier 2 with at least 5 boundary/adversarial cases per feature (75+ total).
- Structure Tier 3 pairwise matrix covering all critical subsystem interactions.
- Structure Tier 4 with 8 rich multilingual real-world audio datasets and validation criteria.
- Draft complete `TEST_INFRA.md` and `report.md`.

## Artifact Index
- `c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix_2\report.md` — Comprehensive report & TEST_INFRA draft
- `c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix_2\handoff.md` — Handoff report
- `c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix_2\progress.md` — Liveness & progress tracker
