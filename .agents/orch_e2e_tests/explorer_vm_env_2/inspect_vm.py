import os
import sys
import json
import glob
import wave
import subprocess
import shutil
import importlib.metadata
import pathlib

result = {}

# 1. Host and System Information
result['system'] = {
    'platform': sys.platform,
    'python_version': sys.version,
    'python_executable': sys.executable,
}

# CPU and Memory info
try:
    with open('/proc/cpuinfo') as f:
        cpuinfo = f.read()
    cores = [line for line in cpuinfo.splitlines() if 'model name' in line]
    result['system']['cpu_cores'] = len(cores)
    result['system']['cpu_model'] = cores[0].split(':')[1].strip() if cores else 'Unknown'
except Exception as e:
    result['system']['cpu_error'] = str(e)

try:
    with open('/proc/meminfo') as f:
        meminfo = f.read()
    mem_total = [line for line in meminfo.splitlines() if 'MemTotal' in line]
    result['system']['mem_total'] = mem_total[0].split(':')[1].strip() if mem_total else 'Unknown'
except Exception as e:
    result['system']['mem_error'] = str(e)

# GPU info
try:
    res = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version', '--format=csv,noheader'], capture_output=True, text=True)
    result['system']['gpu'] = res.stdout.strip()
except Exception as e:
    result['system']['gpu_error'] = str(e)

# System tools
tools = ['ffmpeg', 'ffprobe', 'sox', 'git', 'curl', 'wget', 'nvidia-smi', 'systemctl', 'ss', 'tar', 'unzip']
tool_paths = {}
for t in tools:
    tool_paths[t] = shutil.which(t)
result['system']['tools'] = tool_paths

# Tool versions
try:
    res = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    result['system']['ffmpeg_version'] = res.stdout.splitlines()[0] if res.stdout else 'None'
except Exception as e:
    result['system']['ffmpeg_version'] = str(e)

try:
    res = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True)
    result['system']['ffprobe_version'] = res.stdout.splitlines()[0] if res.stdout else 'None'
except Exception as e:
    result['system']['ffprobe_version'] = str(e)


# 2. Installed Python Packages in /home/ubuntu/ai_kiosk/bin/python
target_packages = [
    'pytest', 'pytest-asyncio', 'pytest-mock', 'pytest-cov',
    'httpx', 'websockets', 'soundfile', 'requests', 'fastapi',
    'uvicorn', 'pydantic', 'pydantic-settings', 'faster-whisper',
    'openai', 'aiohttp', 'torch', 'torchaudio', 'scipy', 'numpy',
    'python-multipart', 'starlette', 'jinja2', 'psutil', 'vllm'
]

pkg_status = {}
for pkg in target_packages:
    try:
        ver = importlib.metadata.version(pkg)
        pkg_status[pkg] = {'installed': True, 'version': ver}
    except Exception as e:
        pkg_status[pkg] = {'installed': False, 'error': str(e)}
result['targeted_packages'] = pkg_status

# All installed packages dictionary
all_pkgs = {}
for dist in importlib.metadata.distributions():
    all_pkgs[dist.metadata['Name']] = dist.version
result['all_packages_count'] = len(all_pkgs)
result['all_packages'] = all_pkgs


# 3. Directory Structures: /mnt, /mnt/models, /home/ubuntu, /home/ubuntu/translation_kiosk
def summarize_dir(path, max_depth=2, current_depth=0):
    if not os.path.exists(path):
        return {'exists': False}
    st = os.stat(path)
    entry = {
        'exists': True,
        'path': path,
        'is_dir': os.path.isdir(path),
        'mode': oct(st.st_mode),
        'size': st.st_size,
    }
    if os.path.isdir(path) and current_depth < max_depth:
        children = []
        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                item_st = os.stat(item_path)
                item_info = {
                    'name': item,
                    'is_dir': os.path.isdir(item_path),
                    'size': item_st.st_size,
                    'mode': oct(item_st.st_mode),
                }
                if os.path.isdir(item_path) and current_depth + 1 < max_depth:
                    item_info['children'] = [c for c in sorted(os.listdir(item_path))[:20]]
                children.append(item_info)
            entry['children'] = children
        except Exception as e:
            entry['error'] = str(e)
    return entry

result['dirs'] = {
    '/mnt': summarize_dir('/mnt', max_depth=3),
    '/mnt/models': summarize_dir('/mnt/models', max_depth=2),
    '/home/ubuntu': summarize_dir('/home/ubuntu', max_depth=2),
    '/home/ubuntu/translation_kiosk': summarize_dir('/home/ubuntu/translation_kiosk', max_depth=4)
}

