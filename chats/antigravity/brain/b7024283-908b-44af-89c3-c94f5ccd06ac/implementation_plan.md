# Global TED Talk Multilingual Batch Download

This plan outlines the architecture for a massive batch script to automatically fetch 130 TED talks across 13 different languages, extracting them natively into `.wav` audio and fetching both their native and English subtitles.

## Proposed Strategy

I will author a robust Python orchestration script on your local Asus machine that loops through your requested 13 languages. 

For each language, the script will:
1. Create a cleanly named directory (e.g., `Urdu Talks`, `Spanish Talks`) inside your My Passport hard drive.
2. Interface with `yt-dlp` to execute an intelligent YouTube query (e.g., `"ytsearch10:TED talk in Urdu"`), which accurately hunts down official TED/TEDx talks spoken in that native language.
3. Use `ffmpeg` to rip the video streams and extract them directly into pristine `.wav` files.
4. Exploit the YouTube subtitle API to extract the official verified `.srt` files in **both English and the native language**.

### Language Code Mapping
To ensure we grab the exact native subtitles, I will strictly map each language to its official ISO 639-1 Subtitle Code:
- **Mandarin Chinese**: `zh-Hans,zh-Hant,zh.*`
- **Hindi**: `hi.*`
- **Spanish**: `es.*`
- **French**: `fr.*`
- **Standard Arabic**: `ar.*`
- **Bengali**: `bn.*`
- **Portuguese**: `pt.*`
- **Russian**: `ru.*`
- **Urdu**: `ur.*`
- **Indonesian**: `id.*`
- **German**: `de.*`
- **Japanese**: `ja.*`
- **Turkish**: `tr.*`

> [!TIP]
> By passing both `"en.*"` and the native code (e.g., `"en.*,ur.*"`) to `yt-dlp`, it will aggressively attempt to fetch both translations for every video, resulting in two distinct `.srt` files alongside the `.wav` file!

## User Review Required
This operation will download exactly 130 audio files and roughly 260 subtitle files. It will run in the background as a detached task so you don't have to keep your terminal open. 

Please review the language list above. If it looks perfectly correct, give me the green light and I will unleash the batch script!
