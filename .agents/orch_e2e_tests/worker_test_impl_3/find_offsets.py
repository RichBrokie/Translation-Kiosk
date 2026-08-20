import sys, asyncio
sys.path.insert(0, '/home/ubuntu/translation_kiosk')
sys.path.insert(0, '/home/ubuntu/translation_kiosk/tests')
import conftest
from whisper_client import WhisperClient

async def test():
    w = WhisperClient(base_url='http://localhost:8001')
    for lang in ['es', 'fr', 'de', 'zh', 'ar', 'ru', 'ja', 'en']:
        for offset in [30.0, 45.0, 60.0, 90.0]:
            pcm, wav = conftest.load_real_speech_sample(lang, start_sec=offset, duration_sec=4.0)
            res = await w.transcribe_wav(wav)
            if res.language == lang:
                print(f'[{lang}] FOUND at offset={offset}s: lang={res.language}, text="{res.text[:40]}"')
                break
            else:
                print(f'[{lang}] offset={offset}s -> {res.language}: "{res.text[:30]}"')
    await w.close()

asyncio.run(test())
