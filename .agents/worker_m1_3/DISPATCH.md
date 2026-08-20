## 2026-08-20T09:39:16Z
You are worker_m1_3 (Final Hardening Worker) for Milestone 1 of the Translation Kiosk project.
Your working directory is: c:\Work\.agents\worker_m1_3

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY INPUTS TO READ:
- Authoritative User Request: c:\Work\.agents\ORIGINAL_REQUEST.md
- Master Project Specification: c:\Work\PROJECT.md
- Milestone 1 Scope: c:\Work\.agents\sub_orch_m1\SCOPE.md
- Challenger 4 Report: c:\Work\.agents\challenger_m1_4\handoff.md
- Worker 2 Remediation Handoff: c:\Work\.agents\worker_m1_2\handoff.md

HOST VM ACCESS:
- Ubuntu VM at 100.109.43.41 via plink.exe:
  `c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "<command>"`
- Python virtualenv: `/home/ubuntu/ai_kiosk/bin/python`
- Target directory: `/home/ubuntu/translation_kiosk`

TASK:
Apply the 5 precision edge-case hardening fixes documented in `c:\Work\.agents\challenger_m1_4\handoff.md`:
1. `whisper_client.py`:
   Ensure `data.get("language")` is robustly stripped and converted to string:
   `raw_lang = data.get("language")`
   `lang = str(raw_lang).lower().strip() if raw_lang is not None and str(raw_lang).strip() else "en"`
2. `qwen_client.py`:
   - In `post_correct_and_translate`:
     `lang_clean = str(source_language).strip().lower() if source_language is not None else "en"`
     `lang_lower = lang_clean if lang_clean else "en"`
   - In `parse_qwen_json`:
     Handle null / "None" / "null" values in JSON fields:
     `raw_corr = data.get("corrected_text")`
     `raw_trans = data.get("english_translation")`
     `corr_str = str(raw_corr).strip() if raw_corr is not None and str(raw_corr).strip() not in ("None", "null") else ""`
     `trans_str = str(raw_trans).strip() if raw_trans is not None and str(raw_trans).strip() not in ("None", "null") else ""`
     `return {"corrected_text": corr_str if corr_str else fallback_text, "english_translation": trans_str if trans_str else fallback_text}`
3. `config.py`:
   Ensure `get_language_name` handles whitespace-only strings:
   `def get_language_name(code: Optional[str]) -> str:`
   `    if not code: return "Unknown"`
   `    code_clean = str(code).lower().strip()`
   `    if not code_clean: return "Unknown"`
   `    return LANGUAGE_NAMES.get(code_clean, code_clean.capitalize())`
4. `audio_pipeline.py`:
   In `flush()`: Guard against non-idempotent consecutive flushes when `self.stitcher.tentative_tail` is empty. If no uncommitted tentative tail exists, return `None`.
5. Run full test suite on VM:
   `/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/ -v`
   Verify that `test_adversarial_challenger_m1_4.py` passes 24/24 (100%) and ALL test suites pass 100%.
6. Write your handoff report to `c:\Work\.agents\worker_m1_3\handoff.md`.
7. Reply with your completion message.
