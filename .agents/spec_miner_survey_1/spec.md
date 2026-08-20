# Technical Specification: Translation Kiosk System (UI, Admin, Systemd & Verification)

- **Document Version**: 1.0.0
- **Target Platform**: Ubuntu 24.04 LTS (Python 3.14 venv at `/home/ubuntu/ai_kiosk`, Node/Vanilla JS frontend, FastAPI/Uvicorn backend)
- **Authoritative Base**: `c:\Work\.agents\ORIGINAL_REQUEST.md`
- **Component Scope**: R1 (Public Kiosk GUI), R2 (Admin Monitoring Panel), R5 (Systemd Service Unit), Acceptance & Verification Test Framework, and WebSocket/REST Interface Contracts.

---

## 1. Executive Summary & System Overview

The Translation Kiosk is a high-reliability, real-time speech translation appliance designed for public spaces (such as museums, visitor centers, and international transit hubs). The system captures continuous multi-lingual speech via browser microphone or administrative audio stream, segments and buffers audio into overlapping chunks, executes Automatic Speech Recognition (ASR) via Faster-Whisper, performs contextual sliding-window correction and neural translation via Qwen 2.5 72B Instruct, and streams dual-pane visual transcription and translation back to the user with sub-5-second transcription latency and sub-8-second translation latency.

