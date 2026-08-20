import os
import wave
import json

audio_exts = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac')

other_audios = []
# search /home/ubuntu
for root, dirs, files in os.walk('/home/ubuntu'):
    for f in files:
        if f.lower().endswith(audio_exts):
            other_audios.append(os.path.join(root, f))

# search /tmp
for root, dirs, files in os.walk('/tmp'):
    for f in files:
        if f.lower().endswith(audio_exts):
            other_audios.append(os.path.join(root, f))

# search /mnt outside /mnt/models
for root, dirs, files in os.walk('/mnt'):
    if root.startswith('/mnt/models'):
        continue
    for f in files:
        if f.lower().endswith(audio_exts):
            other_audios.append(os.path.join(root, f))

print(f"Other audio files found: {len(other_audios)}")
for a in other_audios:
    st = os.stat(a)
    print(f"  {a} ({st.st_size} bytes)")
