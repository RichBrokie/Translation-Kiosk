## 2026-08-19T09:13:22Z
You are spec_miner_test_matrix.
Your working directory is: c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix\
Read the following files before starting:
- c:\Work\.agents\ORIGINAL_REQUEST.md
- c:\Work\PROJECT.md
- c:\Work\.agents\orch_e2e_tests\SCOPE.md

Mission:
Mine and structure the comprehensive E2E test matrix and test infrastructure design for the Translation Kiosk project.
Requirements:
1. 4-Tier Test Case Design:
   - Tier 1: Feature Coverage (>=5 test cases per feature for all 15 features = >=75 test cases)
   - Tier 2: Boundary & Corner Cases (>=5 test cases per feature = >=75 test cases, covering empty audio, clipping, extreme lengths, invalid headers, rapid disconnects, multi-speaker noise, latency timeouts)
   - Tier 3: Cross-Feature Combinations (pairwise interaction matrix covering audio buffer + whisper + stitching + qwen + websocket + telemetry + bypass)
   - Tier 4: Real-World Multilingual Audio Workload Scenarios (at least 8 real-world end-to-end scenarios across Spanish, French, German, Mandarin, Arabic, Russian, Japanese, English with accents/noise)
2. Test Architecture & Runner Specifications:
   - Test runner structure: pytest-based harness with CLI runner `verify_kiosk_pipeline.py`
   - Real-time latency measurement (<5s Whisper, <8s Qwen, E2E)
   - Verification of sliding-window correction improvement vs non-overlapping
   - Verification of English bypass (0ms LLM latency)
   - REST and WebSocket endpoint test harnesses
3. Draft the complete content for `TEST_INFRA.md` following the required project template.

Save your comprehensive report and TEST_INFRA draft in c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix\report.md and write a handoff.md.
Send a message back to the orchestrator when finished.
