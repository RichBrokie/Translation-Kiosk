import time
import requests
import json
import subprocess
import glob
import os

print('========================================')
print('1. INVESTIGATING FASTER-WHISPER ASR (:8001)')
print('========================================')

languages_to_test = [
    ('Spanish', '/mnt/models/Spanish Talks'),
    ('French', '/mnt/models/French Talks'),
    ('German', '/mnt/models/German Talks'),
    ('Japanese', '/mnt/models/Japanese Talks'),
    ('English', '/mnt/models/English Talks'),
    ('Mandarin', '/mnt/models/Mandarin Chinese Talks'),
    ('Russian', '/mnt/models/Russian Talks'),
    ('Arabic', '/mnt/models/Standard Arabic Talks'),
]

# ASR performance benchmark
for lang_name, folder in languages_to_test:
    files = glob.glob(os.path.join(folder, '*.wav'))
    if not files:
        print(f"[{lang_name}] No wav files found in {folder}")
        continue
    sample_file = files[0]
    clip_path = f"/tmp/clip_{lang_name}.wav"
    # Slicing 4 seconds
    subprocess.run(['ffmpeg', '-y', '-i', sample_file, '-ss', '15', '-t', '4', '-ar', '16000', '-ac', '1', clip_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    t0 = time.time()
    with open(clip_path, 'rb') as f:
        resp = requests.post('http://localhost:8001/transcribe', files={'file': (os.path.basename(clip_path), f, 'audio/wav')})
    t1 = time.time()
    latency_ms = (t1 - t0) * 1000
    
    print(f"--- {lang_name} (4s clip) ---")
    print(f"Status: {resp.status_code}, Latency: {latency_ms:.2f} ms")
    print(f"Payload: {resp.text}")

print('\n=== Whisper Edge Cases ===')
# Test 1: Empty file
try:
    resp = requests.post('http://localhost:8001/transcribe', files={'file': ('empty.wav', b'', 'audio/wav')})
    print(f"Empty file: Status={resp.status_code}, Body={resp.text[:200]}")
except Exception as e:
    print(f"Empty file error: {e}")

# Test 2: Different durations (1s, 2s, 4s, 8s, 16s)
sp_files = glob.glob('/mnt/models/Spanish Talks/*.wav')
if sp_files:
    sp_file = sp_files[0]
    for dur in [1, 2, 4, 8, 16]:
        clip_path = f"/tmp/sp_{dur}s.wav"
        subprocess.run(['ffmpeg', '-y', '-i', sp_file, '-ss', '20', '-t', str(dur), '-ar', '16000', '-ac', '1', clip_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        with open(clip_path, 'rb') as f:
            resp = requests.post('http://localhost:8001/transcribe', files={'file': (os.path.basename(clip_path), f, 'audio/wav')})
        t1 = time.time()
        lat = (t1 - t0) * 1000
        try:
            data = resp.json()
            text = data.get('text', '').strip()
            lang = data.get('language')
            print(f"Spanish {dur:2d}s audio: Latency={lat:6.2f} ms | Lang={lang} | Text='{text}'")
        except Exception as e:
            print(f"Spanish {dur:2d}s: Status={resp.status_code}, Response={resp.text}")

print('\n========================================')
print('2. INVESTIGATING QWEN 2.5 72B AWQ (:8000)')
print('========================================')

# Check /v1/models
models_resp = requests.get('http://localhost:8000/v1/models')
print(f"/v1/models: Status={models_resp.status_code}")
print(f"Models response: {json.dumps(models_resp.json(), indent=2)}")

model_name = models_resp.json()['data'][0]['id']
print(f"Active model name in vLLM: {model_name}")

# Test Chat Completions with Translation Prompt
system_prompt = (
    "You are an expert real-time translation kiosk engine. "
    "Your job is to take raw, potentially imperfect ASR transcripts from a spoken language, "
    "correct any phonetic or transcription errors based on context, and translate the text into natural English. "
    "Always return valid JSON with keys: \"corrected_text\" and \"english_translation\"."
)

test_transcripts = [
    ("es", "Spanish", "Hola a todos bienvenidos al museo de arte moderno hoy vamos a explorar las obras mas importantes"),
    ("fr", "French", "Bonjour tout le monde bienvenue au musee des sciences aujourd'hui nous allons decouvrir les secrets de univers"),
    ("de", "German", "Guten Tag und herzlich willkommen im historischen Museum. Wir freuen uns uber Ihren Besuch"),
    ("ja", "Japanese", "こんにちは、美術館へようこそ。本日の展示をお楽しみください。"),
    ("zh", "Chinese", "大家好欢迎来到自然历史博物馆今天我们将参观恐龙化石展区"),
    ("en", "English", "Hello everyone welcome to the exhibition today we are going to see modern sculptures"),
]

for lang_code, lang_name, text in test_transcripts:
    user_prompt = f"Source Language: {lang_name} ({lang_code})\nRaw ASR Transcript: \"{text}\"\n\nProduce JSON output with corrected_text and english_translation."
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }
    
    t0 = time.time()
    resp = requests.post("http://localhost:8000/v1/chat/completions", json=payload)
    t1 = time.time()
    lat = (t1 - t0) * 1000
    
    print(f"\n--- Qwen Chat Completion: {lang_name} ({lang_code}) ---")
    print(f"Status: {resp.status_code}, Latency: {lat:.2f} ms")
    if resp.status_code == 200:
        data = resp.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        print(f"Usage: {usage}")
        print(f"Content:\n{content}")
        try:
            parsed = json.loads(content)
            print(f"Parsed JSON successfully: corrected_text='{parsed.get('corrected_text')}', english_translation='{parsed.get('english_translation')}'")
        except Exception as e:
            print(f"Failed to parse json: {e}")
    else:
        print(f"Error Body: {resp.text}")

print('\n========================================')
print('3. INVESTIGATING PORT 8080 AND SYSTEM SERVICES')
print('========================================')
try:
    kiosk_resp = requests.get('http://localhost:8080', timeout=2)
    print(f"Port 8080 HTTP Status: {kiosk_resp.status_code}")
except Exception as e:
    print(f"Port 8080 is NOT responding (expected since app is not running): {e}")

# Check systemd services
for svc in ['vllm.service', 'audio-kiosk.service', 'translation-kiosk.service']:
    res = subprocess.run(['systemctl', 'is-active', svc], capture_output=True, text=True)
    print(f"Service '{svc}': {res.stdout.strip()} ({res.stderr.strip()})")

print('\n=== INVESTIGATION SCRIPT COMPLETE ===')
