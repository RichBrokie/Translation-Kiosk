import sys, glob, wave, io, asyncio, os
import numpy as np
from scipy.signal import resample
sys.path.insert(0, '/home/ubuntu/translation_kiosk')
from whisper_client import WhisperClient

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
    files = glob.glob('/mnt/models/Mandarin Chinese Talks/*.wav')
    for f in files:
        fname = os.path.basename(f)
        for sec in [30.0, 60.0, 120.0]:
            try:
                with wave.open(f, 'rb') as wf:
                    in_sr = wf.getframerate()
                    n_ch = wf.getnchannels()
                    wf.setpos(int(sec * in_sr))
                    raw = wf.readframes(int(4.0 * in_sr))
                    arr = np.frombuffer(raw, dtype=np.int16)
                    if n_ch > 1:
                        arr = arr.reshape(-1, n_ch).mean(axis=1).astype(np.int16)
                    arr = np.clip(resample(arr.astype(np.float32), int(len(arr) * 16000 / in_sr)), -32768, 32767).astype(np.int16)
                    pcm = arr.tobytes()
                    wav = package_wav(pcm)
                tr = await w.transcribe_wav(wav)
                print(f'{fname[:30]} ({sec}s) -> {tr.language}: "{tr.text[:30]}"')
                if tr.language == 'zh':
                    print(f'*** FOUND ZH FILE: {fname} at {sec}s ***')
                    break
            except Exception as e:
                pass
    await w.close()

asyncio.run(main())
