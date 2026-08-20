import os
import glob
import wave
import json

models_dir = '/mnt/models'
entries = sorted(os.listdir(models_dir))

report = {}

for entry in entries:
    full_path = os.path.join(models_dir, entry)
    if not os.path.isdir(full_path) or entry.startswith('$') or entry == 'System Volume Information':
        continue
    
    files = os.listdir(full_path)
    wav_files = [f for f in files if f.lower().endswith('.wav')]
    other_audio = [f for f in files if f.lower().endswith(('.mp3', '.flac', '.m4a', '.aac'))]
    srt_files = [f for f in files if f.lower().endswith(('.srt', '.vtt'))]
    txt_files = [f for f in files if f.lower().endswith(('.txt', '.json', '.csv', '.tsv'))]
    
    wav_details = []
    total_dur = 0.0
    for w in wav_files:
        wp = os.path.join(full_path, w)
        try:
            with wave.open(wp, 'rb') as wf:
                dur = wf.getnframes() / float(wf.getframerate())
                total_dur += dur
                wav_details.append({
                    'name': w,
                    'duration_sec': round(dur, 2),
                    'sample_rate': wf.getframerate(),
                    'channels': wf.getnchannels(),
                    'bit_depth': wf.getsampwidth() * 8,
                    'size_mb': round(os.path.getsize(wp) / (1024*1024), 2)
                })
        except Exception as e:
            wav_details.append({'name': w, 'error': str(e)})
            
    report[entry] = {
        'total_files': len(files),
        'wav_count': len(wav_files),
        'other_audio_count': len(other_audio),
        'srt_count': len(srt_files),
        'txt_count': len(txt_files),
        'total_duration_sec': round(total_dur, 2),
        'total_duration_min': round(total_dur / 60, 2),
        'wav_details': wav_details,
        'srt_files': srt_files,
        'txt_files': txt_files
    }

print(json.dumps(report, indent=2))
