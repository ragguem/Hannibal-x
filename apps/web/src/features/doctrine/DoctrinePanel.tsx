import { useId, useState, type SyntheticEvent } from "react";
import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import type { AnswerLanguage } from "../../socle/ports";
import { DoctrineAnswerView } from "./DoctrineAnswerView";
import { replaceTerm, useAskDoctrine, usePublications } from "./use-doctrine";

/** Question, optional publication, answer with its citations. Used full-page and in the console. */
export function DoctrinePanel({ title = "Doctrine" }: { title?: string }) {
  const ask = useAskDoctrine();
  const publications = usePublications();
  const [question, setQuestion] = useState("");
  const [publication, setPublication] = useState("");
  const [language, setLanguage] = useState<AnswerLanguage>("fr");
  const ids = { title: useId(), question: useId(), publication: useId(), language: useId() };

  const send = (text: string) => {
    if (text.trim().length < 2) return;
    ask.mutate({ question: text.trim(), language, publication: publication === "" ? null : publication });
  };
  const onSubmit = (e: SyntheticEvent) => {
    e.preventDefault();
    send(question);
  };
  const onUseProposal = (unknown: string, term: string) => {
    const corrected = replaceTerm(question, unknown, term);
    setQuestion(corrected);
    send(corrected);
  };

  return (
    <section className="card doctrine" aria-labelledby={ids.title}>
      <h2 id={ids.title} className="lbl">
        {title}
      </h2>
      <form onSubmit={onSubmit} className="stack">
        <label htmlFor={ids.question}>Question</label>
        <textarea
          id={ids.question}
          rows={3}
          maxLength={1000}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ex. : quelle est la vitesse tactique standard ?"
        />
        <div className="row">
          <label htmlFor={ids.publication}>Publication</label>
          <select id={ids.publication} value={publication} onChange={(e) => setPublication(e.target.value)}>
            <option value="">Toutes</option>
            {(publications.data ?? []).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <label htmlFor={ids.language}>Langue</label>
          <select id={ids.language} value={language} onChange={(e) => setLanguage(e.target.value as AnswerLanguage)}>
            <option value="fr">Français</option>
            <option value="en">English</option>
          </select>
          <span className="grow" />
          <button type="submit" className="btn" disabled={ask.isPending || question.trim().length < 2}>
            {ask.isPending ? "Recherche…" : "Demander"}
          </button>
        </div>
      </form>
      {ask.error && <ErrorPanel message={describeError(ask.error).message} />}
      {ask.data && <DoctrineAnswerView answer={ask.data} onUseProposal={onUseProposal} />}
    </section>
  );
}
