class AudioWorkletProcessorPCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 2048; // ~128ms chunks at 16kHz
    this.buffer = new Int16Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const inputChannel = input[0];
    const inRate = sampleRate; // provided by AudioWorkletGlobalScope
    const outRate = 16000;
    const ratio = inRate / outRate;

    for (let i = 0; i < inputChannel.length; i += ratio) {
      const idx = Math.floor(i);
      let s = inputChannel[idx] || 0;
      s = Math.max(-1.0, Math.min(1.0, s));
      this.buffer[this.bufferIndex++] = s < 0 ? s * 0x8000 : s * 0x7FFF;

      if (this.bufferIndex >= this.bufferSize) {
        this.port.postMessage(this.buffer.buffer, [this.buffer.buffer]);
        this.buffer = new Int16Array(this.bufferSize);
        this.bufferIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor('pcm-worklet-processor', AudioWorkletProcessorPCM);