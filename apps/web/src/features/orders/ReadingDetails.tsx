import type { OrderOutcome } from "../../socle/ports";

/** How the server read the order: MTP signal and its reference, simulator effect, what it assumed. */
export function ReadingDetails({ outcome }: { outcome: OrderOutcome }) {
  const notes = outcome.notes ?? [];
  if (!outcome.signal && !outcome.effect && notes.length === 0) return null;
  return (
    <div className="reading mut">
      {outcome.signal && (
        <p>
          Signal <span className="mono">{outcome.signal}</span>
          {outcome.reference && <> · {outcome.reference}</>}
        </p>
      )}
      {outcome.effect && <p>{outcome.effect}</p>}
      {notes.length > 0 && (
        <ul aria-label="À vérifier">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
