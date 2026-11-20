import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import type { MissionStatus, MissionSummary } from "./dashboard-sample";

const STATUS_LABEL: Record<MissionStatus, string> = { active: "Active", planned: "Planifiée", done: "Terminée" };

export function MissionsPanel({ missions }: { missions: MissionSummary[] }) {
  return (
    <Panel id="dash-missions" title="Missions" icon="target">
      <ul className="dash-missions">
        {missions.map((mission) => (
          <li key={mission.id} className={`dash-mission ${mission.status}`}>
            <span className="dash-mission-thumb" aria-hidden="true">
              <Icon name="ship" size={34} />
            </span>
            <span className="dash-mission-body">
              <span className="row">
                <b className="grow">{mission.name}</b>
                <span className={`status-pill ${mission.status}`}>{STATUS_LABEL[mission.status]}</span>
              </span>
              <span className="mut small">{mission.description}</span>
              <span className="row mut small">
                <span>{mission.ships} navires</span>
                <span>{mission.period}</span>
              </span>
              <span className="row small">
                <span className="meter grow" aria-hidden="true">
                  <span style={{ width: `${String(mission.progress)}%` }} />
                </span>
                <span>{mission.progress} %</span>
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
