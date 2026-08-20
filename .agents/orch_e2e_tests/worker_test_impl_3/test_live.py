import sys, asyncio, time
sys.path.insert(0, '/home/ubuntu/translation_kiosk')
sys.path.insert(0, '/home/ubuntu/translation_kiosk/tests')
from conftest import load_real_speech_sample
from whisper_client import WhisperClient
from qwen_client import QwenClient

async def test_live():
    print('Testing live Whisper :8001 on real Spanish speech...')
    pcm, wav = load_real_speech_sample('es', start_sec=2.0, duration_sec=4.0)
    w_client = WhisperClient(base_url='http://localhost:8001')
    t0 = time.perf_counter()
    w_res = await w_client.transcribe_wav(wav)
    w_lat = (time.perf_counter() - t0) * 1000.0
    print(f'Whisper Result: text="{w_res.text}", lang={w_res.language}, latency={w_lat:.2f}ms')
    
    print('Testing live Qwen :8000 on Spanish text...')
    q_client = QwenClient(base_url='http://localhost:8000/v1')
    t0 = time.perf_counter()
    q_res = await q_client.post_correct_and_translate(w_res.text, source_language=w_res.language)
    q_lat = (time.perf_counter() - t0) * 1000.0
    print(f'Qwen Result: corr="{q_res.corrected_text}", trans="{q_res.english_translation}", latency={q_lat:.2f}ms')
    
    await w_client.close()
    await q_client.close()

asyncio.run(test_live())
