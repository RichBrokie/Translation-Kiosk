import os
import sys
import json
import glob
import subprocess

# Let's inspect additional details:
# 1. Text/subtitle/transcript files alongside audio files
transcript_files = []
for root, dirs, files in os.walk('/mnt/models'):
    for f in files:
        if f.lower().endswith(('.txt', '.vtt', '.srt', '.json', '.tsv', '.csv')):
            transcript_files.append(os.path.join(root, f))

print(f"Transcript/text files in /mnt/models: {len(transcript_files)}")
for tf in transcript_files[:30]:
    print("  ", tf)

# 2. Check /home/ubuntu/translation_kiosk contents in detail
tk_path = '/home/ubuntu/translation_kiosk'
print(f"\nListing {tk_path}:")
if os.path.exists(tk_path):
    for root, dirs, files in os.walk(tk_path):
        print(f"Directory: {root}")
        for d in dirs:
            print(f"  [DIR]  {d}")
        for f in files:
            fp = os.path.join(root, f)
            st = os.stat(fp)
            print(f"  [FILE] {f} ({st.st_size} bytes, mode={oct(st.st_mode)})")
else:
    print("  Directory does not exist!")

# 3. Check systemd service files
print("\nSystemd services check:")
services = ['audio-kiosk.service', 'vllm.service', 'translation-kiosk.service']
for s in services:
    res = subprocess.run(['systemctl', 'status', s], capture_output=True, text=True)
    print(f"--- {s} ---")
    print(res.stdout[:500] if res.stdout else res.stderr[:500])

# 4. Check if /etc/systemd/system/translation-kiosk.service exists
for loc in ['/etc/systemd/system/translation-kiosk.service', '/lib/systemd/system/translation-kiosk.service']:
    if os.path.exists(loc):
        print(f"Found {loc}:")
        with open(loc) as f:
            print(f.read())
    else:
        print(f"{loc} does not exist.")

# 5. Check if user ubuntu has sudo access without password
res = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
print(f"\nsudo -n true return code: {res.returncode} (0 means passwordless sudo available)")

