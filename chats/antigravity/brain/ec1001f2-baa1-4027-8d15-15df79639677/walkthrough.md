# Home Assistant Optimization — Walkthrough

## Changes Made

### 1. Removed Leftover Voice Add-ons ✅
Uninstalled 3 add-ons that were installed during the camera experiment:
- **Whisper** (2.14 GB virtual image)
- **Piper** (1.37 GB virtual image)
- **Speech-to-Phrase** (1.0 GB virtual image)

> [!NOTE]
> **openWakeWord** needs to be manually removed from **Settings → Add-ons → openWakeWord → Uninstall**. The Supervisor keeps auto-restarting it.

### 2. Cleaned Up Integration Entries ✅
- Removed 3 orphaned Wyoming integration entries (openWakeWord, Piper, Speech-to-Phrase) from `core.config_entries`
- Removed the Wyze Camera Wyoming entry

### 3. Removed Orphan Voice Pipeline ✅
- Deleted the "Focused local assistant" pipeline that was created by the setup wizard
- Restored the "Home Assistant" pipeline back to Google AI STT/TTS

### 4. Cleaned Up Leftover Files ✅
- Removed Wyoming brands cache folder

### 5. Removed Deprecated `googlewifi` Component ✅
- Deleted `custom_components/googlewifi/` (no longer maintained, removed from HACS)

### 6. Fixed Template Sensor Errors ✅
- Changed AC target temp templates to return `unavailable` instead of `unknown` when AC is off
- This eliminates the recurring `Received invalid sensor state: unknown` error spam

## Before / After

| Metric | Before | After |
|--------|--------|-------|
| RAM Used | **2.1 GB** | **956 MB** |
| RAM Available | **1.7 GB** | **2.8 GB** |
| HA Log Errors | 3 per cycle | **0** |
| Deprecated components | 1 (`googlewifi`) | **0** |
| Orphan pipelines | 1 | **0** |
| Stale integration entries | 4 | **0** |

## Manual Action Required
- **Uninstall openWakeWord**: Go to **Settings → Add-ons → openWakeWord → Uninstall**
- **Frigate frontend files**: The `advanced-camera-card` files in `/config/www/community/` are part of a HACS frontend card. If you don't use it, you can remove it from **HACS → Frontend**.