The web server binds to `0.0.0.0:8080`, hosting:
1. **Public Kiosk View (`/`)**: High-contrast, large-format 1920x1080 touchscreen interface optimized for museum visitors of all ages and abilities.
2. **Admin Monitoring Panel (`/admin`)**: Telemetry and diagnostics console showing live buffer status, per-chunk Whisper/Qwen latency charts, before-vs-after sliding window diff view, and full API interaction logs.
3. **WebSocket Hub (`/ws/audio`, `/ws/admin`)**: Low-latency bi-directional streaming protocol for audio chunks, transcription diffs, translation updates, and system metrics.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| F01 | Kiosk GUI (R1) | 1920x1080 Touchscreen UI | High-contrast, large-format display with dual cards for original transcription and English translation | User touch / click / browser resize | Rendered DOM with WCAG AAA contrast and clamp-scale typography | Auto-scales with CSS flexbox/grid for non-1080p viewports | ORIGINAL_REQUEST.md R1 |
| F02 | Kiosk GUI (R1) | Fullscreen Mode Controller | Native Fullscreen API integration triggering immersive mode on initial interaction or dedicated button | User tap or "Toggle Fullscreen" button | Browser enters Fullscreen mode (`document.documentElement.requestFullscreen()`) | Fallback to viewport 100vw/100vh if Fullscreen API is blocked | ORIGINAL_REQUEST.md R1, Acceptance Criteria |
| F03 | Kiosk GUI (R1) | Recording State Controller | 4-state visual lifecycle (Idle, Recording/Listening, Processing, Error) with high-visibility tactile controls | Touch/Click on "Start / Stop" button | Audio stream start/stop, visual pulse/waveform, button text/color transition | Gracefully displays error banner on permission denial or disconnection | ORIGINAL_REQUEST.md R1, Acceptance Criteria |
| F04 | Kiosk GUI (R1) | Browser Audio Capture | Web Audio API / MediaRecorder capturing microphone PCM/WAV at 16kHz mono, streaming 2s-3s chunks | User microphone input | Binary WebSocket frames or base64 WAV chunks dispatched to backend | Prompts user for microphone permission; shows high-contrast error card on denial | ORIGINAL_REQUEST.md R1, Acceptance Criteria |
| F05 | Kiosk GUI (R1) | Real-Time Transcription Stream | Live text display updating in real-time as speech is recognized; visually distinguishes interim vs finalized segments | WebSocket `transcription_update` events | Dynamic text update with smooth auto-scroll to latest recognized phrase | Retains last valid text on transient network drop | ORIGINAL_REQUEST.md R1, Acceptance Criteria |
| F06 | Kiosk GUI (R1) | English Translation Display | Completed sentence English translation stream rendered in high-prominence cards with timestamp indicators | WebSocket `translation_update` events | Rendered English sentence cards with fade-in animation | Displays fallback status if translation service is delayed | ORIGINAL_REQUEST.md R1, Acceptance Criteria |
| F07 | Kiosk GUI (R1) | Detected Source Language Badge | Dynamic pill badge indicating auto-detected language (e.g. "🌐 Spanish (Español)") and confidence | ASR language metadata from Whisper response | Visual badge in header/card with country flag/glyph and full language name | Defaults to "Detecting..." until Whisper returns language code | ORIGINAL_REQUEST.md R1, R4 |
| F08 | Admin Panel (R2) | Real-Time Diagnostics Dashboard | 12-column grid monitoring console displaying operational health, pipeline stages, and server load | WebSocket telemetry stream `/ws/admin` | Interactive dashboard with real-time gauges, charts, tables, and controls | Displays "Disconnected — Reconnecting..." overlay if backend offline | ORIGINAL_REQUEST.md R2 |
| F09 | Admin Panel (R2) | Audio Buffer Telemetry | Real-time audio buffer status tracking buffer size (KB/sec), queue depth (# chunks), and arrival timestamps | Audio buffer manager state | Numerical stat cards and buffer gauge meter | Highlights red/warning if buffer exceeds max queue depth (>5 chunks) | ORIGINAL_REQUEST.md R2 |
| F10 | Admin Panel (R2) | Whisper Latency Gauge & Chart | Live gauge and rolling historical sparkline/chart for per-chunk Whisper processing latency | Chunk Whisper execution duration (ms) | Visual gauge (0-5000ms) with color zones (Green <1s, Yellow 1-3s, Red >3s) | Flags SLA breach (>5000ms) in red | ORIGINAL_REQUEST.md R2, Acceptance Criteria |
| F11 | Admin Panel (R2) | Qwen Latency Gauge & Chart | Live gauge and rolling historical sparkline/chart for per-chunk Qwen translation/correction latency | Chunk Qwen execution duration (ms) | Visual gauge (0-8000ms) with color zones (Green <2.5s, Yellow 2.5-5s, Red >5s) | Flags SLA breach (>8000ms) in red | ORIGINAL_REQUEST.md R2, Acceptance Criteria |
| F12 | Admin Panel (R2) | End-to-End Latency Tracking | Combined timeline metric from audio chunk arrival to English translation display | Timestamps: $T_{arrive} \to T_{asr} \to T_{llm} \to T_{ui}$ | E2E Latency KPI card and breakdown stacked bar chart | Highlights bottlenecks (Whisper vs Qwen vs Network) | ORIGINAL_REQUEST.md Acceptance Criteria |
| F13 | Admin Panel (R2) | Sliding-Window Raw Text Diff View | Side-by-side comparative inspection view displaying: (1) Raw uncorrected Whisper chunk, (2) Stitched/Re-transcribed text, (3) Qwen final output | Pipeline intermediate text states per chunk | Colored diff visualization (green additions, red deletions, strike-through) | Shows "Identical (No corrections needed)" if texts match | ORIGINAL_REQUEST.md R2, R3, Acceptance Criteria |
| F14 | Admin Panel (R2) | Scrollable Live API Interaction Log | Real-time terminal/table logging all Whisper and Qwen HTTP requests, payload sizes, timestamps, status, latencies | Backend API client telemetry events | Scrollable tabular log with pause/resume, filter by API/status, and JSON export | Visual error styling (red row) for HTTP 4xx/5xx or timeouts | ORIGINAL_REQUEST.md R2, Acceptance Criteria |
| F15 | Admin Panel (R2) | Pipeline Parameter Tuner | Admin controls to adjust chunk size (s), overlap duration (s), and Qwen system prompt in real-time | Admin form input / slider controls | Dispatches configuration update via REST/WS to backend pipeline | Validates parameters (e.g. overlap < chunk_size); rejects invalid inputs | ORIGINAL_REQUEST.md R3 |
| F16 | Systemd Service (R5) | Systemd Service Unit File | Unit file `translation-kiosk.service` managing automatic startup, environment, and failure restarts | System boot / `systemctl start translation-kiosk` | Daemonized process running FastAPI server on port 8080 | Restarts on failure (`Restart=on-failure`, `RestartSec=5s`) | ORIGINAL_REQUEST.md R5, Acceptance Criteria |
| F17 | Systemd Service (R5) | Service Coexistence Manager | Explicit dependency declarations and resource management alongside `vllm.service` (8000) and `audio-kiosk.service` (8001) | `After=`, `Wants=`, port isolation (8080 vs 8000 vs 8001) | Deterministic startup order without port collisions or GPU OOM conflicts | Fails gracefully with informative journal log if dependency services are down | ORIGINAL_REQUEST.md R5, audio-kiosk.service |
| F18 | Verification Suite | Automated Audio Playback Script | CLI/Python test tool (`verify_kiosk_pipeline.py`) simulating chunked microphone streaming from sample WAV files | Audio WAV file paths, chunk duration, overlap duration | Comprehensive test report: transcription text, translation text, latency per chunk, pass/fail | Exits with non-zero code if latencies exceed SLA or assertions fail | ORIGINAL_REQUEST.md Acceptance Criteria |
| F19 | Verification Suite | English Bypass Verification | Assertion verifying that English audio bypasses Qwen translation and displays transcription directly | English audio WAV file | Confirms Qwen call count = 0, latency < 1000ms, text output matches transcription | Fails assertion if Qwen API was invoked for English source | ORIGINAL_REQUEST.md R4 |
| F20 | Verification Suite | Latency & SLA Assertion Engine | Quantitative benchmark verifying Whisper latency < 5s and E2E translation latency < 8s across languages | Audio test dataset (Spanish, French, German, Mandarin, Arabic, English) | Statistical summary: Min, Mean, P95, Max latencies per pipeline stage | Flags any chunk exceeding 5000ms (Whisper) or 8000ms (Total E2E) | ORIGINAL_REQUEST.md Acceptance Criteria |

---

## 3. Edge Cases & Boundary Conditions

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|-----------------------------|
| E01 | Audio Capture | User denies microphone permission in browser | Kiosk UI displays an amber warning banner: "Microphone Access Denied. Please enable microphone permissions in your browser bar and tap Retry." State changes to ERROR. |
| E02 | Audio Capture | Long period of silence (user stops speaking while recording is active) | Whisper returns empty text `""` or punctuation. Pipeline suppresses empty updates, maintains buffer, does not trigger unnecessary Qwen calls, UI stays in active "Listening..." state. |
| E03 | Audio Stream | High ambient background noise or non-speech audio (coughing, music) | Whisper returns hallucinated tokens (e.g. repeated words or `[Music]`). Qwen post-correction filters out noise artifacts. Admin panel logs raw vs filtered text. |
| E04 | Language Detection | Language switches mid-sentence (code-switching, e.g. "Hola, I need help") | Whisper detects dominant language per window; sliding-window update adjusts language badge smoothly without clearing existing transcript cards. |
| E05 | Language Detection | Source language is English | System identifies language as `en`. Qwen translation API call is bypassed. Transcription text is directly formatted and displayed in the translation card. Admin log records `Bypass: True`. |
| E06 | Network / WebSocket | Transient WebSocket disconnect while user is speaking | Client attempts auto-reconnection with exponential backoff (1s, 2s, 4s). On reconnect, re-establishes session ID. Audio buffer on client queues pending chunks up to 10s. |
| E07 | Backend Backend Dependency | Faster-Whisper service (port 8001) is down or restarting | Backend catches HTTP connection error, returns `503 Service Unavailable` with `ASR_UNAVAILABLE` error message. UI shows non-blocking warning "Speech recognition engine initializing...". Admin log marks red error. |
| E08 | Backend Dependency | Qwen 72B vLLM service (port 8000) is slow under heavy load (>8s) | Backend implements a 7-second timeout for Qwen. If timed out, fallback to displaying the Whisper transcription directly with a note `[Translation delayed]`. System does not crash. |
| E09 | Screen Resolution | Kiosk opened on non-1920x1080 display (e.g., 4K screen, 1280x800 tablet, or mobile phone) | CSS layout uses dynamic `clamp(min, preferred, max)` font sizes, percentage grid columns, and `min-height: 100vh` flex layouts. Content remains legible without horizontal scrollbars. |
| E10 | Touchscreen Interaction | Rapid double-tapping on "Start / Stop" button | Button debounces input by 300ms to prevent rapid toggle race conditions. UI state transition is atomic. |
| E11 | Systemd Startup | `translation-kiosk.service` starts before `vllm.service` completes weights loading (Qwen AWQ takes ~45s to load) | Kiosk server starts and serves UI immediately. Health check reports `qwen: loading`. UI indicates ready state once backend health check reaches 200 OK. |
| E12 | Sliding Window | Overlap segment contains partial/broken words at boundary | Sliding window alignment matches phonemes/tokens; Qwen prompt explicitly instructs: "Stitch and correct overlapping speech fragments into coherent, grammatical sentences." |

---

## 4. R1: Web-Based Kiosk GUI Specification (Public View on Port 8080 `/`)

### 4.1 Touchscreen Viewport & Resolution Standards
- **Reference Resolution**: 1920x1080 (16:9 Landscape Full HD Touchscreen).
- **Minimum Target Touch Target Size**: $96 \times 96\text{ px}$ for primary buttons, $64 \times 64\text{ px}$ for secondary controls (well above the WCAG 2.2 Level AAA minimum of $44 \times 44\text{ px}$).
- **Viewing Distance Optimization**: Legible from 1.5 to 3.0 meters (typical museum kiosk standing distance).
- **Responsive Auto-Fit Strategy**:
  - CSS Grid with `1fr 1fr` columns for 1080p landscape.
  - Media queries dynamically collapse to single column vertical stack if viewport aspect ratio is portrait (< 1.0) or width < 1024px.
  - All font sizes defined via CSS `clamp()` combining `rem` and `vw` units.
  - Zero horizontal overflow (`overflow-x: hidden`), full viewport containment (`height: 100vh; overflow-y: hidden`).

### 4.2 High-Contrast Color Palette & Design Tokens (WCAG AAA Compliant)

| Design Token | CSS Variable | Hex Value | Purpose & Usage | Contrast vs Background |
|--------------|--------------|-----------|-----------------|------------------------|
| **Background Dark** | `--bg-kiosk` | `#0b0f19` | Deep obsidian canvas, eliminates glare in museum environments | Baseline |
| **Surface Card** | `--surface-card` | `#161f30` | Elevated containers for Transcription & Translation panels | 2.1:1 vs Canvas |
| **Border Active** | `--border-glow` | `#2563eb` | Subtle neon blue outline for active card containers | 4.8:1 vs Canvas |
| **Text Primary** | `--text-primary` | `#ffffff` | Stark white text for completed translations & primary headers | **17.8:1** (Exceeds AAA 7:1) |
| **Text Secondary** | `--text-secondary` | `#94a3b8` | Slate silver text for timestamps, labels, and metadata | **6.5:1** (Exceeds AA 4.5:1) |
| **Text Interim** | `--text-interim` | `#38bdf8` | Bright sky blue with slight italic/pulsing for live recognized speech | **8.9:1** (Exceeds AAA) |
| **Accent Recording** | `--accent-rec` | `#ef4444` | High-visibility crimson for active recording state & Stop button | **5.2:1** |
| **Accent Ready** | `--accent-ready` | `#10b981` | Emerald green for Start button, Ready status, and English badge | **8.1:1** |
| **Accent Processing**| `--accent-proc` | `#f59e0b` | Amber gold for processing indicators | **9.4:1** |
| **Language Badge** | `--badge-lang` | `#8b5cf6` | Vibrant violet for detected source language pill | **5.6:1** |

### 4.3 Typography Hierarchy & Legibility Standards

```css
/* Typography Scale Tokens */
:root {
  --font-family-display: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-size-title: clamp(2.2rem, 3.5vw, 3.2rem);       /* 35px - 51px: Main Title */
  --font-size-trans: clamp(1.6rem, 2.2vw, 2.4rem);       /* 25px - 38px: Original Transcript */
  --font-size-trans-lg: clamp(2.0rem, 2.8vw, 3.0rem);    /* 32px - 48px: English Translation */
  --font-size-badge: clamp(1.1rem, 1.4vw, 1.5rem);       /* 17px - 24px: Language Pill & Badges */
  --font-size-button: clamp(1.5rem, 2.0vw, 2.2rem);      /* 24px - 35px: Action Buttons */
  --font-size-status: clamp(1.0rem, 1.2vw, 1.3rem);      /* 16px - 21px: Sub-status info */
  --line-height-body: 1.45;
  --letter-spacing-wide: 0.02em;
}
```

### 4.4 Spatial Layout & Wireframe Blueprint

```
+---------------------------------------------------------------------------------------------------+
|  [🌐 GLOBAL TRANSLATION KIOSK]                       [DETECTED: 🇪🇸 Spanish (Español)]  [⛶ FULLSCREEN] |
+---------------------------------------------------------------------------------------------------+
|                                                 |                                                 |
|  ORIGINAL SPEECH (LIVE TRANSCRIPTION)           |  ENGLISH TRANSLATION                            |
|  +-------------------------------------------+  |  +-------------------------------------------+  |
|  | [14:02:11]                                |  |  | [14:02:12]                                |  |
|  | "Bienvenidos a la exposición de arte        |  |  | "Welcome to the modern art exhibition.     |  |
|  | moderno. Esta sala contiene obras..."     |  |  |  This room contains works from..."        |  |
|  |                                           |  |  |                                           |  |
|  | [14:02:15] (Interim live text)            |  |  | [14:02:16]                                |  |
|  | > "...del siglo veinte que exploran..."   |  |  | "..."                                     |  |
|  |   [~~~ ılılılllıılıl Audio Pulse ~~~]     |  |  |                                           |  |
|  +-------------------------------------------+  |  +-------------------------------------------+  |
|                                                 |                                                 |
+---------------------------------------------------------------------------------------------------+
|               [ ● RECORDING... 00:14 ]            [ ■ STOP TRANSLATION ]                          |
|         Status: Transcribing live audio... (Whisper: 180ms | Qwen: 820ms)                         |
+---------------------------------------------------------------------------------------------------+
```

### 4.5 Fullscreen Lifecycle & Auto-Fit Handling
- **Activation Triggers**:
  1. Top-right dedicated touchscreen button: `[ ⛶ Fullscreen ]`.
  2. First user interaction tap anywhere on the greeting modal/screen.
  3. Keyboard shortcut: `F11` or `KeyF`.
- **Implementation Mechanism**:
  ```javascript
  function toggleFullScreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        console.warn(`Fullscreen error: ${err.message}`);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }
  ```
- **Exit & Re-entry**: Screen remains 100% usable in windowed mode without breaking layout. Touchscreen kiosk browsers running in kiosk mode (e.g. Chromium `--kiosk`) will natively render without browser chrome.

### 4.6 UI State Machine & Visual Indicators

```
        +-------------------------------------------------------+
        |                                                       |
        v                                                       |
   +----------+   User Tap "Start"   +---------------+  Silence / Stop   +------------+
   |   IDLE   | -------------------> |   RECORDING   | ----------------> | PROCESSING |
   +----------+                      +---------------+                   +------------+
        ^                                  |                                   |
        |           Error Occurred         |                                   |
        +----------------------------------+-----------------------------------+
                                           |
                                           v
                                     +-----------+
                                     |   ERROR   |
                                     +-----------+
```

1. **`IDLE` State**:
   - **Button**: Huge Emerald Green button `[ 🎙️ Touch to Start Speaking ]`.
   - **Visual Pulse**: Gentle breathing glow around microphone icon.
   - **Banner**: "Speak in any language — instant English translation."
   - **Transcription/Translation Panels**: Display clear greeting instructions or previous session archive.
2. **`RECORDING` (Listening) State**:
   - **Button**: Pulsing Crimson button `[ ⏹️ Stop Recording ]`.
   - **Visualizer**: Real-time Web Audio API waveform / dynamic audio level bars reacting to mic volume.
   - **Header Indicator**: Glowing Red badge `● LIVE RECORDING [00:12]`.
   - **Status Text**: "Listening... Speak naturally."
3. **`PROCESSING` State**:
   - **Button**: Disabled Amber button `[ ⏳ Finalizing Translation... ]`.
   - **Visualizer**: Smooth wave animation.
   - **Status Text**: "Completing final sentences..." (Transitions to `IDLE` after queue flushes within 1.5s).
4. **`ERROR` State**:
   - **Card**: High-contrast amber/red alert card centered on screen.
   - **Content**: Clear explanation (e.g. "Microphone unavailable" or "Server connection lost").
   - **Action**: Direct `[ 🔄 Try Again ]` button.

### 4.7 Real-Time Live Transcription Display
- **Chunk Stream Format**: As Whisper processes 2s-3s audio slices, raw transcribed text is appended.
- **Visual Staging**:
  - *Finalized Text*: Rendered in `--text-primary` (`#ffffff`), regular weight, grouped into paragraphs/sentences.
  - *Interim / Active Window*: Rendered in `--text-interim` (`#38bdf8`), italicized with a subtle typewriter fade effect.
- **Auto-Scroll Behavior**: Container features sticky bottom scrolling (`scrollTop = scrollHeight`) with a 500ms smooth animation, pausing if the user manually scrolls up to inspect previous sentences.

### 4.8 Completed Sentence English Translation Display
- **Sentence Grouping**: Translations are rendered in card bubbles as complete thoughts are returned by Qwen.
- **Metadata**: Each card shows an optional subtle timestamp (e.g. `14:02:15`) and sentence completion checkmark.
- **Bypass Mode (English Source)**: If Whisper detects English (`en`), the translation panel displays the cleaned English transcript immediately with an indicator `[English Source - Direct Stream]`, avoiding unnecessary LLM latency.

### 4.9 Detected Source Language Badge
- **Badge Anatomy**:
  - Icon: Country flag emoji or globe glyph `🌐`.
  - Language Code & Name: Formatted from ISO-639-1 code to full display name (e.g., `es` $\to$ `Spanish (Español)`, `zh` $\to$ `Mandarin (中文)`, `fr` $\to$ `French (Français)`, `de` $\to$ `German (Deutsch)`, `ar` $\to$ `Arabic (العربية)`).
  - Confidence Indicator: Whisper probability badge (e.g., `99%`).
- **Animation**: Subtle scale/fade transition when language changes.

### 4.10 Browser Audio Capture Specification
- **Audio Constraints**:
  ```javascript
  const audioConstraints = {
    audio: {
      channelCount: 1,
      sampleRate: 16000,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    },
    video: false
  };
  ```
- **Chunking Pipeline**:
  - `MediaRecorder` or `AudioWorkletNode` slicing audio into 2000ms buffers.
  - Formatted as standard 16-bit PCM WAV before streaming over WebSocket binary channel.

---

## 5. R2: Admin Monitoring Panel Specification (`/admin` on Port 8080)

### 5.1 Dashboard Architecture & Wireframe Blueprint

```
+---------------------------------------------------------------------------------------------------+
|  [⚙️ TRANSLATION KIOSK — ADMIN CONTROL & DIAGNOSTICS]               [UPTIME: 04:18:22] [WS: CONNECTED] |
+---------------------------------------------------------------------------------------------------+
|  SYSTEM HEALTH & AUDIO BUFFER       |  WHISPER ASR METRICS            |  QWEN 72B LLM METRICS        |
|  - Buffer Duration: 2.0s            |  - Last Latency: 215ms          |  - Last Latency: 840ms       |
|  - Queue Depth: 0 chunks            |  - Rolling Avg (P95): 290ms     |  - Rolling Avg (P95): 1120ms |
|  - Audio Chunks Ingested: 1,420     |  - Active Language: es (98%)    |  - Total E2E Latency: 1055ms |
|  - Audio Dropouts / Jitter: 0ms     |  - Model: whisper-large-v3-ct2  |  - Model: qwen2.5-72b-awq    |
|  [==== Buffer Level: 15% ====]     |  [==== ASR Gauge: 215ms ====]   |  [==== LLM Gauge: 840ms ===] |
+---------------------------------------------------------------------------------------------------+
|  REAL-TIME LATENCY TIMELINE (LAST 50 CHUNKS)                                                      |
|  ms ^                                                                                             |
| 1500|       --.-.---.----. (Qwen Translation Latency: ~800-1100ms)                                |
| 1000|                                                                                             |
|  500|   ..................... (Whisper ASR Latency: ~200-300ms)                                   |
|    0+-----------------------------------------------------------------------------------> chunks  |
+---------------------------------------------------------------------------------------------------+
|  SLIDING-WINDOW TRANSCRIPTION DIFF VIEWER (BEFORE VS AFTER CORRECTION)                             |
|  Chunk #42 [Spanish]                                                                              |
|  [RAW WHISPER CHUNK]     : "el arte moderno tiene un impacto"                                     |
|  [WINDOW RE-TRANSCRIBED] : "el arte moderno tiene un gran impacto en la sociedad"                 |
|  [QWEN POST-CORRECTED]   : "El arte moderno tiene un gran impacto en la sociedad actual."          |
|  [ENGLISH TRANSLATION]   : "Modern art has a great impact on today's society."                    |
+---------------------------------------------------------------------------------------------------+
|  LIVE API INTERACTION LOG                                                                         |
|  [TIMESTAMP]      [API]      [ENDPOINT]            [SIZE]    [STATUS]  [LATENCY]  [DETAILS]       |
|  14:02:18.120     Whisper    POST :8001/transcribe 96.0 KB   200 OK    215ms      Lang: es (0.98) |
|  14:02:18.340     Qwen 72B   POST :8000/v1/chat/.. 1.2 KB    200 OK    840ms      Tokens: 28      |
|  14:02:20.125     Whisper    POST :8001/transcribe 96.0 KB   200 OK    198ms      Lang: es (0.99) |
|  [ ⏸️ Pause Log ]  [ 🗑️ Clear ]  [ 📥 Export JSON ]  [ Filter: All | Whisper | Qwen | Errors ]   |
+---------------------------------------------------------------------------------------------------+
|  PIPELINE CONFIGURATION & OVERRIDES                                                               |
|  Chunk Size: [ 3.0s ]  Overlap: [ 1.5s ]  Temperature: [ 0.2 ]  [ 💾 Apply Changes ] [ 🧪 Test Audio]|
+---------------------------------------------------------------------------------------------------+
```

### 5.2 Real-Time Audio Buffer Telemetry Specifications
- **Monitored Metrics**:
  - `buffer_size_bytes`: Current raw audio byte length in memory.
  - `buffer_duration_sec`: Converted time length ($bytes / (16000 \times 2)$).
  - `queue_depth`: Number of audio slices currently waiting for Whisper processing worker.
  - `chunk_arrival_timestamp`: Microsecond timestamp of arrival from WebSocket.
  - `inter_chunk_jitter_ms`: Delta variation between expected chunk interval (e.g. 2000ms) and actual arrival time.
- **Visual Alert Thresholds**:
  - Normal: Queue depth 0-1, Buffer $\le 3.0\text{s}$ (Green).
  - Warning: Queue depth 2-3, Buffer 3.0s - 6.0s (Yellow).
  - Critical: Queue depth $>3$, Buffer $>6.0\text{s}$ (Red, Audio drop risk).

### 5.3 Whisper ASR Latency Gauge & Rolling History
- **Metric**: Elapsed execution time of `POST http://localhost:8001/transcribe`.
- **Target SLA**: $< 1000\text{ms}$ (Hard upper limit $< 5000\text{ms}$).
- **Visualization**:
  - Radial or Linear Gauge: $0 - 3000\text{ms}$.
  - Sparkline: Last 50 chunks rolling historical trend.
  - Stats Summary: Min, Max, Mean, P95.

### 5.4 Qwen 72B Latency Gauge & Rolling History
- **Metric**: Elapsed execution time of `POST http://localhost:8000/v1/chat/completions`.
- **Target SLA**: $< 2500\text{ms}$ (Hard upper limit $< 8000\text{ms}$).
- **Visualization**:
  - Radial or Linear Gauge: $0 - 5000\text{ms}$.
  - Sparkline: Last 50 translation requests.
  - Token Throughput: Tokens generated / sec.

### 5.5 Sliding-Window Raw Text Diff View
- **Purpose**: Provides administrative proof that the sliding-window mechanism actively repairs audio recognition errors.
- **4-Stage Text Pipeline Comparison**:
  1. *Stage 1 (Isolated Chunk)*: Raw transcription of the single newest audio slice.
  2. *Stage 2 (Overlapped Window)*: Re-transcription of $(\text{Tail of Previous Chunk} + \text{New Chunk})$.
  3. *Stage 3 (Qwen Post-Correction)*: Grammar, punctuation, and context-refined source text.
  4. *Stage 4 (Qwen Translation)*: English translation output.
- **Diff Highlighting**: Words inserted or modified by sliding-window re-transcription are highlighted with a green background (`#065f46`); words corrected or trimmed are rendered with a strike-through red badge (`#7f1d1d`).

### 5.6 Scrollable Live API Interaction Log
- **Event Log Schema**:
  ```json
  {
    "id": "log_a8f9c1e0",
    "timestamp": "2026-08-19T14:02:18.120Z",
    "api": "Whisper",
    "endpoint": "http://localhost:8001/transcribe",
    "method": "POST",
    "request_size_bytes": 96044,
    "response_status": 200,
    "latency_ms": 215,
    "request_summary": "WAV audio (3.0s, 16kHz, mono)",
    "response_summary": "Detected: es (0.98) | Text: 'el arte moderno tiene un impacto'"
  }
  ```
- **Interactive Capabilities**:
  - Live Auto-scroll with toggle button `[ Pause / Resume ]`.
  - Filter by API (`All`, `Whisper Only`, `Qwen Only`, `Errors Only`).
  - Search input filtering by keyword in request/response.
  - `[ Export JSON / CSV ]` button downloading the full session diagnostic log.

---

## 6. Communication Protocols & API Contracts

### 6.1 WebSocket Endpoint Architecture

The application exposes two dedicated WebSocket endpoints on port 8080:
1. `ws://<host>:8080/ws/audio` — Kiosk client connection for bidirectional audio streaming, live transcript updates, and translations.
2. `ws://<host>:8080/ws/admin` — Admin dashboard connection for real-time telemetry, latency metrics, diff streaming, and log events.

### 6.2 Client-to-Server Protocol (`/ws/audio`)

#### 6.2.1 Audio Chunk Frame (Binary or JSON)
Binary frame containing raw 16-bit PCM WAV audio, or JSON frame:
```json
{
  "type": "audio_chunk",
  "session_id": "sess_89a0b1",
  "chunk_index": 4,
  "timestamp": 1724076138120,
  "audio_data": "<base64_encoded_pcm_wav>"
}
```

#### 6.2.2 Control Commands
```json
// Start Recording Session
{
  "type": "session_start",
  "session_id": "sess_89a0b1",
  "sample_rate": 16000,
  "channels": 1
}

// Stop Recording Session
{
  "type": "session_stop",
  "session_id": "sess_89a0b1"
}

// Reset / Clear Display
{
  "type": "reset"
}
```

### 6.3 Server-to-Client Protocol (`/ws/audio`)

#### 6.3.1 Status & Lifecycle
```json
{
  "type": "status_update",
  "status": "recording", // "idle" | "recording" | "processing" | "error"
  "message": "Listening..."
}
```

#### 6.3.2 Language Detected
```json
{
  "type": "language_detected",
  "language_code": "es",
  "language_name": "Spanish",
  "confidence": 0.984
}
```

#### 6.3.3 Transcription Update
```json
{
  "type": "transcription_update",
  "chunk_id": 4,
  "text": "Bienvenidos a la exposición de arte moderno.",
  "is_final": true,
  "raw_chunk_text": "Bienvenidos a la exposicion de arte",
  "corrected_text": "Bienvenidos a la exposición de arte moderno."
}
```

#### 6.3.4 Translation Update
```json
{
  "type": "translation_update",
  "chunk_id": 4,
  "source_text": "Bienvenidos a la exposición de arte moderno.",
  "translation": "Welcome to the modern art exhibition.",
  "is_complete_sentence": true,
  "latency_ms": 780,
  "bypass_llm": false
}
```

#### 6.3.5 Error Message
```json
{
  "type": "error",
  "error_code": "ASR_SERVICE_UNAVAILABLE",
  "message": "Speech recognition service on port 8001 is not responding.",
  "recoverable": true
}
```

### 6.4 Server-to-Admin Protocol (`/ws/admin`)

#### 6.4.1 Telemetry Snapshot & Chunk Metrics
```json
{
  "type": "chunk_metrics",
  "timestamp": "2026-08-19T14:02:18.340Z",
  "chunk_id": 4,
  "audio_duration_sec": 3.0,
  "whisper_latency_ms": 215,
  "qwen_latency_ms": 840,
  "e2e_latency_ms": 1055,
  "source_language": "es",
  "source_language_prob": 0.984,
  "bypass_qwen": false,
  "text_raw": "Bienvenidos a la exposicion de arte",
  "text_window_retranscribed": "Bienvenidos a la exposición de arte moderno.",
  "text_qwen_corrected": "Bienvenidos a la exposición de arte moderno.",
  "text_translated": "Welcome to the modern art exhibition.",
  "buffer_queue_depth": 0,
  "buffer_duration_sec": 1.5
}
```

#### 6.4.2 API Call Log Event
```json
{
  "type": "api_log",
  "id": "log_8921",
  "timestamp": "2026-08-19T14:02:18.120Z",
  "api": "Whisper",
  "endpoint": "http://localhost:8001/transcribe",
  "request_size_bytes": 96044,
  "response_status": 200,
  "latency_ms": 215,
  "summary": "Transcribed 3.0s audio -> 'es' (0.98)"
}
```

### 6.5 REST API Specifications

| Method | Path | Purpose | Request Body | Response Body |
|--------|------|---------|--------------|---------------|
| `GET` | `/` | Serves the Public Kiosk HTML/JS/CSS GUI | None | `text/html` |
| `GET` | `/admin` | Serves the Admin Monitoring Dashboard HTML/JS/CSS | None | `text/html` |
| `GET` | `/api/health` | Service health status check | None | `{"status": "healthy", "whisper": "ok", "qwen": "ok", "uptime_sec": 1234}` |
| `POST` | `/api/simulate` | Simulates audio processing from uploaded WAV file | `multipart/form-data` (`file`: WAV) | `{"transcription": "...", "translation": "...", "language": "...", "metrics": {...}}` |
| `GET` | `/api/config` | Retrieves current pipeline configuration | None | `{"chunk_duration": 3.0, "overlap_duration": 1.5, "qwen_model": "..."}` |
| `POST` | `/api/config` | Updates pipeline parameters | `{"chunk_duration": 3.0, "overlap_duration": 1.5}` | `{"status": "updated", "config": {...}}` |
| `GET` | `/api/logs` | Fetches historical API interaction logs | Query: `?limit=100&api=all` | `{"logs": [...]}` |

### 6.6 External Backend API Contracts (Unmodified Endpoints)

#### 6.6.1 Faster-Whisper ASR API
- **URL**: `POST http://localhost:8001/transcribe`
- **Headers**: `Content-Type: multipart/form-data`
- **Body**: Form field `file` containing valid WAV binary audio data.
- **Response**:
  ```json
  {
    "text": " Bienvenidos a la exposición de arte moderno.",
    "language": "es"
  }
  ```

#### 6.6.2 Qwen 2.5 72B Instruct AWQ API (vLLM OpenAI-Compatible)
- **URL**: `POST http://localhost:8000/v1/chat/completions`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "model": "/mnt/models/qwen2.5-72b-instruct-awq",
    "messages": [
      {
        "role": "system",
        "content": "You are a real-time translation engine for a museum kiosk. Your task is to take the provided speech transcription, fix any minor grammatical or sliding-window stitching errors, and translate the text accurately and naturally into English. Output ONLY the English translation without explanation or quotes."
      },
      {
        "role": "user",
        "content": "Bienvenidos a la exposición de arte moderno."
      }
    ],
    "temperature": 0.1,
    "max_tokens": 256
  }
  ```
- **Response**:
  ```json
  {
    "id": "chatcmpl-98a1",
    "object": "chat.completion",
    "created": 1724076138,
    "model": "/mnt/models/qwen2.5-72b-instruct-awq",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "Welcome to the modern art exhibition."
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 84,
      "completion_tokens": 9,
      "total_tokens": 93
    }
  }
  ```

---

## 7. R5: Systemd Service Unit File Specification (`translation-kiosk.service`)

### 7.1 Complete Systemd Unit File Definition

File location: `/etc/systemd/system/translation-kiosk.service`

```ini
[Unit]
Description=Translation Kiosk Web Application and Real-Time Audio Pipeline
Documentation=https://github.com/translation-kiosk
After=network.target vllm.service audio-kiosk.service
Wants=vllm.service audio-kiosk.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/translation_kiosk
Environment="PATH=/home/ubuntu/ai_kiosk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="HOST=0.0.0.0"
Environment="PORT=8080"
Environment="WHISPER_URL=http://localhost:8001/transcribe"
Environment="QWEN_URL=http://localhost:8000/v1/chat/completions"
Environment="QWEN_MODEL=/mnt/models/qwen2.5-72b-instruct-awq"
Environment="CHUNK_DURATION=3.0"
Environment="OVERLAP_DURATION=1.5"

