import { clock } from "../../components/format";
import type { ScenarioSummary } from "../../socle/ports";

interface ScenarioListProps {
  scenarios: ScenarioSummary[];
  selectedId: string | undefined;
  onSelect: (scenarioId: string) => void;
}

export function ScenarioList({ scenarios, selectedId, onSelect }: ScenarioListProps) {
  return (
    <fieldset className="card choice-list">
      <legend className="lbl">Scénario</legend>
      {scenarios.map((s) => (
        <label key={s.id} className={s.id === selectedId ? "choice on" : "choice"}>
          <input type="radio" name="scenario" value={s.id} checked={s.id === selectedId} onChange={() => onSelect(s.id)} />
          <span className="choice-body">
            <b>{s.title}</b>
            <small className="mut">
              {s.level ?? "niveau libre"} · {clock(s.duration_s)}
            </small>
            {s.summary && <span>{s.summary}</span>}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