# Detailed check of /home/ubuntu/translation_kiosk
tk_path = '/home/ubuntu/translation_kiosk'
if os.path.exists(tk_path):
    st = os.stat(tk_path)
    result['translation_kiosk_details'] = {
        'exists': True,
        'writable_by_current_user': os.access(tk_path, os.W_OK),
        'readable_by_current_user': os.access(tk_path, os.R_OK),
        'executable_by_current_user': os.access(tk_path, os.X_OK),
        'owner_uid': st.st_uid,
        'group_gid': st.st_gid,
        'full_tree': []
    }
    for root, dirs, files in os.walk(tk_path):
        for f in files:
            fp = os.path.join(root, f)
            fst = os.stat(fp)
            result['translation_kiosk_details']['full_tree'].append({
                'rel_path': os.path.relpath(fp, tk_path),
                'size': fst.st_size,
                'mode': oct(fst.st_mode)
            })
else:
    result['translation_kiosk_details'] = {'exists': False}


# 4. Comprehensive Audio File Discovery and Inspection
audio_extensions = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma')

# Search directories
search_roots = ['/mnt/models', '/home/ubuntu', '/mnt']
audio_files = []

for root_dir in search_roots:
    if not os.path.exists(root_dir):
        continue
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith(audio_extensions):
                full_path = os.path.join(root, f)
                audio_files.append(full_path)

audio_files = sorted(list(set(audio_files)))
result['total_audio_files_found'] = len(audio_files)

# Detailed analysis of each audio file
audio_details = []

for af in audio_files:
    info = {
        'path': af,
        'filename': os.path.basename(af),
        'directory': os.path.dirname(af),
        'size_bytes': os.path.getsize(af),
    }
    
    # Check parent folder for language context
    parent_folder = os.path.basename(os.path.dirname(af))
    info['parent_folder'] = parent_folder
    
    # Try reading with wave module
    if af.lower().endswith('.wav'):
        try:
            with wave.open(af, 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                duration_sec = nframes / float(framerate) if framerate > 0 else 0
                info['channels'] = channels
                info['sample_width_bytes'] = sample_width
                info['sample_width_bits'] = sample_width * 8
                info['sample_rate'] = framerate
                info['nframes'] = nframes
                info['duration_sec'] = round(duration_sec, 3)
                info['method'] = 'wave'
        except Exception as e:
            info['wave_error'] = str(e)
            
    # Try ffprobe if needed or for all files
    if 'sample_rate' not in info or not info.get('duration_sec'):
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', af
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                probe_data = json.loads(res.stdout)
                fmt = probe_data.get('format', {})
                streams = probe_data.get('streams', [])
                audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
                
                info['format_name'] = fmt.get('format_name')
                info['duration_sec'] = round(float(fmt.get('duration', 0)), 3)
                info['bit_rate'] = fmt.get('bit_rate')
                info['sample_rate'] = int(audio_stream.get('sample_rate', 0))
                info['channels'] = int(audio_stream.get('channels', 0))
                info['codec_name'] = audio_stream.get('codec_name')
                info['bits_per_sample'] = audio_stream.get('bits_per_sample')
                info['method'] = 'ffprobe'
        except Exception as e:
            info['ffprobe_error'] = str(e)
            
    audio_details.append(info)

result['audio_files'] = audio_details

# Group audio files by language / folder
languages_summary = {}
for af in audio_details:
    folder = af.get('parent_folder', 'unknown')
    if folder not in languages_summary:
        languages_summary[folder] = {
            'count': 0,
            'files': [],
            'sample_rates': set(),
            'channels': set(),
            'total_duration_sec': 0.0,
        }
    languages_summary[folder]['count'] += 1
    languages_summary[folder]['files'].append({
        'filename': af['filename'],
        'duration_sec': af.get('duration_sec', 0),
        'sample_rate': af.get('sample_rate', 0),
        'channels': af.get('channels', 0),
        'size_bytes': af.get('size_bytes', 0)
    })
    if 'sample_rate' in af:
        languages_summary[folder]['sample_rates'].add(af['sample_rate'])
    if 'channels' in af:
        languages_summary[folder]['channels'].add(af['channels'])
    languages_summary[folder]['total_duration_sec'] += af.get('duration_sec', 0)

# Convert sets to lists for JSON serialization
for folder, data in languages_summary.items():
    data['sample_rates'] = list(data['sample_rates'])
    data['channels'] = list(data['channels'])
    data['total_duration_sec'] = round(data['total_duration_sec'], 2)

result['audio_languages_summary'] = languages_summary

# Save to /tmp/vm_investigation_complete.json
with open('/tmp/vm_investigation_complete.json', 'w') as f:
    json.dump(result, f, indent=2)

print(f"SUCCESS: Completed investigation. Found {len(audio_files)} audio files across {len(languages_summary)} folders.")
print(f"Output saved to /tmp/vm_investigation_complete.json")
