import { Panel } from "../../components/Panel";
import type { EventKind, LoggedEvent } from "./dashboard-sample";

const KIND_LABEL: Record<EventKind, string> = { ok: "Succès", info: "Information", warning: "Avertissement" };

export function EventLogPanel({ events, seeAllTo }: { events: LoggedEvent[]; seeAllTo?: string }) {
  return (
    <Panel id="dash-events" title="Journal des événements" icon="list" seeAllTo={seeAllTo} className="dash-events-panel">
      <div className="table-scroll">
        <table className="table dash-events">
          <thead>
            <tr>
              <th scope="col">Heure</th>
              <th scope="col">Type</th>
              <th scope="col">Événement</th>
              <th scope="col">Auteur</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={`${event.time}-${event.label}`}>
                <td className="mono">{event.time}</td>
                <td>
                  <span className={`event-dot ${event.kind}`} role="img" aria-label={KIND_LABEL[event.kind]} />
                </td>
                <td>{event.label}</td>
                <td className="mut">{event.author}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
