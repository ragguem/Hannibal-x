import { useCallback, useEffect, useId, type ChangeEvent } from "react";
import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import type { VoiceOrderOutcome } from "../../socle/ports";
import { useSubmitVoiceOrder } from "./use-voice-order";
import { useVoiceRecorder, type RecorderState } from "./use-voice-recorder";

const BUTTON_LABEL: Record<RecorderState, string> = {
  idle: "Maintenir pour parler",
  starting: "Ouverture du micro…",
  recording: "Relâcher pour envoyer",
  encoding: "Préparation…",
};

/** Space bar talks only when the focus is not in a field: typing a space in the order must stay a space. */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName);
}

interface VoiceCaptureProps {
  missionId: string;
  canSubmit: boolean;
  /** Command corrected by the next recording, if any. */
  correctionOf: string | null;
  onOutcome: (outcome: VoiceOrderOutcome) => void;
}

export function VoiceCapture({ missionId, canSubmit, correctionOf, onOutcome }: VoiceCaptureProps) {
  const submit = useSubmitVoiceOrder(missionId);
  const fileId = useId();
  const submitMutate = submit.mutate;

  const send = useCallback(
    (recording: Blob) =>
      submitMutate({ recording, parentId: correctionOf ?? undefined }, { onSuccess: (outcome) => onOutcome(outcome) }),
    [submitMutate, correctionOf, onOutcome],
  );
  const recorder = useVoiceRecorder(send);
  const { start, stop } = recorder;
  const busy = submit.isPending || recorder.state === "encoding";

  useEffect(() => {
    if (!canSubmit) return;
    const down = (event: KeyboardEvent) => {
      if (event.code !== "Space" || event.repeat || isTypingTarget(event.target)) return;
      event.preventDefault();
      void start();
    };
    const up = (event: KeyboardEvent) => {
      if (event.code !== "Space" || isTypingTarget(event.target)) return;
      event.preventDefault();
      stop();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [canSubmit, start, stop]);

  const importFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) send(file);
  };

  return (
    <section className="card voice" aria-labelledby="voice-title">
      <h2 id="voice-title" className="lbl">
        Ordre vocal{correctionOf ? " (correction)" : ""}
      </h2>
      <div className="row wrap">
        <button
          type="button"
          className={`btn talk ${recorder.state}`}
          aria-pressed={recorder.state === "recording"}
          disabled={!canSubmit || busy}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            void start();
          }}
          onPointerUp={stop}
          onPointerCancel={stop}
        >
          {BUTTON_LABEL[recorder.state]}
        </button>
        <label htmlFor={fileId} className="btn ghost sm">
          Importer un WAV
        </label>
        <input
          id={fileId}
          className="visually-hidden"
          type="file"
          accept="audio/wav,audio/x-wav,.wav"
          disabled={!canSubmit || busy}
          onChange={importFile}
        />
        {submit.isPending && (
          <span role="status" className="mut">
            Transcription…
          </span>
        )}
      </div>
      <p className="mut small">Ou maintenez la barre d'espace, hors des champs de saisie.</p>
      {recorder.error && <p role="alert">{recorder.error}</p>}
      {submit.error && <ErrorPanel message={describeError(submit.error).message} />}
    </section>
  );
}
