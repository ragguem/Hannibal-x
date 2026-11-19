import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import { CitationList } from "./CitationList";
import { useExplainCommand } from "./use-doctrine";

/** « Expliquer » under a command: the model rephrases, the decoded values stay authoritative. */
export function OrderExplanation({ commandId }: { commandId: string }) {
  const explain = useExplainCommand(commandId);
  const e = explain.data;
  return (
    <section className="card explanation" aria-label="Explication de l'ordre">
      {!e && (
        <button type="button" className="btn sm ghost" disabled={explain.isPending} onClick={() => explain.mutate()}>
          {explain.isPending ? "Explication…" : "Expliquer l'ordre"}
        </button>
      )}
      {explain.error && <ErrorPanel message={describeError(explain.error).message} />}
      {e && (
        <>
          <p className="fr">{e.explanation_fr}</p>
          <p className="mut" lang="en">
            {e.explanation_en}
          </p>
          {e.source === "deterministic" && (
            <small className="mut">Interprétation déterministe : le texte du modèle n'a pas passé les contrôles.</small>
          )}
          <CitationList citations={e.citations} />
        </>
      )}
    </section>
  );
}
