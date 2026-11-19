import { memo } from "react";
import { clock } from "../../components/format";
import type { Objective } from "../../socle/ports";

export const ObjectiveList = memo(function ObjectiveList({ objectives }: { objectives: Objective[] }) {
  return (
    <section className="card" aria-labelledby="objectives-title">
      <h2 id="objectives-title" className="lbl">
        Objectifs
      </h2>
      {objectives.length === 0 ? (
        <p className="mut">Aucun objectif.</p>
      ) : (
        <ul className="objectives">
          {objectives.map((o) => (
            <li key={o.description} className={o.achieved ? "done" : undefined}>
              <span aria-hidden="true">{o.achieved ? "✓" : "○"}</span> {o.description}
              <span className="visually-hidden">{o.achieved ? " (atteint)" : " (en cours)"}</span>
              {o.achieved && o.achieved_at_s !== null && o.achieved_at_s !== undefined ? (
                <small className="mut"> · atteint à {clock(o.achieved_at_s)}</small>
              ) : o.deadline_s !== null && o.deadline_s !== undefined ? (
                <small className="mut"> · avant {clock(o.deadline_s)}</small>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
});
