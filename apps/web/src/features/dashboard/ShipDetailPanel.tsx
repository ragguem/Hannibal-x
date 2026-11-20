import { Icon, type IconName } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { ShipIllustration } from "../../components/ShipIllustration";
import { SHIP_STATUS_LABEL } from "./dashboard-labels";
import type { FleetShip, ShipDetail } from "./dashboard-sample";

function SpeedSparkline({ values }: { values: number[] }) {
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const points = values.map((v, i) => `${String((i / (values.length - 1)) * 200)},${String(46 - ((v - min) / span) * 40)}`);
  return (
    <svg className="sparkline" viewBox="0 0 200 50" preserveAspectRatio="none" role="img" aria-label="Vitesse sur la dernière heure">
      <polygon className="sparkline-area" points={`0,50 ${points.join(" ")} 200,50`} />
      <polyline points={points.join(" ")} />
    </svg>
  );
}

interface ShipDetailPanelProps {
  ship: FleetShip;
  detail: ShipDetail;
}

export function ShipDetailPanel({ ship, detail }: ShipDetailPanelProps) {
  const sameShip = detail.name === ship.name;
  const rows: [IconName, string, string][] = [
    ["list", "Identifiant", sameShip ? detail.identifier : "—"],
    ["target", "Mission", sameShip ? detail.mission : "—"],
    ["pin", "Position", sameShip ? detail.position : "—"],
    ["gauge", "Vitesse", ship.speedKn === null ? "—" : `${ship.speedKn.toFixed(1)} nd`],
    ["arrow", "Cap", `${String(ship.headingDeg).padStart(3, "0")}°`],
    ["shield", "État", sameShip ? detail.state : SHIP_STATUS_LABEL[ship.status]],
    ["clock", "Dernière liaison", sameShip ? detail.lastContact : "—"],
    ["user", "Responsable", sameShip ? detail.responsible : "—"],
  ];

  return (
    <Panel id="dash-ship" title="Détails du navire" icon="ship" className="dash-ship">
      <div className="ship-hero">
        <ShipIllustration />
        <div className="ship-hero-caption">
          <h3>{ship.name}</h3>
          <span className={`status-pill ${ship.status}`}>{SHIP_STATUS_LABEL[ship.status]}</span>
        </div>
      </div>
      <dl className="ship-facts">
        {rows.map(([icon, label, value]) => (
          <div key={label}>
            <dt>
              <Icon name={icon} size={15} /> {label}
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {sameShip && (
        <>
          <p className="lbl">Vitesse récente · 1 h</p>
          <SpeedSparkline values={detail.speedHistory} />
        </>
      )}
    </Panel>
  );
}
