import type { HeardWord, VoiceOrderOutcome } from "../../socle/ports";
import { ReadingDetails } from "./ReadingDetails";

/** Below this, the word is shown as doubtful: the operator checks it before approving. */
export const DOUBTFUL_CONFIDENCE = 0.6;

function HeardText({ transcript, words }: { transcript: string; words: HeardWord[] }) {
  if (words.length === 0) return <>{transcript || "(rien entendu)"}</>;
  return (
    <>
      {words.map((w, i) => (
        <span key={`${String(i)}-${w.word}`}>
          {i > 0 && " "}
          {w.confidence < DOUBTFUL_CONFIDENCE ? (
            <mark title={`confiance ${String(Math.round(w.confidence * 100))} %`}>{w.word}</mark>
          ) : (
            w.word
          )}
        </span>
      ))}
    </>
  );
}

interface InterpretationCardProps {
  outcome: VoiceOrderOutcome;
  canSubmit: boolean;
  /** Puts the transcript in the order field; `commandId` is set when there is a command to correct. */
  onCorrect: (transcript: string, commandId: string | null) => void;
  onDismiss: () => void;
}

/** What was heard, then what the server understood from it — or why it did not. */
export function InterpretationCard({ outcome, canSubmit, onCorrect, onDismiss }: InterpretationCardProps) {
  return (
    <section className={`card interpretation ${outcome.accepted ? "ok" : "refused"}`} aria-labelledby="interpretation-title">
      <h2 id="interpretation-title" className="lbl">
        Entendu
      </h2>
      <p className="mono heard" lang="en">
        <HeardText transcript={outcome.transcript} words={outcome.heard_words} />
      </p>
      {outcome.accepted ? (
        <p role="status" className="accepted">
          Compris : <span className="mono">{outcome.text_en}</span>
          {outcome.text_fr && <span className="fr"> · {outcome.text_fr}</span>}
        </p>
      ) : (
        <div role="alert" className="refusal">
          <b>Non reconnu :</b> {outcome.refusal_reason}
          {outcome.hint && <p className="mut">{outcome.hint}</p>}
        </div>
      )}
      <ReadingDetails outcome={outcome} />
      <div className="row">
        <small className="mut grow">Transcrit en {outcome.transcription_seconds.toFixed(1)} s</small>
        {canSubmit && (
          <button type="button" className="btn sm" onClick={() => onCorrect(outcome.transcript, outcome.command_id ?? null)}>
            Corriger au clavier
          </button>
        )}
        <button type="button" className="btn ghost sm" onClick={onDismiss}>
          Fermer
        </button>
      </div>
    </section>
  );
}
