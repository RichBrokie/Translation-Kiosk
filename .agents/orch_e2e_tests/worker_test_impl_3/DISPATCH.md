## 2026-08-20T09:09:24Z
You are worker_test_impl_3.
Your working directory is: c:\Work\.agents\orch_e2e_tests\worker_test_impl_3\
Read the following files before starting:
- c:\Work\.agents\ORIGINAL_REQUEST.md
- c:\Work\PROJECT.md
- c:\Work\.agents\orch_e2e_tests\SCOPE.md
- c:\Work\.agents\orch_e2e_tests\spec_miner_test_matrix_2\report.md
- c:\Work\.agents\orch_e2e_tests\explorer_vm_env_2\report.md
- c:\Work\.agents\orch_e2e_tests\explorer_api_services\report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Host VM access info:
Ubuntu 26.04 VM at 100.109.43.41 via c:\Work\plink.exe (user: ubuntu, pw: Metropolis0!, hostkey: SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM)
Command syntax:
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "<command>"
Python virtualenv on VM: /home/ubuntu/ai_kiosk/bin/python

YOUR MISSION:
1. Create c:\Work\TEST_INFRA.md on the host documenting the complete test architecture, 4-tier methodology (Tier 1: >=75 tests, Tier 2: >=75 tests, Tier 3: >=15 pairwise tests, Tier 4: >=8 real-world multilingual audio workload scenarios), latency thresholds (<5s Whisper, <8s Qwen, 0ms bypass for English), and test runner specifications per spec_miner_test_matrix_2/report.md.
2. In /home/ubuntu/translation_kiosk/tests/ on the Ubuntu VM:
   - Ensure required packages (pytest, pytest-asyncio, soundfile, httpx, websockets, requests) are installed in /home/ubuntu/ai_kiosk/bin/python.
   - Implement `conftest.py`: pytest fixtures, audio generators (sine, silence, noise, clipping), audio loader for real speech from `/mnt/models/* Talks/*.wav`, mock & live client fixtures for ports 8000, 8001, 8080.
   - Implement `test_tier1_feature_coverage.py`: 75 test cases covering all 15 features in isolation (F1-F15, 5 tests each).
   - Implement `test_tier2_boundary_corner.py`: 75 test cases covering boundary, corner, starvation, clipping, timeout, rapid reconnect, and error handling (F1-F15, 5 tests each).
   - Implement `test_tier3_cross_feature.py`: 15 test cases covering pairwise multi-component interactions.
   - Implement `test_tier4_real_world_scenarios.py`: 8 test cases covering real-world audio playback across Spanish, French, German, Mandarin, Arabic, Russian, Japanese, and accented English with noise using real audio from `/mnt/models/* Talks/*.wav`.
   - Implement `verify_kiosk_pipeline.py`: Standalone CLI automated verification runner with argument parsing (--audio, --endpoint, --live-services, --fast, --strict-latency, --output-json), per-chunk latency measurements (Whisper <5s, Qwen <8s, E2E), sliding-window vs non-overlapping baseline comparison, and English bypass verification (0ms LLM latency).
3. Run the test suites via pytest and run verify_kiosk_pipeline.py on the VM. Verify that the test runner executes and outputs pass/fail metrics.
4. Save your detailed implementation report in c:\Work\.agents\orch_e2e_tests\worker_test_impl_3\report.md and write a handoff.md.
Send a message back to the orchestrator when finished.
