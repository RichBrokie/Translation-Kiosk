Title: Live Content

Description: Fetched live

Source: https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/main/README.md

---

<h1 align="center" style="border-bottom: none">
   <img alt="Voice Satellite for Home Assistant" src="https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/refs/heads/main/assets/banner.png" width="650" />
</h1>

<p align="center">
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jxlarrea&repository=voice-satellite-card-integration"><img src="https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge" alt="hacs_badge"></a>
<img src="https://img.shields.io/github/stars/jxlarrea/voice-satellite-card-integration?style=for-the-badge&label=Stars&color=yellow" alt="Stars">
<a href="https://github.com/jxlarrea/voice-satellite-card-integration/releases"><img src="https://img.shields.io/github/downloads/jxlarrea/voice-satellite-card-integration/total?style=for-the-badge&label=Downloads&color=blue" alt="Downloads"></a>
<a href="https://github.com/jxlarrea/voice-satellite-card-integration/releases"><img src="https://shields.io/github/v/release/jxlarrea/voice-satellite-card-integration?style=for-the-badge&color=purple" alt="version"></a>
<a href="https://github.com/jxlarrea/voice-satellite-card-integration/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/jxlarrea/voice-satellite-card-integration/release.yml?style=for-the-badge&label=Build" alt="Build"></a>
</p>

<p align="center">
<a href="https://buymeacoffee.com/jxlarrea"><img src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

Turn any tablet, phone, or browser into a hands-free voice assistant for [Home Assistant](https://www.home-assistant.io) - like Alexa, Siri, or Google Home, but fully private and running on your own hardware. Just say the wake word and go: ask questions, control devices, set timers, get announcements, and see rich visual results - all without touching the screen.

Voice Satellite works as a drop-in integration that transforms any web browser into a full [Assist satellite](https://www.home-assistant.io/voice-pe/) with wake word detection, media playback, and visual feedback.

### Demo Video (**Make sure your volume is up**)

https://github.com/user-attachments/assets/af3956a8-3f58-420a-85ef-872ab9e33e8f

## How It Works

Voice Satellite runs as a **global engine** that loads on every page of Home Assistant - no dashboard card required. Once you assign a satellite entity in the sidebar panel, the engine starts automatically and listens for wake words across all page navigations.

- **Turns your browser into a real satellite** - registered as a proper `assist_satellite` device in HA with full feature parity with physical voice assistants
- **On-device wake word detection** - three engines, all running in the browser: **vsWakeWord** (WebGPU, purpose-built for wall-mounted tablets, best recall and zero false positives in our benchmarks, interpretable per-trigger phoneme logs), **microWakeWord** (pure-JS CPU, works on every device, lowest per-chunk latency), and **openWakeWord** (WebGPU-accelerated, broad pre-trained keyword library, near-free multi-keyword scaling). Custom model support and optional voice-activated stop interruption on all three. Falls back to server-side detection when preferred
- **Dual wake words / dual pipelines** - load two wake words simultaneously (e.g. "Okay Nabu" and "Hey Jarvis") and route each to its own Assist pipeline, so a household can mix languages, mix a local-only pipeline with a cloud/LLM one, or give each character its own conversation agent and voice
- **Timers, announcements, conversations** - voice-activated timers with countdown pills, `assist_satellite.announce` / `start_conversation` / `ask_question` from automations
- **Media player entity** - exposed as a TV-class device. Plays audio, local video files, and HLS / MJPEG camera streams full-screen on the satellite, with volume control, `tts.speak` targeting, `media_player.play_media` from automations, and Media Browser support. TTS can route to browser or a remote speaker
- **Skins** - 9 built-in skins (Default, Alexa, Google Home, Home Assistant, Ink Blobs, Lens Flares, Retro Terminal, Siri, Waveform) with CSS overrides. Reactive audio-level animation on the activity bar
- **Screensaver** - black overlay, image/video/folder from the HA media library, or live camera feed. Cross-fades between folder items; integrates with kiosk app backlight dimming and motion-dismiss (Kiosk Satellite, Fully Kiosk)
- **Mini card** - optional `voice-satellite-mini-card` for in-dashboard text display without the fullscreen overlay
- **LLM tools** *(experimental)* - image/video/web/Wikipedia search, weather, stocks/crypto with visual panels. Requires [Voice Satellite - LLM Tools](https://github.com/jxlarrea/voice-satellite-card-llm-tools)
- **Works on any device** - tablets, phones, computers, kiosks
- **Kiosk Satellite companion app** - on Android, the free official [Kiosk Satellite](https://github.com/jxlarrea/kiosk-satellite) app runs wake word detection natively: it keeps listening with the screen off or another app in front, starts on boot, and assigns the satellite entity automatically during its setup wizard

## Screenshots

<p align="center">
 <img src="https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/refs/heads/main/assets/screenshots/locks.jpg" alt="Assist" width="49%"/>
 <img src="https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/refs/heads/main/assets/screenshots/videos.jpg" alt="Video Search" width="49%"/>
 <img src="https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/refs/heads/main/assets/screenshots/weather.jpg" alt="Weather" width="49%"/>
 <img src="https://raw.githubusercontent.com/jxlarrea/voice-satellite-card-integration/refs/heads/main/assets/screenshots/currency-waveform.jpg" alt="Stocks" width="49%"/>
</p>

## Wall Tablet? Meet Kiosk Satellite

On an Android tablet, the best way to run Voice Satellite is [Kiosk Satellite](https://github.com/jxlarrea/kiosk-satellite) - the free official companion kiosk app, built specifically for Home Assistant. Voice Satellite detects it is running inside Kiosk Satellite and hands wake word detection over to the app's native engine automatically. You keep configuring everything in Voice Satellite as usual; the app's setup wizard even assigns the satellite entity for you.

Native detection removes the limits a browser puts on a wall tablet:

| Capability | Voice Satellite in a browser | Inside Kiosk Satellite |
| --- | --- | --- |
| Wake word with the dashboard on screen | ✅ | ✅ |
| Wake word with the screen off | ❌ | ✅ |
| Wake word with another app in front | ❌ | ✅ Returns to the dashboard on trigger |
| Mic acces in non-HTTPS HA instances | ❌ | ✅ |
| Detection cost | ⚠️ Browser based, heavy 

