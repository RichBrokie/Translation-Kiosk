## 2026-08-20T09:19:39Z
You are worker_m1_2 (Remediation & Hardening Worker) for Milestone 1 of the Translation Kiosk project.
Your working directory is: c:\Work\.agents\worker_m1_2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY INPUTS TO READ:
- Authoritative User Request: c:\Work\.agents\ORIGINAL_REQUEST.md
- Master Project Specification: c:\Work\PROJECT.md
- Milestone 1 Scope: c:\Work\.agents\sub_orch_m1\SCOPE.md
- Reviewer 2 Findings & Reproduction: c:\Work\.agents\reviewer_m1_2\handoff.md
- Reviewer 1 Findings & Recommendations: c:\Work\.agents\reviewer_m1_1\handoff.md
- Prior Worker Handoff: c:\Work\.agents\worker_m1_1\handoff.md

HOST VM ACCESS:
- Ubuntu VM at 100.109.43.41 via plink.exe:
  `c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "<command>"`
- Python virtualenv: `/home/ubuntu/ai_kiosk/bin/python`
- Target directory: `/home/ubuntu/translation_kiosk`

TASK:
Apply the 4 critical reviewer remediations directly on the VM:
1. Fix `TextStitcher.process_window` in `/home/ubuntu/translation_kiosk/audio_pipeline.py`:
   - When `match.size >= 1`: Prepend unmatched prefix from previous tentative tail before the match:
     `unmatched_prev = prev_words[:match.a]`
     `overlap_to_commit = unmatched_prev + curr_words[:split_idx]`
     `new_tentative = curr_words[split_idx:]`
   - When `match.size == 0`: Commit all previous tentative tail before new window:
     `unmatched_prev = prev_words`
     `overlap_to_commit = unmatched_prev + curr_words[:split_idx]`
     `new_tentative = curr_words[split_idx:]`
   - Update `self.committed_text` and `self.tentative_tail` consistently.
2. Fix `AudioRollingBuffer.append_pcm` in `/home/ubuntu/translation_kiosk/audio_pipeline.py`:
   - Enforce memory bound:
     `if len(self._buffer) > self.max_retention_bytes:`
     `    del self._buffer[:-self.max_retention_bytes]`
3. Update `config.py`:
   - Increase `QWEN_TIMEOUT_SEC = 10.0` to accommodate multi-window streaming translations.
4. Fix `whisper_client.py` and `qwen_client.py`:
   - Null-safe language fallback: `(data.get("language") or "en").lower()` and `(source_language or "en").lower().strip()`.
5. Update `tests/test_pipeline.py` on the VM with dedicated regression unit tests covering:
   - `test_text_stitcher_offset_match_preserves_prefix_words`
   - `test_text_stitcher_zero_match_commits_previous_tail`
   - `test_audio_buffer_max_retention_enforcement`
   - `test_whisper_and_qwen_clients_null_language_safety`
6. Run full pytest suite on VM: `/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/test_pipeline.py -v`.
7. Verify all tests pass (100%).
8. Write your completion report to `c:\Work\.agents\worker_m1_2\handoff.md`.
9. Send completion message back to caller (ID: da36c33c-618d-4a51-81f7-80e99cb0754e).
