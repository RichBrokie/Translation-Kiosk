import os
import json

models_dir = '/mnt/models'
model_folders = ['qwen2.5-72b-instruct-awq', 'whisper-large-v3-turbo', 'whisper-large-v3-turbo-ct2', 'gpt-oss-120b', 'gpt-oss-120b-awq', 'pyannote-3.1']

for mf in model_folders:
    p = os.path.join(models_dir, mf)
    if not os.path.exists(p):
        print(f"{mf}: NOT FOUND")
        continue
    files = os.listdir(p)
    total_size = sum(os.path.getsize(os.path.join(p, f)) for f in files if os.path.isfile(os.path.join(p, f)))
    print(f"\nModel: {mf}")
    print(f"  Path: {p}")
    print(f"  Total size: {total_size / (1024*1024*1024):.2f} GB ({len(files)} files)")
    print(f"  Files:")
    for f in sorted(files):
        fp = os.path.join(p, f)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp) / (1024*1024)
            print(f"    - {f} ({sz:.2f} MB)")
        else:
            print(f"    - [DIR] {f}")
    # If config.json exists, show a few key attributes
    cfg_path = os.path.join(p, 'config.json')
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as cf:
                cfg = json.load(cf)
                print(f"  Config preview: architectures={cfg.get('architectures')}, model_type={cfg.get('model_type')}, quantization={cfg.get('quantization_config')}")
        except Exception as e:
            print(f"  Config error: {e}")
