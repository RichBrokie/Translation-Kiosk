# Adversarial Challenger Report — Milestone 1 (Pipeline & Error Resilience)

**Agent**: `challenger_m1_4` (Pipeline & Error Resilience Adversarial Challenger)  
**Parent Conversation ID**: `da36c33c-618d-4a51-81f7-80e99cb0754e`  
**Working Directory**: `c:\Work\.agents\challenger_m1_4`  
**Date**: 2026-08-20  
**Target VM**: `100.109.43.41` (`/home/ubuntu/translation_kiosk`)  
**Verdict**: **FAIL (Remediation Required for 5 Confirmed Vulnerabilities)**

---

## 1. Observation

Adversarial stress testing executed on the remote Ubuntu VM (`/home/ubuntu/ai_kiosk/bin/python`) revealed **5 empirical failures** across null-safety, parser corruption handling, language normalization, and session flush idempotency.

### Test Execution Command:
```bash
/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/test_adversarial_challenger_m1_4.py -v
```

### Verbatim Pytest Failure Output:
```
=================================== FAILURES ===================================
_ TestClientNullSafetyAndMalformedParams.test_whisper_client_malformed_language_types_in_server_json _
    client = WhisperClient(client=mock_http)
    res = await client.transcribe_wav(b"\x00\x00" * 500)
>   assert res.language == expected_code.strip().lower()
E   AssertionError: assert '  es  ' == 'es'
E     - es
E     +   es
translation_kiosk/tests/test_adversarial_challenger_m1_4.py:117: AssertionError

_ TestClientNullSafetyAndMalformedParams.test_qwen_client_null_empty_whitespace_source_language _
    res_ws = await client.post_correct_and_translate("Hello world", source_language="   ")
>   assert res_ws.bypassed is True
E   assert False is True
E    + where False = TranslationResult(corrected_text='Hello, world.', english_translation='Hello, world.', source_language='   ', latency_ms=1564.1ms, bypassed=False, error=None).bypassed
translation_kiosk/tests/test_adversarial_challenger_m1_4.py:156: AssertionError

_ TestClientNullSafetyAndMalformedParams.test_parse_qwen_json_adversarial_corruptions _
    corrupt_null = '{"corrected_text": null, "english_translation": null}'
    parsed = parse_qwen_json(corrupt_null, fallback_text=fallback)
>   assert parsed["corrected_text"] == fallback
E   AssertionError: assert 'None' == 'Original raw transcript text'
E     - Original raw transcript text
E     + None
translation_kiosk/tests/test_adversarial_challenger_m1_4.py:185: AssertionError

_ TestClientNullSafetyAndMalformedParams.test_config_get_language_name_robustness _
    assert get_language_name(None) == "Unknown"
    assert get_language_name("") == "Unknown"
>   assert get_language_name("   ") == "Unknown"
E   AssertionError: assert '' == 'Unknown'
E     - Unknown
translation_kiosk/tests/test_adversarial_challenger_m1_4.py:214: AssertionError

__ TestSessionFlushAndLifecycle.test_consecutive_duplicate_flush_idempotency ___
    f1 = await pipeline.flush()
    assert f1 is not None
    assert f1.is_final is True
    f2 = await pipeline.flush()
>   assert f2 is None
E   AssertionError: assert PipelineResult(raw_text='', window_text='', stitched_text='One last thing', language='en', language_name='English', corrected_text='One last thing', translated_text='One last thing', is_english=True, is_final=True) is None
translation_kiosk/tests/test_adversarial_challenger_m1_4.py:509: AssertionError

========================= 5 failed, 19 passed in 3.82s =========================
```

---

## 2. Logic Chain

### Finding 1: `whisper_client.py` Line 125 — Unstripped & Non-String Language Codes
- **Observation**: `lang = (data.get("language") or "en").lower()`.
- **Logic**: When the ASR server returns `{"language": "  ES  "}`, `lang` is set to `"  es  "`. If `language` is an integer `{"language": 123}`, `(123 or "en").lower()` raises `AttributeError`.
- **Blast Radius**: Downstream dictionary lookups (`LANGUAGE_NAMES.get(lang)`) fail to match; language tags in UI render with leading/trailing spaces or crash the client.

### Finding 2: `qwen_client.py` Line 106 — Whitespace Source Language Fails English Bypass
- **Observation**: `lang_lower = (source_language or "en").lower().strip()`.
- **Logic**: When `source_language = "   "`, `"   "` is truthy in Python, so `("   " or "en")` evaluates to `"   "`. Then `lang_lower` evaluates to `""`. Since `"" not in ("en", "english")`, English bypass is NOT triggered.
- **Blast Radius**: Audio chunks with unassigned or whitespace languages trigger redundant 1.5s - 6.0s LLM calls to vLLM Qwen 72B, wasting quota and GPU cycles.

