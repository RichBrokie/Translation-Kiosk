import os
import json
import subprocess
import glob

def get_audio_info(filepath):
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', filepath
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), {})
        fmt = data.get('format', {})
        return {
            'path': filepath,
            'filename': os.path.basename(filepath),
            'codec': stream.get('codec_name'),
            'sample_rate': int(stream.get('sample_rate', 0)) if stream.get('sample_rate') else None,
            'channels': stream.get('channels'),
            'bits_per_sample': stream.get('bits_per_sample') or stream.get('bits_per_raw_sample'),
            'duration_sec': float(fmt.get('duration', 0)),
            'size_bytes': int(fmt.get('size', 0)),
        }
    except Exception as e:
        return {'path': filepath, 'error': str(e)}

def scan_dir(base_dir):
    results = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac')):
                p = os.path.join(root, f)
                rel = os.path.relpath(p, base_dir)
                cat = rel.split(os.sep)[0]
                if cat not in results:
                    results[cat] = []
                results[cat].append(get_audio_info(p))
    return results

if __name__ == '__main__':
    data = scan_dir('/mnt/models')
    print("=== MNT MODELS AUDIO SCAN SUMMARY ===")
    total_files = 0
    total_duration = 0.0
    category_summary = {}
    for cat, items in sorted(data.items()):
        total_files += len(items)
        cat_dur = sum(item.get('duration_sec', 0) for item in items if 'duration_sec' in item)
        total_duration += cat_dur
        sr_set = list(set(item.get('sample_rate') for item in items if 'sample_rate' in item))
        ch_set = list(set(item.get('channels') for item in items if 'channels' in item))
        category_summary[cat] = {
            'count': len(items),
            'duration_minutes': round(cat_dur / 60.0, 2),
            'sample_rates': sr_set,
            'channels': ch_set,
            'files': items
        }
        print(f"Category: {cat:25s} | Files: {len(items):3d} | Dur: {cat_dur/60:6.1f}m | SR: {sr_set} | Ch: {ch_set}")

    print(f"\nTOTAL: {total_files} audio files, {total_duration/3600:.2f} hours")

    # Inspect /tmp
    tmp_files = glob.glob('/tmp/*.wav') + glob.glob('/tmp/*.mp3')
    print(f"\n=== TMP AUDIO FILES ({len(tmp_files)}) ===")
    tmp_items = []
    for f in sorted(tmp_files):
        info = get_audio_info(f)
        tmp_items.append(info)
        print(f"{info.get('filename'):20s} | {info.get('sample_rate')}Hz | {info.get('channels')}ch | {info.get('duration_sec',0):5.2f}s | {info.get('size_bytes')}B")

    with open('/tmp/audio_inventory.json', 'w', encoding='utf-8') as f:
        json.dump({'models': category_summary, 'tmp': tmp_items, 'total_files': total_files, 'total_duration_sec': total_duration}, f, indent=2, ensure_ascii=False)
    print("\nSaved full inventory to /tmp/audio_inventory.json")
