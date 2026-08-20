# Home Assistant Full System Optimization

Based on a comprehensive audit of your HA installation at `192.168.86.41` running **HA 2026.7.4**.

## User Review Required

> [!IMPORTANT]
> Several add-ons installed during our camera experiment are still running and consuming significant RAM. Your server only has **3.8 GB total RAM** with **1.7 GB available** — removing them will free up ~1GB.

> [!WARNING]
> The `googlewifi` custom component has been **removed from HACS** and is no longer maintained. It should be uninstalled to prevent future compatibility issues.

## Proposed Changes

### 1. Remove Leftover Voice Add-ons (~1GB RAM savings)

These 4 add-ons were installed during our camera experiment and are no longer needed:

| Add-on | Container Size | Action |
|--------|---------------|--------|
| Whisper | **2.14 GB** (virtual) | **Uninstall** |
| Piper | **1.37 GB** (virtual) | **Uninstall** |
| Speech-to-Phrase | **1.0 GB** (virtual) | **Uninstall** |
| openWakeWord | **272 MB** (virtual) | **Uninstall** |

Also remove the 3 Wyoming integration entries (openWakeWord, Piper, Speech-to-Phrase) from `core.config_entries`.

---

### 2. Remove Leftover Frigate Files

Frigate frontend card files are still sitting in your `www/community` folder:
- `engine-frigate-*.js` (6 files + gzipped copies)
- `frigate-hass-card.js` (+ gzipped)
- Wyoming brands cache folder

These are dead weight and should be deleted.

---

### 3. Fix Template Errors (3 errors in logs)

**Error 1:** `sensor.dac_target_temp` returns `unknown` when the AC is off.
- **Fix:** Change `unknown` to `0` or `unavailable` in the template so HA doesn't throw an error every time the AC is off.

**Error 2:** `binary_sensor.my_wall_panel_charging` / `sensor.my_wall_panel_battery_level` template error.
- **Fix:** Add a `| default(0)` filter to the `int` conversion in the template.

---

### 4. Remove Deprecated `googlewifi` Component

HACS warns: `djtimca/hagooglewifi has been removed from HACS`. This integration is no longer maintained and will eventually break. 
- **Action:** Remove the `googlewifi` folder from `custom_components/`.
- **Action:** Remove the corresponding config entry from `core.config_entries` if present.

---

### 5. Optimize go2rtc Config (Duplicate Stream)

Your `go2rtc.yaml` has a duplicate:
- `gate_cam` → `192.168.86.20:554/stream0`
- `back_street` → `192.168.86.20:554/stream0`

Both point to the **same IP**. Is this intentional (same camera, two names) or a copy-paste error?

---

### 6. Clean Up the "Focused Local Assistant" Pipeline

The setup wizard created a second pipeline called "Focused local assistant" that uses Speech-to-Phrase (which we're uninstalling). This pipeline should be removed.

---

### 7. Recorder Optimization (Already Good!)

Your recorder config is already well-optimized:
- ✅ 5-day purge
- ✅ 30s commit interval  
- ✅ Cameras and updates excluded
- ✅ Proxmox polling sensors excluded
- ✅ Voltage/current/signal sensors excluded
- ✅ Database is a healthy 77 MB

No changes needed here.

---

## Summary of Expected Improvements

| Metric | Before | After |
|--------|--------|-------|
| Running containers | 15 | 11 |
| Available RAM | ~1.7 GB | ~2.5+ GB |
| Log errors per cycle | 3 | 0 |
| Dead files on disk | ~8 files | 0 |
| Deprecated components | 1 | 0 |

## Verification Plan

### Automated Tests
- Check `docker ps` count drops from 15 to 11
- Check `free -h` shows increased available memory
- Check `docker logs homeassistant` for zero ERROR lines after restart
- Verify all dashboards still load correctly

### Manual Verification
- Confirm the voice assistant still works from your browser/phone (using Google AI STT/TTS + Gemini)
- Confirm cameras still stream properly on kiosk dashboard
