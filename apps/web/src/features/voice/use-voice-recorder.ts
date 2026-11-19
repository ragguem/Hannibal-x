import { useCallback, useEffect, useRef, useState } from "react";
import { encodeWavPcm16, toSpeechSamples } from "./wav-encoding";

export type RecorderState = "idle" | "starting" | "recording" | "encoding";

/** `navigator.mediaDevices` is missing outside secure contexts (plain http) even though the DOM types say otherwise. */
const microphoneAvailable = () => "mediaDevices" in navigator && "getUserMedia" in navigator.mediaDevices;

/** Decodes whatever the browser recorded (webm, ogg…) and re-encodes it as 16 kHz mono WAV. */
async function toSpeechWav(recorded: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await recorded.arrayBuffer());
    const channels = Array.from({ length: decoded.numberOfChannels }, (_, i) => decoded.getChannelData(i));
    return new Blob([encodeWavPcm16(toSpeechSamples(channels, decoded.sampleRate))], { type: "audio/wav" });
  } finally {
    void context.close();
  }
}

/**
 * Push-to-talk: `start` opens the microphone, `stop` closes it and hands over the WAV.
 * A `stop` that arrives while the microphone is still opening ends the recording as soon as it starts.
 */
export function useVoiceRecorder(onRecording: (wav: Blob) => void) {
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const stopRequested = useRef(false);
  const isStopRequested = useCallback(() => stopRequested.current, []);
  const onRecordingRef = useRef(onRecording);

  useEffect(() => {
    onRecordingRef.current = onRecording;
  }, [onRecording]);

  const start = useCallback(async () => {
    if (recorderRef.current) return;
    if (!microphoneAvailable()) {
      setError("Micro indisponible dans ce navigateur : importez un fichier WAV.");
      return;
    }
    setError(null);
    stopRequested.current = false;
    setState("starting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      setState("idle");
      setError("Accès au micro refusé.");
      return;
    }
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => chunks.push(event.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      setState("encoding");
      toSpeechWav(new Blob(chunks, { type: recorder.mimeType }))
        .then((wav) => onRecordingRef.current(wav))
        .catch(() => setError("Enregistrement illisible, recommencez."))
        .finally(() => setState("idle"));
    };
    recorderRef.current = recorder;
    recorder.start();
    setState("recording");
    if (isStopRequested()) recorder.stop();
  }, [isStopRequested]);

  const stop = useCallback(() => {
    stopRequested.current = true;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  useEffect(
    () => () => {
      const recorder = recorderRef.current;
      if (recorder?.state === "recording") {
        recorder.onstop = null;
        recorder.stop();
        recorder.stream.getTracks().forEach((track) => track.stop());
      }
    },
    [],
  );

  return { state, error, start, stop };
}
