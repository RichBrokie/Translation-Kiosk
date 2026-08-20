import sys
import os
import asyncio

APP_DIR = "/home/ubuntu/translation_kiosk"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from audio_pipeline import AudioPipeline, pack_pcm_to_wav, TextStitcher
from qwen_client import parse_qwen_json
from telemetry import TelemetryCollector

async def main():
    assert len(pack_pcm_to_wav(b"")) == 44
    st = TextStitcher()
    c, t, d, r = st.process_window("  ")
    assert d == ""
    p = AudioPipeline()
    assert (await p.process_chunk(b"")) is None
    assert (await p.flush()) is None
    assert parse_qwen_json("", "fb")["corrected_text"] == "fb"
    assert TelemetryCollector.compute_percentiles([])["p50"] == 0.0
    print("ALL_ADVERSARIAL_EDGE_CASES_PASSED")

if __name__ == "__main__":
    asyncio.run(main())
