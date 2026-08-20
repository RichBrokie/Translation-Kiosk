# Review & Handoff Report — Milestone 1: Robustness & Edge-Case Review

**Reviewer**: `reviewer_m1_2` (Robustness & Edge-Case Reviewer, Critic)  
**Parent Conversation ID**: `da36c33c-618d-4a51-81f7-80e99cb0754e`  
**Working Directory**: `c:\Work\.agents\reviewer_m1_2`  
**Date**: 2026-08-20  
**Verdict**: **REQUEST_CHANGES**

---

## Review Summary

An independent, adversarial review and stress-test of Milestone 1 components (`AudioRollingBuffer`, `pack_pcm_to_wav`, `TextStitcher`, `QwenClient`, `TelemetryCollector`, `AudioPipeline`) was performed on the Ubuntu VM (`100.109.43.41`).

While core architecture, RIFF WAV packaging, Requirement R4 English bypass (0ms latency), and Telemetry percentiles calculations are well-designed, **adversarial stress testing revealed a Critical functional defect in `TextStitcher` resulting in silent deletion of spoken words**, as well as an un-enforced memory bound in `AudioRollingBuffer`.

---

## Findings

### [Critical] Finding 1: `TextStitcher` drops words on offset overlap matches (`match.a > 0`) and zero-overlap transitions (`match.size == 0`)

- **Location**: `/home/ubuntu/translation_kiosk/audio_pipeline.py:255-288`
- **What**:
  1. When `difflib.SequenceMatcher` finds a match starting at `match.a > 0` in `prev_words` (e.g. `prev_words = ["have", "ancient", "egypt"]` matching `"ancient"` at index 1), the unmatched prefix `prev_words[:match.a]` (`["have"]`) is discarded without being committed to `self.committed_text`.
  2. When `match.size == 0` (e.g. natural speaker pauses, phrase boundary shifts, or disjoint utterances), `split_idx` falls back to `len(curr_words) * overlap_ratio` and completely overwrites `self.tentative_tail` with the new window's tail without committing the previous `self.tentative_tail` to `self.committed_text`.
- **Reproduction Evidence**:
  - *Case A (`match.a > 0`)*:
    - Input Window 1: `"Here we have ancient egypt"` (`committed="Here we"`, `tail="have ancient egypt"`)
    - Input Window 2: `"ancient egyptian artifacts from the tomb"`
    - **Actual Result**: `committed = "Here we ancient egyptian"`, `display = "Here we ancient egyptian artifacts from the tomb"` (The word **"have"** was dropped).
    - **Expected Result**: `"Here we have ancient egyptian artifacts from the tomb"`
  - *Case B (`match.size == 0`)*:
    - Input Window 1: `"The quick brown fox jumps"` (`committed="The quick"`, `tail="brown fox jumps"`)
    - Input Window 2: `"over a lazy dog"`
    - **Actual Result**: `committed = "The quick over a"`, `display = "The quick over a lazy dog"` (The phrase **"brown fox jumps"** was permanently dropped).
    - **Expected Result**: `"The quick brown fox jumps over a lazy dog"`
- **Why**:
  In `TextStitcher.process_window`:
  ```python
  # Current implementation (buggy):
  overlap_to_commit = curr_words[:split_idx]
  new_tentative = curr_words[split_idx:]
  if overlap_to_commit:
      if self.committed_text:
          self.committed_text = f"{self.committed_text} {' '.join(overlap_to_commit)}".strip()
      else:
          self.committed_text = " ".join(overlap_to_commit)
  self.tentative_tail = " ".join(new_tentative)
  ```
  `prev_words[:match.a]` (in matched cases) and `self.tentative_tail` (in zero-match cases) are never added to `self.committed_text`.
- **Suggested Fix**:
  ```python
  if match.size >= 1:
      # Prepend unmatched prefix from previous tentative tail before the match
      unmatched_prev = prev_words[:match.a]
      overlap_to_commit = unmatched_prev + curr_words[:split_idx]
      new_tentative = curr_words[split_idx:]
  else:
      # Zero match found: commit all of previous tentative tail first
      unmatched_prev = prev_words
      overlap_to_commit = unmatched_prev + curr_words[:split_idx]
      new_tentative = curr_words[split_idx:]

  if overlap_to_commit:
      if self.committed_text:
          self.committed_text = f"{self.committed_text} {' '.join(overlap_to_commit)}".strip()
      else:
          self.committed_text = " ".join(overlap_to_commit)
  self.tentative_tail = " ".join(new_tentative)
  ```

---

### [Major] Finding 2: `AudioRollingBuffer` does not enforce `MAX_RETENTION_BYTES` memory limit

- **Location**: `/home/ubuntu/translation_kiosk/audio_pipeline.py:93-115`
- **What**:
  `config.py` defines `MAX_RETENTION_SEC = 12.0` (384,000 bytes) and `AudioRollingBuffer.__init__` computes `self.max_retention_bytes`, but `append_pcm()` never checks or prunes `len(self._buffer)`.
- **Why**:
  If audio is pushed continuously while processing is delayed or waiting on slow upstream networks, the internal `bytearray` grows without bound.
- **Suggested Fix**:
  In `AudioRollingBuffer.append_pcm()`:
  ```python
  async with self._lock:
      self._buffer.extend(chunk)
      self._total_bytes_received += len(chunk)
      if len(self._buffer) > self.max_retention_bytes:
          del self._buffer[:-self.max_retention_bytes]
  ```

