import { memo } from "react";
import { clock } from "../../components/format";
import type { Mission } from "../../socle/ports";

interface GuideOrdersProps {
  pending: Mission["pending_orders"];
  planned: Mission["planned_orders"];
  elapsed: number;
}

/** What the guide has ordered and not yet executed, then what the scenario plans next. */
export const GuideOrders = memo(function GuideOrders({ pending, planned, elapsed }: GuideOrdersProps) {
  const upcoming = planned.filter((o) => o.planned_at_s >= elapsed).slice(0, 3);
  if (pending.length === 0 && upcoming.length === 0) return null;
  return (
    <section className="card accent" aria-labelledby="guide-orders-title">
      <h2 id="guide-orders-title" className="lbl amber">
        Ordres du guide
      </h2>
      {pending.length > 0 && (
        <ul className="plain">
          {pending.map((text) => (
            <li key={text} className="mono" lang="en">
              {text} <span className="badge guide">à exécuter</span>
            </li>
          ))}
        </ul>
      )}
      {upcoming.length > 0 && (
        <ul className="plain">
          {upcoming.map((o) => (
            <li key={`${o.planned_at_s}-${o.text_en}`}>
              <small className="mono mut">{clock(o.planned_at_s)}</small> <span className="fr">{o.text_fr}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
});
