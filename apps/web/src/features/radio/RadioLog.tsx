import { memo, useState } from "react";
import { clock } from "../../components/format";
import type { RadioMessage } from "../../socle/ports";
import { useSpeech } from "./use-speech";

export const RadioLog = memo(function RadioLog({ messages }: { messages: RadioMessage[] }) {
  const [speak, setSpeak] = useState(false);
  useSpeech(messages, speak);
  const latestFirst = [...messages].reverse();
  return (
    <section className="card radio" aria-labelledby="radio-title">
      <div className="row">
        <h2 id="radio-title" className="lbl grow">
          Radio
        </h2>
        <button type="button" className="btn sm" aria-pressed={speak} onClick={() => setSpeak(!speak)}>
          Lecture vocale
        </button>
      </div>
      <ol className="radio-log" role="log" aria-live="polite">
        {latestFirst.map((m) => (
          <li key={m.id} className={`msg ${m.kind}`}>
            <small className="mono mut">
              {clock(m.sent_at_s)} · {m.sender} → {m.recipient}
            </small>
            <span className="mono" lang="en">
              {m.text_en}
            </span>
            <span className="fr">{m.text_fr}</span>
          </li>
        ))}
      </ol>
    </section>
  );
});
