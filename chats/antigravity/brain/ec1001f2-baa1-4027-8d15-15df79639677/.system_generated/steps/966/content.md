Title: Live Content

Description: Fetched live

Source: https://raw.githubusercontent.com/jxlarrea/kiosk-satellite/main/README.md

---

<h1 align="center" style="border-bottom: none">
   <img alt="Kiosk Satellite for Home Assistant" src="assets/banners/kiosk_satellite_banner.png" width="650" />
</h1>

<p align="center">
<img src="https://img.shields.io/github/stars/jxlarrea/kiosk-satellite?style=for-the-badge&label=Stars&color=orange" alt="Stars">
<a href="https://github.com/jxlarrea/kiosk-satellite/releases"><img src="https://img.shields.io/github/downloads/jxlarrea/kiosk-satellite/total?style=for-the-badge&label=Downloads&color=blue" alt="Downloads"></a>
<a href="https://github.com/jxlarrea/kiosk-satellite/releases/latest"><img src="https://shields.io/github/v/release/jxlarrea/kiosk-satellite?style=for-the-badge&color=purple" alt="version"></a>
<a href="https://github.com/jxlarrea/kiosk-satellite/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/jxlarrea/kiosk-satellite/release.yml?style=for-the-badge&label=Build" alt="Build"></a>
</p>

<p align="center">
<a href="https://buymeacoffee.com/jxlarrea"><img src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

Turn any Android tablet into a beautiful, voice-enabled Home Assistant
kiosk in about two minutes.

Kiosk Satellite is an open source lightweight kiosk browser built **specifically for Home
Assistant**, and the official companion app for
[Voice Satellite](https://github.com/jxlarrea/voice-satellite-card-integration).
Mount a tablet on the wall, run the setup wizard, and you get a locked-down,
always-on dashboard that listens for your wake word natively, even while
the screen is off or another app is in front. And it is built to stay
smooth on the low-powered, older tablets that usually end up on walls.

<p align="center">
 <img src="assets/ks-demo-lossy.gif" alt="Kiosk Satellite" width="650"/>
</p>

## Main Features

&bull; **Guided setup**: a five-step wizard connects to Home Assistant, picks
  the dashboard, detects Voice Satellite, and requests only the Android
  permissions your choices need. Run it on the tablet or from a browser
  on your computer.

&bull; **Voice Satellite, natively**: the kiosk gets its own
  `assist_satellite` entity and the app's built-in engine takes over
  wake-word detection: it keeps listening with the screen off, at a
  fraction of the CPU a browser needs. No configuration in Voice
  Satellite; everything is inherited.

<p align="center">
 <img src="assets/vs-demo.gif" alt="Voice Satellite" width="650"/>
</p>

&bull; **Plain HTTP instances, fully unlocked**: a loopback proxy inside the
  app makes an `http://` dashboard a genuine secure context, so the
  microphone and the rest of the https-only browser surface work with no
  certificates or reverse proxy. Enabled automatically during setup.
  
&bull; **Fast dashboards on slow tablets**: optional
  [optimizations](docs/optimizations.md) filter Home Assistant's state
  stream down to just the entities on the view currently on screen,
  turning constant stutter on older tablets into smooth scrolling, and
  pause the dashboard's rendering while the screensaver covers it, taking
  a busy dashboard's browser from over two full cores and 70% GPU to a
  fraction of one core and 0%. The connection and Voice Satellite keep
  working throughout, and any view the filter cannot fully resolve is
  left unfiltered, so nothing ever breaks.

&bull; **Kiosk lockdown**: exit gesture with PIN, blocked back/volume/home
  buttons, a status-bar shield, instant re-wake on power button, and
  lock-task support on device-owner provisioned tablets.

&bull; **Gestures**: map corner taps, corner holds, multi-finger taps and
  holds, or a knock-code corner sequence to
  [configurable actions](docs/gestures.md): jump to a dashboard view,
  call a Home Assistant service or script, open another app and more,
  all invisible to guests.

&bull; **Sendspin player**: the tablet doubles as a synchronized
  [Sendspin](https://www.sendspin-audio.com/) speaker for Music
  Assistant, in sample-accurate sync with every other Sendspin player in
  the house, with metadata, artwork and volume in Home Assistant.

<p align="center">
 <img src="assets/screenshots/sendspin-horizontal.png" alt="Sendspin" width="650"/>
</p>

&bull; **Screensavers**: dim, black, clock, Home Assistant media, local
  folders, a photo gallery picked straight from the system picker, or an
  [Immich](docs/immich.md) library or album as a full photo frame with
  metadata overlay, all with crossfade / slide / zoom / Ken Burns
  transitions and an optional c