### Finding 3: `qwen_client.py` Line 29-33 — Null Value Extraction Produces Literal `"None"` in UI
- **Observation**: `corrected = str(data.get("corrected_text", fallback_text)).strip()`.
- **Logic**: When Qwen outputs `{"corrected_text": null, "english_translation": null}`, `dict.get("corrected_text", fallback_text)` returns `None` because the key exists with value `None`. `str(None)` converts this to the string `"None"`. Because `"None"` is non-empty, the fallback is ignored.
- **Blast Radius**: Kiosk visitors see the word `"None"` rendered as translated speech text on the kiosk UI.

### Finding 4: `config.py` Line 84 — Whitespace Language Code Returns Empty String
- **Observation**: `def get_language_name(code: Optional[str]) -> str:`
- **Logic**: If `code = "   "`, `if not code:` evaluates to `False`. `code_lower` becomes `""`. `LANGUAGE_NAMES.get("", "".capitalize())` returns `""` instead of `"Unknown"`.
- **Blast Radius**: UI displays blank language name tag.

### Finding 5: `audio_pipeline.py` Line 172-185 — Non-Idempotent Duplicate `flush()` Execution
- **Observation**: `final_text = self.stitcher.flush_final()`. `TextStitcher.flush_final()` returns `self.committed_text` even when `self.tentative_tail` was already empty.
- **Logic**: If `flush()` is called twice consecutively (e.g., frontend stop button + WebSocket disconnect), the second flush sees `final_text = self.committed_text` and launches a second Qwen LLM translation over the entire transcript history.
- **Blast Radius**: Duplicate WebSocket messages, wasted LLM tokens, duplicate UI rendering events.

---

## 3. Concrete Mitigations

### 1. In `whisper_client.py`:
```python
raw_lang = data.get("language")
lang = str(raw_lang).lower().strip() if raw_lang is not None and str(raw_lang).strip() else "en"
```

### 2. In `qwen_client.py`:
```python
# Fix English bypass:
lang_clean = str(source_language).strip().lower() if source_language is not None else "en"
lang_lower = lang_clean if lang_clean else "en"

# Fix parse_qwen_json null values:
raw_corr = data.get("corrected_text")
raw_trans = data.get("english_translation")
corr_str = str(raw_corr).strip() if raw_corr is not None and str(raw_corr).strip() not in ("None", "null") else ""
trans_str = str(raw_trans).strip() if raw_trans is not None and str(raw_trans).strip() not in ("None", "null") else ""
return {
    "corrected_text": corr_str if corr_str else fallback_text,
    "english_translation": trans_str if trans_str else fallback_text
}
```

### 3. In `config.py`:
```python
def get_language_name(code: Optional[str]) -> str:
    if not code:
        return "Unknown"
    code_clean = str(code).lower().strip()
    if not code_clean:
        return "Unknown"
    return LANGUAGE_NAMES.get(code_clean, code_clean.capitalize())
```

### 4. In `audio_pipeline.py`:
```python
async def flush(self) -> Optional[PipelineResult]:
    slice_data = await self.buffer.flush()
    if slice_data:
        window_pcm, window_idx, start_sec = slice_data
        result = await self._process_window_pcm(window_pcm, is_final=True)
        self.stitcher.flush_final()
        if result:
            result.stitched_text = self.stitcher.committed_text
            result.is_final = True
        return result
    else:
        # Check if there is an uncommitted tentative tail
        if not self.stitcher.tentative_tail:
            return None
            
        final_text = self.stitcher.flush_final()
        if not final_text:
            return None
            
        qwen_res = await self.qwen_client.post_correct_and_translate(
            final_text,
            self._last_detected_language
        )
        is_en = (self._last_detected_language or "en").lower() in ("en", "english")
        return PipelineResult(
            raw_text="",
            window_text="",
            stitched_text=final_text,
            language=self._last_detected_language,
            language_name=get_language_name(self._last_detected_language),
            corrected_text=qwen_res.corrected_text,
            translated_text=qwen_res.english_translation,
            whisper_latency_ms=0.0,
            qwen_latency_ms=qwen_res.latency_ms,
            e2e_latency_ms=qwen_res.latency_ms,
            is_english=is_en,
            is_final=True
        )
```

---

## 4. Caveats

- Baseline audio streaming, WAV packaging, and live GPU Whisper (port 8001) / vLLM Qwen 72B (port 8000) integrations are fully operational.
- The 5 identified failures are edge-case / boundary conditions that degrade resilience under malformed inputs, whitespace strings, JSON nulls, and duplicate session terminations.

---

## 5. Conclusion

**Verdict**: **FAIL**  
The Milestone 1 core pipeline requires remediation for the 5 confirmed vulnerabilities documented above before proceeding to production deployment.

---

## 6. Verification Method

To independently execute and verify the adversarial challenger test suite on the VM:

```bash
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/test_adversarial_challenger_m1_4.py -v"
```
