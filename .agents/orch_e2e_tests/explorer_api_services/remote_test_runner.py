import time
import requests
import json
import subprocess
import glob
import os

def run_tests():
    report = {}
    
    print("==================================================")
    print("1. FASTER-WHISPER ASR BENCHMARK & SCHEMA AUDIT")
    print("==================================================")
    
    asr_results = []
    
    # Check synthetic audio
    for dur in [1, 2, 4, 6, 8, 12, 16]:
        synth_path = f"/tmp/synth_{dur}s.wav"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}", "-ar", "16000", "-ac", "1", synth_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.perf_counter()
        with open(synth_path, "rb") as f:
            resp = requests.post("http://localhost:8001/transcribe", files={"file": (f"synth_{dur}s.wav", f, "audio/wav")})
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        
        data = resp.json() if resp.status_code == 200 else {"error": resp.text}
        asr_results.append({
            "type": "synthetic_sine",
            "duration_sec": dur,
            "latency_ms": round(lat_ms, 2),
            "status_code": resp.status_code,
            "response": data
        })
        print(f"Synthetic {dur:2d}s audio -> Status: {resp.status_code}, Latency: {lat_ms:6.2f} ms, Response: {data}")
    
    # Check real speech across languages
    lang_folders = [
        ("Spanish", "es", "/mnt/models/Spanish Talks"),
        ("French", "fr", "/mnt/models/French Talks"),
        ("German", "de", "/mnt/models/German Talks"),
        ("Japanese", "ja", "/mnt/models/Japanese Talks"),
        ("English", "en", "/mnt/models/English Talks"),
        ("Mandarin", "zh", "/mnt/models/Mandarin Chinese Talks"),
        ("Russian", "ru", "/mnt/models/Russian Talks"),
        ("Arabic", "ar", "/mnt/models/Standard Arabic Talks"),
        ("Portuguese", "pt", "/mnt/models/Portuguese Talks"),
        ("Turkish", "tr", "/mnt/models/Turkish Talks"),
    ]
    
    for lang_name, expected_code, folder in lang_folders:
        wav_files = glob.glob(os.path.join(folder, "*.wav"))
        if not wav_files:
            continue
        sample_file = wav_files[0]
        clip_path = f"/tmp/speech_{lang_name}_4s.wav"
        # Extract 4 seconds starting at 20s
        subprocess.run(["ffmpeg", "-y", "-i", sample_file, "-ss", "20", "-t", "4", "-ar", "16000", "-ac", "1", clip_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        t0 = time.perf_counter()
        with open(clip_path, "rb") as f:
            resp = requests.post("http://localhost:8001/transcribe", files={"file": (os.path.basename(clip_path), f, "audio/wav")})
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
            
        asr_results.append({
            "type": "real_speech",
            "language_name": lang_name,
            "expected_code": expected_code,
            "duration_sec": 4,
            "latency_ms": round(lat_ms, 2),
            "status_code": resp.status_code,
            "detected_lang": data.get("language"),
            "text": data.get("text", "").strip()
        })
        print(f"Speech {lang_name:10s} (4s) -> Status: {resp.status_code}, Latency: {lat_ms:6.2f} ms | Lang: {data.get('language')} | Text: {data.get('text', '').strip()[:80]}")

    # Edge cases
    print("\n--- Testing Whisper Edge Cases ---")
    # Empty file
    t0 = time.perf_counter()
    resp = requests.post("http://localhost:8001/transcribe", files={"file": ("empty.wav", b"", "audio/wav")})
    t1 = time.perf_counter()
    print(f"Empty File Upload -> Status: {resp.status_code}, Latency: {(t1-t0)*1000:.2f} ms, Response: {resp.text[:100]}")
    
    # Missing file field
    resp_bad = requests.post("http://localhost:8001/transcribe", data={"not_a_file": "test"})
    print(f"Missing File Field -> Status: {resp_bad.status_code}, Response: {resp_bad.text[:100]}")

    print("\n==================================================")
    print("2. QWEN 2.5 72B INSTRUCT AWQ BENCHMARK & SCHEMA AUDIT")
    print("==================================================")
    
    # Models endpoint
    models_resp = requests.get("http://localhost:8000/v1/models")
    print(f"/v1/models: {models_resp.status_code}")
    model_id = models_resp.json()["data"][0]["id"]
    print(f"Model ID: {model_id}")
    
    system_prompt = (
        "You are an expert real-time translation kiosk engine.\n"
        "Your task:\n"
        "1. Take raw, potentially noisy or error-prone ASR speech transcripts in any language.\n"
        "2. Contextually correct any grammatical, phonetic, or boundary stitching errors in the source language.\n"
        "3. Accurately translate the corrected text into natural, fluent English.\n"
        "Output strictly valid JSON with exactly two fields:\n"
        "{\n"
        '  "corrected_text": "<corrected transcript in source language>",\n'
        '  "english_translation": "<fluent English translation>"\n'
        "}"
    )
    
    llm_test_cases = [
        ("Spanish", "es", "en el segundo piso de las cosas que se quedan a medias podran encontrar"),
        ("French", "fr", "ne sest jamais donne les moyens de ses ambitions un homme qui sest oublie"),
        ("German", "de", "weil es oft leider reduziert wird auf attraktive menschen"),
        ("Japanese", "ja", "美術館へようこそ 本日の特別展をご案内いたします"),
        ("Mandarin", "zh", "欢迎来到自然历史博物馆 今天我们将探索古代恐龙的世界"),
        ("Russian", "ru", "Добро пожаловать в наш музей науки и технологий"),
        ("Arabic", "ar", "صباح الخير ومرحباً بكم في متحف الفنون الجميلة"),
        ("English (ASR typo)", "en", "i wan to welcom you to our musuem of modren art today we see painting"),
    ]
    
    llm_results = []
    for lang_name, lang_code, raw_text in llm_test_cases:
        user_prompt = f"Source Language: {lang_name} ({lang_code})\nRaw ASR Transcript: \"{raw_text}\"\n\nProduce JSON output with corrected_text and english_translation."
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "response_format": {"type": "json_object"}
        }
        
        t0 = time.perf_counter()
        resp = requests.post("http://localhost:8000/v1/chat/completions", json=payload)
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        
        if resp.status_code == 200:
            res_json = resp.json()
            raw_content = res_json["choices"][0]["message"]["content"]
            usage = res_json.get("usage", {})
            try:
                parsed = json.loads(raw_content)
                parse_ok = True
            except Exception as e:
                parsed = {"error": str(e)}
                parse_ok = False
            
            llm_results.append({
                "language": lang_name,
                "code": lang_code,
                "raw_input": raw_text,
                "latency_ms": round(lat_ms, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "json_valid": parse_ok,
                "corrected_text": parsed.get("corrected_text"),
                "english_translation": parsed.get("english_translation")
            })
            print(f"\n--- {lang_name} ({lang_code}) ---")
            print(f"Latency: {lat_ms:6.2f} ms | Tokens: {usage.get('total_tokens')} (Prompt: {usage.get('prompt_tokens')}, Comp: {usage.get('completion_tokens')})")
            print(f"Corrected : {parsed.get('corrected_text')}")
            print(f"Translated: {parsed.get('english_translation')}")
        else:
            print(f"LLM call failed for {lang_name}: Status {resp.status_code}, Body: {resp.text}")

    print("\n==================================================")
    print("3. PORT 8080 AND SERVICE ORCHESTRATION STATUS")
    print("==================================================")
    # Check port 8080
    try:
        r = requests.get("http://localhost:8080", timeout=2)
        p8080_status = f"Listening (Status {r.status_code})"
    except Exception as e:
        p8080_status = f"Not listening ({type(e).__name__})"
    print(f"Port 8080 Status: {p8080_status}")
    
    # Check systemd units
    units = ["audio-kiosk.service", "vllm.service", "translation-kiosk.service"]
    unit_statuses = {}
    for u in units:
        res = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True)
        unit_statuses[u] = res.stdout.strip()
        print(f"Service {u:26s}: {unit_statuses[u]}")
        
    full_dump = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_id": model_id,
        "asr_results": asr_results,
        "llm_results": llm_results,
        "port_8080_status": p8080_status,
        "service_statuses": unit_statuses
    }
    
    with open("/tmp/api_investigation_results.json", "w", encoding="utf-8") as out:
        json.dump(full_dump, out, indent=2, ensure_ascii=False)
    print("\nWrote results to /tmp/api_investigation_results.json")

if __name__ == "__main__":
    run_tests()
