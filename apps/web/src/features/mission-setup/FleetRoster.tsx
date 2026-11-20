import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";

interface FleetRosterProps {
  /** Guide first. */
  ships: string[];
  guide: string;
  selected: string;
  onSelect: (ship: string) => void;
}

/** Playable ships; the chosen row is the ship the operator will hold. */
export function FleetRoster({ ships, guide, selected, onSelect }: FleetRosterProps) {
  return (
    <Panel id="planner-fleet" title="Flotte disponible" icon="ship" className="planner-fleet">
      <p className="lbl">Choisissez votre navire</p>
      <div className="fleet-roster">
        {ships.map((ship) => {
          const isSelected = ship === selected;
          return (
            <label key={ship} className={isSelected ? "fleet-roster-row on" : "fleet-roster-row"}>
              <input
                type="radio"
                className="card-radio"
                name="ship"
                value={ship}
                checked={isSelected}
                onChange={() => onSelect(ship)}
              />
              <Icon name="ship" size={20} />
              <b className="fleet-roster-name">{ship.toUpperCase()}</b>
              <span className="fleet-roster-state">
                <span className="dot ok" aria-hidden="true" /> Prêt
              </span>
              <span className="fleet-roster-role mut">{ship === guide ? "Navire guide" : "Escorte"}</span>
              {isSelected && <span className="badge me">Vous</span>}
            </label>
          );
        })}
      </div>
    </Panel>
  );
}
