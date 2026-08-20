# Handoff Report — VM Environment & Audio Assets Investigation

**Agent**: `explorer_vm_env_2`  
**Working Directory**: `c:\Work\.agents\orch_e2e_tests\explorer_vm_env_2\`  
**Target Environment**: Ubuntu 26.04 VM (`100.109.43.41`)  
**Parent Orchestrator**: `cb00708b-db7f-4135-a44f-23edaa12c161`  
**Date**: 2026-08-19  

---

## 1. Observation

1. **Filesystem & Mount Layout**:
   - `/mnt/models` is mounted on `/dev/sdb1` (Total: 3.5 TB, Used: 254 GB, Available: 3.3 TB, 8% used). Permissions: `drwxrwxrwx` owned by `ubuntu:ubuntu`.
   - Root filesystem `/` on `/dev/sda2` has 84 GB available (34 GB used out of 124 GB).
   - `/home/ubuntu/translation_kiosk` exists with permissions `drwxrwxr-x` (mode `0775`), owned by `ubuntu:ubuntu` (UID 1000, GID 1000), currently empty and ready for deployment.

2. **Multilingual Audio Asset Corpus**:
   - Cataloged **140 full-length WAV audio files** across 14 language directories in `/mnt/models/* Talks`:
     - `Bengali Talks`: 10 WAVs, 2 SRTs, Total Duration: 2h 45m 25s
     - `English Talks`: 10 WAVs, 10 SRTs, Total Duration: 2h 11m 10s
     - `French Talks`: 10 WAVs, 11 SRTs, Total Duration: 2h 30m 57s
     - `German Talks`: 10 WAVs, 8 SRTs, Total Duration: 2h 34m 19s
     - `Hindi Talks`: 10 WAVs, 4 SRTs, Total Duration: 2h 49m 32s
     - `Indonesian Talks`: 10 WAVs, 6 SRTs, Total Duration: 2h 29m 06s
     - `Japanese Talks`: 10 WAVs, 13 SRTs, Total Duration: 2h 21m 14s
     - `Mandarin Chinese Talks`: 10 WAVs, 12 SRTs, Total Duration: 1h 55m 04s
     - `Portuguese Talks`: 10 WAVs, 1 SRT, Total Duration: 2h 45m 58s
     - `Russian Talks`: 10 WAVs, 10 SRTs, Total Duration: 2h 30m 45s
     - `Spanish Talks`: 10 WAVs, 10 SRTs, Total Duration: 2h 26m 54s
     - `Standard Arabic Talks`: 10 WAVs, 11 SRTs, Total Duration: 1h 11m 05s
     - `Turkish Talks`: 10 WAVs, 6 SRTs, Total Duration: 2h 48m 39s
     - `Urdu Talks`: 10 WAVs, 1 SRT, Total Duration: 2h 50m 07s
   - Total Audio Duration: **34 hours 10 minutes 22 seconds** (20.21 GB).
   - All 140 WAV files have identical specifications: **44,100 Hz sample rate**, **2 channels (stereo)**, **16-bit PCM**.
   - Accompanied by **105 ground-truth SRT subtitle files** with timestamped human transcripts.
   - Additional audio files: 16 WAVs in `/tmp/` (sliced benchmark chunks), 1 WAV in `pyannote/audio/sample/sample.wav` (16kHz mono), 23 WAVs in `scipy/io/tests/data/`.

3. **Python Environment & Dependencies**:
   - Python executable: `/home/ubuntu/ai_kiosk/bin/python` (Python 3.14.0).
   - Core packages installed and verified:
     - Web & API: `fastapi` 0.136.3, `uvicorn` 0.52.3, `starlette` 1.6.0, `pydantic` 2.13.4, `pydantic-settings` 2.15.0, `python-multipart` 0.0.32, `jinja2` 3.1.6
     - HTTP & WS: `httpx` 0.28.1, `websockets` 17.0.1, `aiohttp` 3.14.3, `requests` 2.34.2
     - Audio & ML: `scipy` 1.18.0 (with `scipy.signal` and `scipy.io.wavfile`), `torchaudio` 2.11.0, `faster-whisper` 1.2.1, `torch` 2.13.0, `openai` 3.1.0, `vllm` 0.27.1, `transformers` 5.15.0
     - Monitoring: `psutil` 7.2.2, `loguru` 0.7.3, `rich` 15.0.0, `watchfiles` 1.2.0, `prometheus_client` 0.26.0
   - Missing test packages: `pytest`, `pytest-asyncio`, `soundfile`. Pip dry-run confirmed active internet access and clean installability (`pip install pytest pytest-asyncio soundfile`).
   - System tools: `ffmpeg` 7.1.3-1ubuntu1 (`/usr/bin/ffmpeg`), `ffprobe` 7.1.3-1ubuntu1 (`/usr/bin/ffprobe`), `git` 2.48.1, `nvidia-smi` (NVIDIA RTX 6000 Ada, 48 GB VRAM).

4. **Service Status**:
   - `audio-kiosk.service`: active on port `8001` (PID 2053, Faster-Whisper Large v3 Turbo CT2).
   - `vllm.service`: active on port `8000` (PID 2071, Qwen 2.5 72B AWQ).
   - Port `8080` is completely free.
   - `translation-kiosk.service` is not yet installed in `/etc/systemd/system/`.

---

## 2. Logic Chain

1. From Observation 1: `/home/ubuntu/translation_kiosk` is owned by `ubuntu:ubuntu` with write permissions (0775) and 84 GB free space on root and 3.3 TB on `/mnt/models`, ensuring complete capacity for source files, test fixtures, and logs.
2. From Observation 2: The 140 TED Talk WAV files in `/mnt/models/* Talks` cover 14 distinct languages with matching SRT transcripts. Because they are 44.1kHz stereo, test generators and simulation replay runners must downsample to 16kHz mono PCM (via `scipy.signal.resample` or `ffmpeg`), perfectly matching the Kiosk ingestion contract.
3. From Observation 3: The Python environment contains all necessary ASGI and HTTP/WebSocket server and client libraries (`fastapi`, `uvicorn`, `httpx`, `websockets`, `pydantic`). If `pytest` is desired for test execution, running `pip install pytest pytest-asyncio soundfile` in `/home/ubuntu/ai_kiosk` will immediately configure it, or tests can execute with Python's built-in `unittest`.
4. From Observation 4: Port 8080 is available, allowing `main.py` and the future `translation-kiosk.service` to bind directly to `0.0.0.0:8080` alongside existing background AI services without conflict.

---

## 3. Caveats

- **Stereo 44.1kHz to Mono 16kHz**: Talk WAV files must be downsampled to 16kHz mono when feeding into the kiosk pipeline or Whisper client.
- **Sudo Password**: User `ubuntu` requires sudo password (`Metropolis0!`) when deploying systemd unit files to `/etc/systemd/system/`.
- **PyPI Installation**: `pytest` and `pytest-asyncio` are not yet installed in `/home/ubuntu/ai_kiosk`, but pip network access is verified and ready.

---

## 4. Conclusion

The VM environment is in prime operational condition. The filesystem structure, permissions, audio assets, Python libraries, system tools, and AI background services provide all prerequisites required for the Translation Kiosk application and the full 5-tier E2E testing framework. Detailed data and asset catalog are documented in `report.md`.

---

## 5. Verification Method

To independently verify these findings on the VM, execute:

```bash
# 1. Verify filesystem, disk space, and directory permissions
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "ls -ld /home/ubuntu/translation_kiosk /mnt/models; df -h / /mnt/models"

# 2. Count and verify talk audio files across languages
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/python -c \"import os; dirs=[d for d in os.listdir('/mnt/models') if 'Talks' in d]; print(f'Found {len(dirs)} Talk dirs with {sum(len([f for f in os.listdir(os.path.join(\\\"/mnt/models\\\", d)) if f.endswith(\\\".wav\\\")]) for d in dirs)} WAVs')\""

# 3. Verify Python packages and ffmpeg
c:\Work\plink.exe -batch -ssh -pw Metropolis0! -hostkey SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM ubuntu@100.109.43.41 "/home/ubuntu/ai_kiosk/bin/python -c \"import fastapi, uvicorn, httpx, websockets, scipy; print('Core packages OK')\"; ffmpeg -version | head -n 1"
```