ExecStart=/home/ubuntu/ai_kiosk/bin/python server.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s
KillMode=mixed
TimeoutStopSec=10s
LimitNOFILE=65536

# Standard journal logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=translation-kiosk

[Install]
WantedBy=multi-user.target
```

### 7.2 Service Directives Analysis & Operational Justification

1. **`After=network.target vllm.service audio-kiosk.service`**:
   Ensures that systemd initializes both the Whisper ASR server and the vLLM Qwen 72B server before launching the Kiosk web application, eliminating connection errors on cold boot.
2. **`Wants=vllm.service audio-kiosk.service`**:
   Establishes a cooperative dependency where starting `translation-kiosk.service` attempts to activate both backend AI microservices if they are not already running.
3. **`User=ubuntu` / `Group=ubuntu`**:
   Runs under standard non-root privileges with full access to `/home/ubuntu/ai_kiosk` virtualenv and `/home/ubuntu/translation_kiosk` workspace.
4. **`WorkingDirectory=/home/ubuntu/translation_kiosk`**:
   Ensures static assets (`static/`, `templates/`) and configuration files resolve correctly via relative paths.
5. **`Restart=on-failure` with `RestartSec=5s`**:
   Provides high-availability kiosk resilience; automatically restarts the server within 5 seconds if an unhandled Python exception occurs.
6. **`LimitNOFILE=65536`**:
   Raises open file descriptor limits to support high-concurrency WebSocket connections and audio temporary files.

### 7.3 Multi-Service Coexistence & Port Segregation Matrix

| Service Unit | Port | Protocol | Process / Component | Memory / Resource Footprint |
|--------------|------|----------|---------------------|-----------------------------|
| `vllm.service` | `8000` | HTTP (OpenAI Chat API) | vLLM Qwen 2.5 72B AWQ | GPU VRAM (~40-44 GB AWQ on CUDA) |
| `audio-kiosk.service` | `8001` | HTTP (FastAPI `/transcribe`) | Faster-Whisper Large-v3-Turbo | GPU/Host RAM (~2-4 GB VRAM/RAM) |
| `translation-kiosk.service` | `8080` | HTTP / WebSocket | FastAPI / Uvicorn Kiosk Server | Host CPU / RAM (~200-500 MB RAM) |

---

## 8. Acceptance & Verification Test Scripts Specification

### 8.1 Automated Verification Script (`verify_kiosk_pipeline.py`)

A standalone Python test tool verifying the entire pipeline end-to-end by simulating chunked microphone audio streaming against live backend services.

#### 8.1.1 Command-Line Interface Specification
```bash
# Run full automated verification suite across test fixtures
/home/ubuntu/ai_kiosk/bin/python verify_kiosk_pipeline.py \
  --kiosk-url http://localhost:8080 \
  --fixtures-dir ./test_fixtures \
  --output-report ./verification_report.json \
  --strict-latency
