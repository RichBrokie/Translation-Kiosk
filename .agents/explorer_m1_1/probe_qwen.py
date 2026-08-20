import time
import json
import httpx

client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

test_cases = [
    {
        "lang": "Spanish",
        "raw_text": "hola buenas tardes esto es una una prueba del del quiosco de traducción"
    },
    {
        "lang": "French",
        "raw_text": "bonjour je voudrais visiter le le musée s il vous plaît"
    },
    {
        "lang": "German",
        "raw_text": "guten tag wo ist der eingang zum zur ausstellung"
    },
    {
        "lang": "Chinese",
        "raw_text": "你好请问请问这个展览在在哪里"
    },
    {
        "lang": "Arabic",
        "raw_text": "مرحبا اين اين يقع متحف الفنون"
    }
]

system_prompt = (
    "You are a real-time translation kiosk assistant. "
    "Clean and post-correct the transcribed text (fixing ASR repetitions, grammar, punctuation in the source language) "
    "and translate it to English. "
    "Output MUST be a valid JSON object with exactly two keys: 'corrected_text' (the cleaned source language text) "
    "and 'english_translation' (the fluent English translation). Do not output any other text or markdown fences."
)

print("=== Testing Qwen 2.5 72B Instruct via vLLM ===\n")

for tc in test_cases:
    payload = {
        "model": "/mnt/models/qwen2.5-72b-instruct-awq",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Source Language: {tc['lang']}\nTranscribed Text: {tc['raw_text']}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 256
    }
    
    t0 = time.perf_counter()
    resp = client.post("/v1/chat/completions", json=payload)
    latency_ms = (time.perf_counter() - t0) * 1000
    
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        tok_per_sec = (completion_tokens / (latency_ms / 1000)) if latency_ms > 0 else 0
        
        print(f"[{tc['lang']}] Status: {resp.status_code} | Latency: {latency_ms:.1f} ms | Prompt Toks: {prompt_tokens} | Comp Toks: {completion_tokens} ({tok_per_sec:.1f} tok/s)")
        try:
            parsed = json.loads(content)
            print(f"  Corrected: {parsed.get('corrected_text')}")
            print(f"  English:   {parsed.get('english_translation')}")
        except Exception as e:
            print(f"  JSON Parse Error: {e}")
            print(f"  Raw Content: {content}")
    else:
        print(f"[{tc['lang']}] Error {resp.status_code}: {resp.text}")
    print()
