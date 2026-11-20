import { minutes } from "../../components/format";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { ShipIllustration } from "../../components/ShipIllustration";
import type { ScenarioSummary } from "../../socle/ports";
import { levelTone } from "./planner-config";

interface ScenarioListProps {
  scenarios: ScenarioSummary[];
  selectedId: string | undefined;
  onSelect: (scenarioId: string) => void;
}

export function ScenarioList({ scenarios, selectedId, onSelect }: ScenarioListProps) {
  return (
    <Panel id="planner-scenario" title="Scénarios disponibles" icon="star" className="planner-scenarios">
      <div className="scenario-cards">
        {scenarios.map((scenario) => {
          const selected = scenario.id === selectedId;
          return (
            <label key={scenario.id} className={selected ? "scenario-card on" : "scenario-card"}>
              <input
                type="radio"
                className="card-radio"
                name="scenario"
                value={scenario.id}
                checked={selected}
                onChange={() => onSelect(scenario.id)}
              />
              <span className="scenario-thumb" aria-hidden="true">
                <ShipIllustration pennant="" />
              </span>
              <span className="scenario-body">
                <b>{scenario.title}</b>
                <span className="scenario-meta">
                  <span>
                    <Icon name="ship" size={14} /> {scenario.playable_ships.length} navires
                  </span>
                  <span>
                    <Icon name="clock" size={14} /> {minutes(scenario.duration_s)}
                  </span>
                  <span className={`level-badge ${levelTone(scenario.level)}`}>{scenario.level ?? "niveau libre"}</span>
                </span>
                {scenario.summary && <small className="mut">{scenario.summary}</small>}
              </span>
              <span className="radio-mark" aria-hidden="true">
                {selected && <Icon name="check" size={20} />}
              </span>
            </label>
          );
        })}
      </div>
    </Panel>
  );
}