```

#### 8.1.2 Functional Workflow Architecture
1. **Health Check Probe**: Queries `GET http://localhost:8080/api/health`, `http://localhost:8001/docs`, and `http://localhost:8000/v1/models` to confirm all 3 services are online.
2. **Audio Chunk Simulation**:
   - Reads source WAV file (e.g. `spanish_sample.wav`, 16kHz mono).
   - Slices audio into 2.0s chunks with 1.0s overlap.
   - Dispatches chunks sequentially over WebSocket (`/ws/audio`) or `/api/simulate` at real-time playback cadence (or accelerated burst mode).
3. **Telemetry & Output Capture**:
   - Captures timestamp of chunk dispatch ($T_0$).
   - Captures timestamp of `transcription_update` ($T_{trans}$).
   - Captures timestamp of `translation_update` ($T_{translat}$).
   - Records Whisper latency, Qwen latency, and End-to-End latency.
4. **Assertion & Evaluation Suite**:
   - **Language Detection Assertion**: `detected_language == expected_language`.
   - **Whisper Latency SLA**: $T_{trans} - T_0 < 5000\text{ms}$ (Goal $< 1000\text{ms}$).
   - **Qwen / E2E Latency SLA**: $T_{translat} - T_0 < 8000\text{ms}$ (Goal $< 2500\text{ms}$).
   - **English Bypass Assertion**: When input is English, verify zero Qwen calls and immediate transcript display.
   - **Transcription & Translation Quality**: Semantic fuzzy matching or Levenshtein distance against reference transcriptions.

