import { useEffect, useRef } from "react";
import type { RadioMessage } from "../../socle/ports";

/** Reads new radio messages aloud (English, as transmitted). Silent where speech synthesis is missing. */
export function useSpeech(messages: RadioMessage[], enabled: boolean): void {
  const lastSpoken = useRef<number | null>(null);

  useEffect(() => {
    const newest = messages.at(-1)?.id ?? null;
    if (!enabled || !("speechSynthesis" in window)) {
      lastSpoken.current = newest;
      return;
    }
    const fresh = messages.filter((m) => lastSpoken.current === null || m.id > lastSpoken.current);
    lastSpoken.current = newest;
    for (const m of fresh) {
      const utterance = new SpeechSynthesisUtterance(m.text_en);
      utterance.lang = "en-GB";
      window.speechSynthesis.speak(utterance);
    }
  }, [messages, enabled]);

  useEffect(() => () => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);
}
