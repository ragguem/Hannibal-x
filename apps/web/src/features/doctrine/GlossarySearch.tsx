import { useDeferredValue, useId, useState } from "react";
import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";
import { GLOSSARY_MIN_CHARS, useGlossary } from "./use-doctrine";

export function GlossarySearch() {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query);
  const glossary = useGlossary(deferred);
  const ids = { title: useId(), input: useId() };
  const entries = glossary.data?.entries ?? [];

  return (
    <section className="card glossary" aria-labelledby={ids.title}>
      <h2 id={ids.title} className="lbl">
        Glossaire
      </h2>
      <label htmlFor={ids.input}>Terme, traduction ou sigle</label>
      <input id={ids.input} type="search" value={query} maxLength={100} onChange={(e) => setQuery(e.target.value)} />
      {glossary.error && <ErrorPanel message={describeError(glossary.error).message} />}
      {deferred.trim().length >= GLOSSARY_MIN_CHARS && glossary.isSuccess && entries.length === 0 && (
        <p className="mut">Aucune entrée.</p>
      )}
      <dl>
        {entries.map((e) => (
          <div key={`${e.source}-${e.en}-${e.sense ?? 0}`}>
            <dt>
              <span lang="en">{e.en}</span>
              {e.abbreviation && <span className="mono"> ({e.abbreviation})</span>}
              {e.fr && <> — {e.fr}</>}
            </dt>
            <dd>
              {e.definition_fr ?? e.definition_en}
              <small className="mut">
                {" "}
                {e.source}
                {e.page ? `, p. ${e.page}` : ""}
              </small>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
