# BRIEFING — 2026-08-19T10:38:00Z

## Mission
Implement comprehensive test suite (Tiers 1-4, conftest, and verify_kiosk_pipeline.py) for the multilingual translation kiosk on the Ubuntu VM and create TEST_INFRA.md.

## 🔒 My Identity
- Archetype: test_writer
- Roles: specialist, qa
- Working directory: c:\Work\.agents\orch_e2e_tests\worker_test_impl_2\
- Original parent: cb00708b-db7f-4135-a44f-23edaa12c161
- Milestone: E2E Test Suite Implementation

## 🔒 Key Constraints
- Test code only — never modify implementation code.
- Plink command syntax: c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "<command>"
- Python env: /home/ubuntu/ai_kiosk/bin/python
- Test directory: /home/ubuntu/translation_kiosk/tests/
- Tier 1: >=75 tests (F1-F15, 5 tests each)
- Tier 2: >=75 tests (F1-F15, 5 tests each)
- Tier 3: >=15 pairwise tests
- Tier 4: >=8 real-world multilingual audio workload scenarios (/mnt/models/* Talks/*.wav)
- verify_kiosk_pipeline.py: CLI runner with latency thresholds (<5s Whisper, <8s Qwen, 0ms English bypass), sliding window comparison, JSON output.
- TEST_INFRA.md on host.
- NO dummy or facade tests. Real logic and validation.

## Current Parent
- Conversation ID: cb00708b-db7f-4135-a44f-23edaa12c161
- Updated: 2026-08-19T10:38:00Z

## Loaded Skills
- None required specifically beyond standard test writer role.

## Quality Status
- Build/test result: [TBD]
- Lint status: [TBD]
- Tests added/modified: [TBD]

## Task Summary
- **What to build**: Full 4-tier test suite + verify_kiosk_pipeline.py on VM, TEST_INFRA.md on host.
- **Success criteria**: All test files implemented, syntax valid, pytest runnable, verify_kiosk_pipeline.py runnable and functional.
- **Interface contracts**: spec_miner_test_matrix_2/report.md, SCOPE.md, explorer reports.
- **Code layout**: /home/ubuntu/translation_kiosk/tests/

## Key Decisions Made
- [TBD]

## Artifact Index
- c:\Work\TEST_INFRA.md — Test architecture & methodology
- c:\Work\.agents\orch_e2e_tests\worker_test_impl_2\report.md — Implementation report
- c:\Work\.agents\orch_e2e_tests\worker_test_impl_2\handoff.md — Handoff report
