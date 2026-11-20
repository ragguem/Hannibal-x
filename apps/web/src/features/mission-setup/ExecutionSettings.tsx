import { useId } from "react";
import { minutes } from "../../components/format";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import type { ExecutionOptions } from "./planner-config";

interface SwitchFieldProps {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function SwitchField({ label, hint, checked, onChange }: SwitchFieldProps) {
  const hintId = useId();
  return (
    <label className="switch-field">
      <span className="switch-label">
        {label}
        <span className="info-hint" title={hint}>
          <Icon name="info" size={14} />
        </span>
      </span>
      <span id={hintId} className="visually-hidden">
        {hint}
      </span>
      <input
        type="checkbox"
        role="switch"
        className="switch"
        aria-describedby={hintId}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

interface ExecutionSettingsProps {
  options: ExecutionOptions;
  onOptionsChange: (options: ExecutionOptions) => void;
  durationS: number;
  shipCount: number;
}

/** Rendered once a scenario and a ship are chosen, so the configuration is always complete. */
export function ExecutionSettings({ options, onOptionsChange, durationS, shipCount }: ExecutionSettingsProps) {
  return (
    <Panel id="planner-execution" title="Paramètres d'exécution" icon="gauge" collapsible className="planner-execution">
      <div className="execution-grid">
        <div className="execution-switches">
          <SwitchField
            label="Mode automatique"
            hint="Les ordres du guide sont exécutés sans vous."
            checked={options.autopilot}
            onChange={(autopilot) => onOptionsChange({ ...options, autopilot })}
          />
          <SwitchField
            label="Barre manuelle"
            hint="Vous tenez le cap et la vitesse."
            checked={options.manualHelm}
            onChange={(manualHelm) => onOptionsChange({ ...options, manualHelm })}
          />
        </div>
        <ul className="execution-summary">
          <li>
            <Icon name="clock" size={18} /> Durée estimée : <b>{minutes(durationS)}</b>
          </li>
          <li>
            <Icon name="ship" size={18} /> <b>{shipCount} navires</b> engagés
          </li>
          <li className="ok">
            <Icon name="check" size={18} /> Configuration valide
          </li>
        </ul>
      </div>
    </Panel>
  );
}
