import { useId, useState, type SyntheticEvent } from "react";
import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import type { OrderMode, Simulation } from "../../socle/ports";
import { ReadingDetails } from "./ReadingDetails";
import { useSimulateOrder, useSubmitOrder } from "./use-orders";

interface OrderFormProps {
  missionId: string;
  draft: string;
  onDraftChange: (text: string) => void;
  canSubmit: boolean;
  /** Command this order corrects: the correction goes to review, chained to it. */
  correctionOf: string | null;
  onCancelCorrection: () => void;
  onCommand: (commandId: string) => void;
  onSimulation: (simulation: Simulation | null) => void;
}

/** The operator types a signal; whether it is valid MTP is the server's call, never the screen's. */
export function OrderForm({
  missionId,
  draft,
  onDraftChange,
  canSubmit,
  correctionOf,
  onCancelCorrection,
  onCommand,
  onSimulation,
}: OrderFormProps) {
  const submit = useSubmitOrder(missionId);
  const simulate = useSimulateOrder(missionId);
  const [chosenMode, setMode] = useState<OrderMode>("review");
  const mode: OrderMode = correctionOf ? "review" : chosenMode;
  const inputId = useId();
  const text = draft.trim();

  const send = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (text === "") return;
    submit.mutate(
      { text, mode, parent_id: correctionOf },
      {
        onSuccess: (outcome) => {
          if (!outcome.accepted) return;
          onDraftChange("");
          onSimulation(null);
          if (correctionOf) onCancelCorrection();
          if (outcome.command_id) onCommand(outcome.command_id);
        },
      },
    );
  };

  const outcome = submit.data;
  const failure = submit.error ?? simulate.error;

  return (
    <form className="card order-form" onSubmit={send} aria-label="Ordre">
      <label htmlFor={inputId} className="lbl">
        Ordre (signal)
      </label>
      <div className="row">
        <input
          id={inputId}
          className="grow mono"
          value={draft}
          onChange={(e) => {
            onDraftChange(e.target.value);
            if (submit.data) submit.reset();
          }}
          placeholder="ex. TURN 060"
          autoComplete="off"
          spellCheck={false}
          disabled={!canSubmit}
        />
        <button
          type="button"
          className="btn"
          disabled={!canSubmit || text === "" || simulate.isPending}
          onClick={() => simulate.mutate(text, { onSuccess: onSimulation })}
        >
          Simuler
        </button>
        <button type="submit" className="btn green" disabled={!canSubmit || text === "" || submit.isPending}>
          {mode === "review" ? "Soumettre" : "Émettre"}
        </button>
      </div>
      {correctionOf && (
        <p className="row correction">
          <span className="grow">Correction d'un ordre précédent : elle sera soumise à validation.</span>
          <button type="button" className="btn ghost sm" onClick={onCancelCorrection}>
            Annuler la correction
          </button>
        </p>
      )}
      <fieldset className="row mode" disabled={!canSubmit || correctionOf !== null}>
        <legend className="visually-hidden">Mode d'envoi</legend>
        <label className="check">
          <input type="radio" name="mode" checked={mode === "review"} onChange={() => setMode("review")} />
          Soumettre à validation
        </label>
        <label className="check">
          <input type="radio" name="mode" checked={mode === "direct"} onChange={() => setMode("direct")} />
          Émission directe
        </label>
      </fieldset>
      {!canSubmit && <p className="mut">Votre rôle ne permet pas d'émettre d'ordre.</p>}
      {outcome && !outcome.accepted && (
        <div role="alert" className="refusal">
          <b>Refusé :</b> {outcome.refusal_reason}
          {outcome.hint && <p className="mut">{outcome.hint}</p>}
        </div>
      )}
      {outcome?.accepted && (
        <p role="status" className="accepted">
          {outcome.command_state === "awaiting_review" ? "En attente de validation : " : "Transmis : "}
          <span className="mono">{outcome.text_en}</span>
          {outcome.text_fr && <span className="fr"> · {outcome.text_fr}</span>}
        </p>
      )}
      {outcome && <ReadingDetails outcome={outcome} />}
      {failure && <ErrorPanel message={describeError(failure).message} />}
    </form>
  );
}
