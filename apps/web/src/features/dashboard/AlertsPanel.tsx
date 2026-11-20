import { Panel } from "../../components/Panel";
import type { AlertLevel, RaisedAlert } from "./dashboard-sample";

const LEVEL_LABEL: Record<AlertLevel, string> = { critical: "Critique", warning: "Avertissement", info: "Information" };

export function AlertsPanel({ alerts }: { alerts: RaisedAlert[] }) {
  return (
    <Panel id="dash-alerts" title="Alertes récentes" icon="alert" className="dash-alerts">
      <ul className="alert-list">
        {alerts.map((alert) => (
          <li key={`${alert.time}-${alert.title}`} className={`alert-item ${alert.level}`}>
            <span className={`alert-dot ${alert.level}`} role="img" aria-label={LEVEL_LABEL[alert.level]} />
            <span className="mono small mut">{alert.time}</span>
            <span className="grow">
              <b className="alert-title">{alert.title}</b>
              <span className="block small mut">{alert.detail}</span>
            </span>
            <button type="button" className={`btn sm ${alert.level === "critical" ? "danger" : ""}`} disabled title="Arrive avec la fonctionnalité Alertes">
              {alert.action}
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
