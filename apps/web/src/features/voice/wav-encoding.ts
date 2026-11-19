/** Whisper works at 16 kHz mono: the browser sends exactly that, so the server never has to guess the format. */
export const SPEECH_SAMPLE_RATE = 16_000;

/** Averages the channels, then resamples by linear interpolation. */
export function toSpeechSamples(channels: readonly Float32Array[], sampleRate: number): Float32Array {
  const length = channels[0]?.length ?? 0;
  const mono = new Float32Array(length);
  for (const channel of channels) {
    for (let i = 0; i < length; i++) mono[i] = (mono[i] ?? 0) + (channel[i] ?? 0) / channels.length;
  }
  if (sampleRate === SPEECH_SAMPLE_RATE || length === 0) return mono;
  const outLength = Math.max(1, Math.round((length * SPEECH_SAMPLE_RATE) / sampleRate));
  const out = new Float32Array(outLength);
  const step = outLength > 1 ? (length - 1) / (outLength - 1) : 0;
  for (let i = 0; i < outLength; i++) {
    const position = i * step;
    const left = Math.floor(position);
    const right = Math.min(left + 1, length - 1);
    const weight = position - left;
    out[i] = (mono[left] ?? 0) * (1 - weight) + (mono[right] ?? 0) * weight;
  }
  return out;
}

/** RIFF/WAVE, PCM 16-bit little-endian, one channel. */
export function encodeWavPcm16(samples: Float32Array, sampleRate = SPEECH_SAMPLE_RATE): ArrayBuffer {
  const dataBytes = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, dataBytes, true);
  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return buffer;
}
