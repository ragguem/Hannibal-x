import type { DoctrineAnswer } from "../../socle/ports";
import { CitationList } from "./CitationList";

const REFUSAL_LABEL: Record<NonNullable<DoctrineAnswer["refusal_reason"]>, string> = {
  no_evidence: "aucun passage ne répond à la question",
  ungrounded_claim: "la réponse contenait des éléments absents des extraits",
  unsupported_answer: "la réponse n'était pas appuyée par les extraits cités",
};

interface DoctrineAnswerViewProps {
  answer: DoctrineAnswer;
  /** The user picked a proposal for an unknown term: ask again with it. */
  onUseProposal: (unknown: string, term: string) => void;
}

export function DoctrineAnswerView({ answer, onUseProposal }: DoctrineAnswerViewProps) {
  const refused = answer.status === "refused";
  const suggestions = answer.suggestions ?? [];
  const unknownTerms = answer.unknown_terms ?? [];
  return (
    <section className={`card doctrine-answer ${answer.status}`} aria-live="polite" aria-label="Réponse de doctrine">
      <p className="answer-text">{answer.answer}</p>
      {refused && answer.refusal_reason && (
        <p className="mut">
          Refus : {REFUSAL_LABEL[answer.refusal_reason]}
          {answer.refusal_detail ? ` (${answer.refusal_detail})` : ""}.
        </p>
      )}
      {suggestions.length > 0 && (
        <div className="suggestions">
          {suggestions.map((s) => (
            <p key={s.unknown}>
              « {s.unknown} » est absent des publications. Vouliez-vous dire{" "}
              {s.proposals.map((p) => (
                <button key={p.term} type="button" className="btn sm ghost" onClick={() => onUseProposal(s.unknown, p.term)}>
                  {p.term}
                  {p.fr ? ` (${p.fr})` : ""}
                </button>
              ))}
              ?
            </p>
          ))}
        </div>
      )}
      {suggestions.length === 0 && unknownTerms.length > 0 && (
        <p className="mut">Termes absents des publications : {unknownTerms.join(", ")}.</p>
      )}
      <CitationList citations={answer.citations} />
      <small className="mut">
        {answer.model} · index {answer.index_version} · {(answer.duration_ms / 1000).toFixed(1)} s
        {answer.second_try ? " · second essai" : ""}
      </small>
    </section>
  );
}
