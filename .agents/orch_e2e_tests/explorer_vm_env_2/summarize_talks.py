import json
import sys

# Compute and print directly from /mnt/models
import os, wave

models_dir = '/mnt/models'
talk_folders = [
    'Bengali Talks', 'English Talks', 'French Talks', 'German Talks',
    'Hindi Talks', 'Indonesian Talks', 'Japanese Talks', 'Mandarin Chinese Talks',
    'Portuguese Talks', 'Russian Talks', 'Spanish Talks', 'Standard Arabic Talks',
    'Turkish Talks', 'Urdu Talks'
]

print(f"{'Folder Name':<25} | {'WAVs':<5} | {'SRTs':<5} | {'Total Duration':<15} | {'Sample Rates':<15} | {'Channels':<10} | {'Bit Depth':<10}")
print("-" * 95)

grand_total_wavs = 0
grand_total_srts = 0
grand_total_sec = 0.0

for folder in sorted(talk_folders):
    path = os.path.join(models_dir, folder)
    if not os.path.exists(path):
        continue
    
    files = os.listdir(path)
    wav_files = sorted([f for f in files if f.lower().endswith('.wav')])
    srt_files = sorted([f for f in files if f.lower().endswith(('.srt', '.vtt'))])
    
    total_sec = 0.0
    srs = set()
    chs = set()
    bds = set()
    for w in wav_files:
        wp = os.path.join(path, w)
        try:
            with wave.open(wp, 'rb') as wf:
                dur = wf.getnframes() / float(wf.getframerate())
                total_sec += dur
                srs.add(wf.getframerate())
                chs.add(wf.getnchannels())
                bds.add(wf.getsampwidth() * 8)
        except Exception:
            pass
            
    grand_total_wavs += len(wav_files)
    grand_total_srts += len(srt_files)
    grand_total_sec += total_sec
    
    total_dur_str = f"{int(total_sec//3600)}h {int((total_sec%3600)//60)}m {int(total_sec%60)}s"
    print(f"{folder:<25} | {len(wav_files):<5} | {len(srt_files):<5} | {total_dur_str:<15} | {str(list(srs)):<15} | {str(list(chs)):<10} | {str(list(bds)):<10}")

print("-" * 95)
print(f"{'TOTAL':<25} | {grand_total_wavs:<5} | {grand_total_srts:<5} | {int(grand_total_sec//3600)}h {int((grand_total_sec%3600)//60)}m {int(grand_total_sec%60)}s")