### 8.2 Test Fixtures & Multilingual Verification Dataset

| Fixture File | Source Language | Reference Transcript | Expected English Translation |
|--------------|-----------------|----------------------|------------------------------|
| `test_es_01.wav` | Spanish (`es`) | "Bienvenidos a la exposición de arte moderno." | "Welcome to the modern art exhibition." |
| `test_fr_01.wav` | French (`fr`) | "Le musée est ouvert tous les jours sauf le lundi." | "The museum is open every day except Monday." |
| `test_de_01.wav` | German (`de`) | "Wo befindet sich der Ausgang zum Garten?" | "Where is the exit to the garden?" |
| `test_zh_01.wav` | Chinese (`zh`) | "请问现代艺术展厅在哪里？" | "Excuse me, where is the modern art exhibition hall?" |
| `test_ar_01.wav` | Arabic (`ar`) | "أين يمكنني شراء تذاكر الدخول للمتحف؟" | "Where can I buy museum entrance tickets?" |
| `test_en_01.wav` | English (`en`) | "Could you please tell me what time the guided tour starts?" | "Could you please tell me what time the guided tour starts?" (Bypasses Qwen) |

### 8.3 SLA Benchmark & Latency Target Table

| Metric | Target (Nominal) | Upper SLA Bound (Failure Limit) | Measurement Point |
|--------|------------------|---------------------------------|-------------------|
| **Speech-to-Transcription Latency** | $< 1000\text{ms}$ | **$< 5000\text{ms}$** | Chunk sent $\to$ `transcription_update` received |
| **Speech-to-Translation Latency** | $< 2500\text{ms}$ | **$< 8000\text{ms}$** | Chunk sent $\to$ `translation_update` received |
| **English Direct Stream Latency** | $< 800\text{ms}$ | **$< 3000\text{ms}$** | Chunk sent $\to$ direct English display |
| **Kiosk Web GUI First Contentful Paint** | $< 500\text{ms}$ | **$< 2000\text{ms}$** | Browser HTTP GET `/` $\to$ DOM ready |
| **Admin Panel Telemetry Refresh Jitter** | $< 50\text{ms}$ | **$< 500\text{ms}$** | WS `/ws/admin` broadcast delta |

---

## 9. Verification Method & Compliance Checklist

To independently verify the completeness and validity of this specification:

1. **Verify Kiosk GUI Specifications**:
   - Inspect Section 4 for 1920x1080 responsive layout, WCAG AAA color tokens, and 4-state UI lifecycle.
   - Verify that all visual requirements from `ORIGINAL_REQUEST.md` (R1) are fully specified.
2. **Verify Admin Dashboard Specifications**:
   - Inspect Section 5 for real-time telemetry, Whisper/Qwen gauges, sliding-window diff viewer, and API interaction logs per `ORIGINAL_REQUEST.md` (R2).
3. **Verify Systemd Service Specifications**:
   - Inspect Section 7 for exact systemd unit directives, virtualenv path `/home/ubuntu/ai_kiosk/bin/python`, working directory `/home/ubuntu/translation_kiosk`, and non-conflicting port allocation (8080 vs 8000 vs 8001).
4. **Verify Test Script Specifications**:
   - Inspect Section 8 for the automated playback test architecture, latency assertions (<5s Whisper, <8s E2E), and multilingual test coverage.
