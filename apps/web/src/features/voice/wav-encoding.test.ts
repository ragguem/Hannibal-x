import { describe, expect, it } from "vitest";
import { encodeWavPcm16, SPEECH_SAMPLE_RATE, toSpeechSamples } from "./wav-encoding";

describe("toSpeechSamples", () => {
  it("averages stereo into mono", () => {
    const out = toSpeechSamples([new Float32Array([1, 0]), new Float32Array([0, 0.5])], SPEECH_SAMPLE_RATE);
    expect(Array.from(out)).toEqual([0.5, 0.25]);
  });

  it("resamples 48 kHz to 16 kHz", () => {
    const second = new Float32Array(48_000).fill(0.25);
    const out = toSpeechSamples([second], 48_000);
    expect(out.length).toBe(16_000);
    expect(out[8_000]).toBeCloseTo(0.25);
  });
});

describe("encodeWavPcm16", () => {
  it("writes a 16 kHz mono PCM header and clamps samples", () => {
    const view = new DataView(encodeWavPcm16(new Float32Array([0, 1, -1, 2])));
    const text = (offset: number, length: number) =>
      String.fromCharCode(...Array.from({ length }, (_, i) => view.getUint8(offset + i)));
    expect(text(0, 4)).toBe("RIFF");
    expect(text(8, 4)).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16_000);
    expect(view.getUint32(40, true)).toBe(8);
    expect([0, 1, 2, 3].map((i) => view.getInt16(44 + i * 2, true))).toEqual([0, 32767, -32768, 32767]);
  });
});
