import { memo } from "react";
import { clock } from "../../components/format";
import type { AuthorizationRequest } from "../../socle/ports";

interface RequestListProps {
  requests: AuthorizationRequest[];
  canDecide: boolean;
  onReply: (ship: string, approve: boolean) => void;
}

/** Captains asking the guide for permission (e.g. to investigate a contact). */
export const RequestList = memo(function RequestList({ requests, canDecide, onReply }: RequestListProps) {
  if (requests.length === 0) return null;
  return (
    <section className="card accent" aria-labelledby="requests-title">
      <h2 id="requests-title" className="lbl amber">
        Demandes des commandants
      </h2>
      <ul className="requests">
        {requests.map((r) => (
          <li key={r.ship}>
            <small className="mono mut">
              {clock(r.requested_at_s)} · {r.ship.toUpperCase()}
            </small>
            <p>{r.text_fr}</p>
            {canDecide ? (
              <div className="row">
                <button type="button" className="btn sm green" onClick={() => onReply(r.ship, true)}>
                  Autoriser
                </button>
                <button type="button" className="btn sm" onClick={() => onReply(r.ship, false)}>
                  Refuser
                </button>
              </div>
            ) : (
              <p className="mut">En attente d'un superviseur.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
});
