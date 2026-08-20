import sys, asyncio, time
sys.path.insert(0, '/home/ubuntu/translation_kiosk')
sys.path.insert(0, '/home/ubuntu/translation_kiosk/tests')
from conftest import load_real_speech_sample
from whisper_client import WhisperClient
from qwen_client import QwenClient

async def test_multilingual():
    languages = [
        ("es", "Spanish"),
        ("fr", "French"),
        ("de", "German"),
        ("zh", "Mandarin Chinese"),
        ("ar", "Standard Arabic"),
        ("ru", "Russian"),
        ("ja", "Japanese"),
        ("en", "English")
    ]
    w_client = WhisperClient(base_url='http://localhost:8001')
    q_client = QwenClient(base_url='http://localhost:8000/v1')
    
    for code, name in languages:
        pcm, wav = load_real_speech_sample(code, start_sec=15.0, duration_sec=4.0)
        t0 = time.perf_counter()
        w_res = await w_client.transcribe_wav(wav)
        w_lat = (time.perf_counter() - t0) * 1000.0
        
        t0 = time.perf_counter()
        q_res = await q_client.post_correct_and_translate(w_res.text, source_language=w_res.language)
        q_lat = (time.perf_counter() - t0) * 1000.0
        
        print(f"[{code.upper()}] ({name}) -> Detected: {w_res.language} (W: {w_lat:.1f}ms | Q: {q_lat:.1f}ms)")
        print(f"   ASR:   {w_res.text}")
        print(f"   Trans: {q_res.english_translation}")
        print()
        
    await w_client.close()
    await q_client.close()

asyncio.run(test_multilingual())
