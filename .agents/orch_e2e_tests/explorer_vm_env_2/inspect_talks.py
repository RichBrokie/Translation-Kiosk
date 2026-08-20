import os
import sys
import json
import wave
import subprocess

# Let's categorize audio files:
models_dir = '/mnt/models'
talk_dirs = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d)) and not d.startswith('$') and not d.startswith('.')]

print(f"Talks & Model Directories in /mnt/models ({len(talk_dirs)}):")
for d in sorted(talk_dirs):
    full_d = os.path.join(models_dir, d)
    files = os.listdir(full_d)
    audio_files = [f for f in files if f.lower().endswith(('.wav', '.mp3', '.flac', '.m4a'))]
    srt_files = [f for f in files if f.lower().endswith(('.srt', '.vtt', '.txt'))]
    print(f"\nDirectory: '{d}'")
    print(f"  Total items: {len(files)}, Audio files: {len(audio_files)}, Subtitle/Text files: {len(srt_files)}")
    if audio_files:
        for af in audio_files[:10]:
            af_path = os.path.join(full_d, af)
            try:
                with wave.open(af_path, 'rb') as wf:
                    ch = wf.getnchannels()
                    sr = wf.getframerate()
                    sw = wf.getsampwidth()
                    frames = wf.getnframes()
                    dur = frames / float(sr) if sr > 0 else 0
                    print(f"    - [WAV] {af[:50]}... | {dur:.1f}s | {sr}Hz | {ch}ch | {sw*8}-bit | {os.path.getsize(af_path)/1024/1024:.2f} MB")
            except Exception as e:
                # try ffprobe
                try:
                    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', af_path]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    pd = json.loads(res.stdout)
                    fmt = pd.get('format', {})
                    strm = next((s for s in pd.get('streams', []) if s.get('codec_type') == 'audio'), {})
                    print(f"    - [OTHER] {af[:50]}... | {float(fmt.get('duration', 0)):.1f}s | {strm.get('sample_rate')}Hz | {strm.get('channels')}ch | {os.path.getsize(af_path)/1024/1024:.2f} MB")
                except Exception as e2:
                    print(f"    - {af} | Error: {e} / {e2}")
        if len(audio_files) > 10:
            print(f"    ... and {len(audio_files)-10} more audio files")

