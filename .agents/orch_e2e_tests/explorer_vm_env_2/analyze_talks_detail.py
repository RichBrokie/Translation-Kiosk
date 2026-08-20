import os
import wave
import json

models_dir = '/mnt/models'
talk_folders = [
    'Bengali Talks', 'English Talks', 'French Talks', 'German Talks',
    'Hindi Talks', 'Indonesian Talks', 'Japanese Talks', 'Mandarin Chinese Talks',
    'Portuguese Talks', 'Russian Talks', 'Spanish Talks', 'Standard Arabic Talks',
    'Turkish Talks', 'Urdu Talks'
]

summary = {}

for folder in talk_folders:
    path = os.path.join(models_dir, folder)
    if not os.path.exists(path):
        summary[folder] = {'exists': False}
        continue
    
    files = os.listdir(path)
    wav_files = sorted([f for f in files if f.lower().endswith('.wav')])
    srt_files = sorted([f for f in files if f.lower().endswith(('.srt', '.vtt'))])
    
    wav_list = []
    total_sec = 0.0
    for w in wav_files:
        wp = os.path.join(path, w)
        size = os.path.getsize(wp)
        try:
            with wave.open(wp, 'rb') as wf:
                dur = wf.getnframes() / float(wf.getframerate())
                sr = wf.getframerate()
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                total_sec += dur
                
                # Check for corresponding srt
                base_name = os.path.splitext(w)[0]
                matching_srts = [s for s in srt_files if base_name in s or s.startswith(base_name[:20])]
                
                wav_list.append({
                    'file': w,
                    'duration_sec': round(dur, 2),
                    'duration_formatted': f"{int(dur//60)}m {int(dur%60)}s",
                    'sample_rate': sr,
                    'channels': ch,
                    'bit_depth': sw * 8,
                    'size_mb': round(size / (1024*1024), 2),
                    'matching_srts': matching_srts
                })
        except Exception as e:
            wav_list.append({'file': w, 'error': str(e), 'size_mb': round(size / (1024*1024), 2)})
            
    summary[folder] = {
        'exists': True,
        'wav_count': len(wav_files),
        'srt_count': len(srt_files),
        'total_duration_sec': round(total_sec, 2),
        'total_duration_formatted': f"{int(total_sec//3600)}h {int((total_sec%3600)//60)}m {int(total_sec%60)}s",
        'all_sample_rates': list(set(w.get('sample_rate') for w in wav_list if 'sample_rate' in w)),
        'all_channels': list(set(w.get('channels') for w in wav_list if 'channels' in w)),
        'all_bit_depths': list(set(w.get('bit_depth') for w in wav_list if 'bit_depth' in w)),
        'wavs': wav_list,
        'srts': srt_files
    }

print(json.dumps(summary, indent=2))
