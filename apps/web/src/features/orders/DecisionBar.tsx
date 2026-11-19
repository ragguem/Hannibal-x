import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import type { CommandState } from "../../socle/ports";
import { useCommand, useDecideCommand } from "./use-orders";

const STATE_LABEL: Record<CommandState, string> = {
  awaiting_review: "en attente de validation",
  rejected: "rejeté",
  dispatching: "transmission en cours…",
  dispatched: "transmis",
  dispatch_failed: "échec de transmission",
};

interface DecisionBarProps {
  commandId: string;
  canDecide: boolean;
  onDismiss: () => void;
}

export function DecisionBar({ commandId, canDecide, onDismiss }: DecisionBarProps) {
  const command = useCommand(commandId);
  const decide = useDecideCommand();
  const c = command.data;
  if (!c) return command.isError ? <ErrorPanel message={describeError(command.error).message} /> : null;

  const final = c.state === "dispatched" || c.state === "rejected";
  const act = (decision: "approve" | "reject" | "retry") => decide.mutate({ commandId, decision });

  return (
    <section className={`card decision ${c.state}`} aria-labelledby="decision-title">
      <h2 id="decision-title" className="lbl">
        Ordre {STATE_LABEL[c.state]}
      </h2>
      <p className="mono" lang="en">
        {c.text_en || c.text}
      </p>
      {c.text_fr && <p className="fr">{c.text_fr}</p>}
      <small className="mut">
        Soumis par {c.submitted_by}
        {c.decided_by ? ` · décidé par ${c.decided_by}` : ""}
      </small>
      {c.state === "dispatch_failed" && c.last_error && <p role="alert">{c.last_error}</p>}
      {decide.error && <ErrorPanel message={describeError(decide.error).message} />}
      <div className="row">
        {canDecide && c.state === "awaiting_review" && (
          <>
            <button type="button" className="btn green" disabled={decide.isPending} onClick={() => act("approve")}>
              Valider
            </button>
            <button type="button" className="btn" disabled={decide.isPending} onClick={() => act("reject")}>
              Rejeter
            </button>
          </>
        )}
        {canDecide && c.state === "dispatch_failed" && (
          <button type="button" className="btn amber" disabled={decide.isPending} onClick={() => act("retry")}>
            Réessayer
          </button>
        )}
        {!canDecide && c.state === "awaiting_review" && <span className="mut">Un superviseur doit valider.</span>}
        {final && (
          <button type="button" className="btn ghost sm" onClick={onDismiss}>
            Fermer
          </button>
        )}
      </div>
    </section>
  );
}
