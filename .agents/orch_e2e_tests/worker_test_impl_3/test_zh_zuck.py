import sys, glob, wave, io, asyncio
import numpy as np
from scipy.signal import resample
sys.path.insert(0, '/home/ubuntu/translation_kiosk')
from whisper_client import WhisperClient
from qwen_client import QwenClient

def package_wav(pcm_bytes, sample_rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

async def main():
    w = WhisperClient(base_url='http://localhost:8001')
    q = QwenClient(base_url='http://localhost:8000/v1')
    
    files = glob.glob('/mnt/models/Mandarin Chinese Talks/*Zuckerberg*.wav')
    print('Found Zuckerberg:', files)
    f = files[0]
    with wave.open(f, 'rb') as wf:
        in_sr = wf.getframerate()
        n_ch = wf.getnchannels()
        wf.setpos(int(15.0 * in_sr))
        raw = wf.readframes(int(4.0 * in_sr))
        arr = np.frombuffer(raw, dtype=np.int16)
        if n_ch > 1:
            arr = arr.reshape(-1, n_ch).mean(axis=1).astype(np.int16)
        arr = np.clip(resample(arr.astype(np.float32), int(len(arr) * 16000 / in_sr)), -32768, 32767).astype(np.int16)
        pcm = arr.tobytes()
        wav = package_wav(pcm)
        
    tr = await w.transcribe_wav(wav)
    print(f'ZH -> Lang: {tr.language} | Text: "{tr.text}"')
    if tr.language == 'zh':
        qr = await q.post_correct_and_translate(tr.text, source_language='zh')
        print(f'   Qwen Trans: "{qr.english_translation}"')
        
    await w.close()
    await q.close()

asyncio.run(main())
