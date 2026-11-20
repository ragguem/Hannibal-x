import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { SHIP_STATUS_LABEL } from "./dashboard-labels";
import type { FleetShip } from "./dashboard-sample";

function SignalBars({ level }: { level: number }) {
  return (
    <span className="signal-bars" role="img" aria-label={`Liaison ${String(level)} sur 4`}>
      {[1, 2, 3, 4].map((bar) => (
        <span key={bar} className={bar <= level ? "on" : undefined} />
      ))}
    </span>
  );
}

interface FleetPanelProps {
  ships: FleetShip[];
  selected: string;
  onSelect: (name: string) => void;
}

export function FleetPanel({ ships, selected, onSelect }: FleetPanelProps) {
  return (
    <Panel id="dash-fleet" title="Flotte" icon="ship">
      <ul className="dash-fleet">
        {ships.map((ship) => (
          <li key={ship.name}>
            <button
              type="button"
              className={`dash-fleet-row ${ship.name === selected ? "on" : ""}`}
              aria-pressed={ship.name === selected}
              onClick={() => onSelect(ship.name)}
            >
              <Icon name="ship" size={22} />
              <span className="grow">
                <b>{ship.name}</b>
                <span className={`small status-text ${ship.status}`}>● {SHIP_STATUS_LABEL[ship.status]}</span>
              </span>
              <span className="small">{ship.speedKn === null ? "—" : `${ship.speedKn.toFixed(1)} nd`}</span>
              <SignalBars level={ship.signal} />
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
