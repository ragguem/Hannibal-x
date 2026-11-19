import type { Citation } from "../../socle/ports";

function reference(c: Citation): string {
  return [
    c.publication + (c.edition ? ` (éd. ${c.edition})` : ""),
    c.chapter && `chap. ${c.chapter}`,
    c.article && `art. ${c.article}`,
    c.page && `p. ${c.page}`,
  ]
    .filter(Boolean)
    .join(", ");
}

/** The extracts the answer cites, numbered as in the answer, for the operator to check against the publication. */
export function CitationList({ citations = [] }: { citations?: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ol className="citations" aria-label="Extraits cités">
      {citations.map((c) => (
        <li key={`${c.number}-${c.passage_id}`} value={c.number}>
          <strong>{reference(c)}</strong>
          {c.title && <span className="mut"> — {c.title}</span>}
          <blockquote lang="en">{c.text}</blockquote>
          {c.table_row && <p className="mono sm">Ligne du tableau : {c.table_row}</p>}
        </li>
      ))}
    </ol>
  );
}
