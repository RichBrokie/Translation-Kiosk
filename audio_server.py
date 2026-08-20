import os
import uvicorn
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import tempfile

app = FastAPI(title="Translation Kiosk Audio API (Whisper Only)")

print("Loading Whisper...")
whisper_model = WhisperModel("/mnt/models/whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        segments, info = whisper_model.transcribe(tmp_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return {"text": text, "language": info.language}
    finally:
        os.remove(tmp_path)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