---

### [Minor] Finding 3: `WhisperClient` and `QwenClient` vulnerable to `AttributeError` on `None` language input

- **Location**:
  - `/home/ubuntu/translation_kiosk/whisper_client.py:126` (`data.get("language", "en").lower()`)
  - `/home/ubuntu/translation_kiosk/qwen_client.py:145` (`source_language.lower().strip()`)
- **What**:
  If Whisper returns `{"text": "...", "language": null}`, `data.get("language", "en")` evaluates to `None`, causing `.lower()` to raise `AttributeError`. Similarly, calling `post_correct_and_translate` with `source_language=None` crashes on `.lower()`.
- **Suggested Fix**:
  Use `(data.get("language") or "en").lower()` and `(source_language or "en").lower().strip()`.

---

## 1. Observation

Direct observations from independent execution on Ubuntu VM (`100.109.43.41`):

1. **Unit Test Suite Execution (`tests/test_pipeline.py`)**:
   - Command: `/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/test_pipeline.py -v`
   - Output: `23 passed in 0.18s` (100% pass on baseline unit tests).
2. **Adversarial Stress Test (`verify_robustness.py`)**:
   - `pack_pcm_to_wav`: Verified canonical 44-byte RIFF header, readable by standard python `wave` module, handles 0-byte and arbitrary byte lengths correctly.
   - `QwenClient`: Verified Requirement R4 English bypass (0ms latency, no HTTP request), 5-stage JSON parser resilience against markdown code blocks, conversational preambles, and malformed strings.
   - `TelemetryCollector`: Verified percentile calculations (`min`, `max`, `avg`, `p50`, `p90`, `p95`), ring buffer bounding (`maxlen=100`), and admin payload serialization.
   - `TextStitcher`: Failed on word retention during offset matches (`match.a > 0`) and zero-match transitions (`match.size == 0`).
   - `AudioRollingBuffer`: Failed to enforce `max_retention_bytes` bound.

---

## 2. Logic Chain

1. *Observation*: During continuous speech transcription with sliding windows, Whisper ASR output tokens do not always align at word index 0 of the tentative tail (e.g. pauses or slight tokenization differences).
   *Inference*: If `difflib.SequenceMatcher` matches at index `match.a > 0` and the stitcher only takes `curr_words[:split_idx]`, words `prev_words[:match.a]` are permanently lost from the committed transcript.
2. *Observation*: When speech pauses or topic changes occur between windows, `difflib.SequenceMatcher` finds 0 matching words (`match.size == 0`).
   *Inference*: The fallback split overwrites `self.tentative_tail` without committing the previous tail, causing complete loss of the last words spoken before the pause.
3. *Observation*: Kiosk is intended for long-running continuous deployments (museum exhibit).
   *Inference*: Without enforcing `max_retention_bytes` in `AudioRollingBuffer`, temporary downstream stalls cause unbounded memory growth.

---

## 3. Caveats

- Live Whisper (port 8001) and vLLM Qwen (port 8000) microservices are operational on the VM.
- The unit test suite `tests/test_pipeline.py` passed because existing test cases only tested exact index-0 overlap matches; they did not cover offset matches (`match.a > 0`) or zero-overlap transitions (`match.size == 0`).
- No integrity violations (hardcoded test results, facade logic, or shortcuts) were detected in the source code.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The worker must implement the following fixes before Milestone 1 can be approved:
1. Fix `TextStitcher.process_window` in `/home/ubuntu/translation_kiosk/audio_pipeline.py` to commit `prev_words[:match.a]` when `match.size >= 1`, and commit the full `self.tentative_tail` when `match.size == 0`.
2. Add unit tests in `tests/test_pipeline.py` covering offset overlap matches (`match.a > 0`) and zero-match transitions (`match.size == 0`).
3. Enforce `max_retention_bytes` in `AudioRollingBuffer.append_pcm()`.
4. Add null-safe fallbacks for `language` in `whisper_client.py` and `qwen_client.py`.

---

## 5. Verification Method

To independently verify these findings and validate future fixes:

1. **Run the TextStitcher Reproduction Script**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/python -c '
   import sys; sys.path.append(\"/home/ubuntu/translation_kiosk\")
   from audio_pipeline import TextStitcher
   s = TextStitcher(overlap_ratio=0.5)
   s.process_window(\"Here we have ancient egypt\")
   c, t, d, r = s.process_window(\"ancient egyptian artifacts from the tomb\")
   assert \"have\" in d, f\"FAILED: have was dropped from display: {d}\"
   print(\"PASSED:\", d)
   '"
   ```

2. **Run the Zero-Match Disjoint Utterance Script**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/python -c '
   import sys; sys.path.append(\"/home/ubuntu/translation_kiosk\")
   from audio_pipeline import TextStitcher
   s = TextStitcher(overlap_ratio=0.5)
   s.process_window(\"The quick brown fox jumps\")
   c, t, d, r = s.process_window(\"over a lazy dog\")
   assert \"brown fox jumps\" in d, f\"FAILED: brown fox jumps was dropped: {d}\"
   print(\"PASSED:\", d)
   '"
   ```

3. **Run the Full Test Suite on VM**:
   ```powershell
   c:\Work\plink.exe -hostkey "SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM" -batch -ssh -pw Metropolis0! ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/pytest /home/ubuntu/translation_kiosk/tests/test_pipeline.py -v"
   ```
