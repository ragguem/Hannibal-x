import { useId } from "react";
import { deg3 } from "../../components/format";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { normalizeHeading, SPACING_LIMITS_KM, type FormationPlan } from "./planner-config";

interface FormationSettingsProps {
  guide: string;
  plan: FormationPlan;
  onPlanChange: (plan: FormationPlan) => void;
}

const HEADING_STEP_DEG = 1;

function Compass({ headingDeg }: { headingDeg: number }) {
  return (
    <svg className="compass" viewBox="-50 -50 100 100" aria-hidden="true">
      <circle className="compass-dial" r="46" />
      {Array.from({ length: 36 }, (_, i) => (
        <line key={i} className={i % 9 === 0 ? "compass-tick major" : "compass-tick"} y1="-46" y2={i % 9 === 0 ? -38 : -42} transform={`rotate(${String(i * 10)})`} />
      ))}
      <text className="compass-cardinal" y="-26" textAnchor="middle">
        N
      </text>
      <g transform={`rotate(${String(headingDeg)})`}>
        <path className="compass-needle" d="M0 -34 L7 0 L0 6 L-7 0 Z" />
        <path className="compass-needle-tail" d="M0 34 L7 0 L-7 0 Z" />
      </g>
      <circle className="compass-hub" r="4" />
    </svg>
  );
}

function TrackPreview() {
  return (
    <svg className="track-preview" viewBox="0 0 240 60" preserveAspectRatio="none" aria-hidden="true">
      <path className="track-preview-line" d="M6 52 C60 50 90 40 130 30 C170 20 200 14 234 8" />
      {[
        [60, 48],
        [130, 30],
        [200, 14],
      ].map(([x, y]) => (
        <path key={x} className="track-preview-ship" d="M-9 0 L7 0 L10 -3 L-6 -3 Z" transform={`translate(${String(x)} ${String(y)})`} />
      ))}
    </svg>
  );
}

export function FormationSettings({ guide, plan, onPlanChange }: FormationSettingsProps) {
  const uid = useId();
  const typeId = `${uid}-type`;
  const spacingId = `${uid}-spacing`;
  const headingId = `${uid}-heading`;
  const guideLabelId = `${uid}-guide`;

  const setHeading = (deg: number) => onPlanChange({ ...plan, headingDeg: normalizeHeading(deg) });

  return (
    <Panel id="planner-formation" title="Formation" icon="formation" className="planner-formation">
      <div className="planner-field">
        <label htmlFor={typeId}>Type de formation</label>
        <select id={typeId} defaultValue="column">
          <option value="column">Colonne</option>
          <option value="line-abreast" disabled>
            Ligne de front (prochaine version)
          </option>
          <option value="screen" disabled>
            Écran (prochaine version)
          </option>
        </select>
      </div>

      <div className="planner-field">
        <span id={guideLabelId} className="planner-field-label">
          Navire guide
        </span>
        <span className="field-static" aria-labelledby={guideLabelId} role="group">
          <Icon name="ship" size={18} />
          <b>{guide.toUpperCase()}</b>
          <span className="grow" />
          <span className="dot ok" aria-hidden="true" />
        </span>
      </div>

      <div className="planner-field">
        <label htmlFor={spacingId}>Espacement</label>
        <span className="range-row">
          <input
            id={spacingId}
            type="range"
            min={SPACING_LIMITS_KM.min}
            max={SPACING_LIMITS_KM.max}
            step={SPACING_LIMITS_KM.step}
            value={plan.spacingKm}
            onChange={(event) => onPlanChange({ ...plan, spacingKm: Number(event.target.value) })}
          />
          <output htmlFor={spacingId} className="value-box">
            {plan.spacingKm} km
          </output>
        </span>
      </div>

      <div className="planner-field">
        <label htmlFor={headingId}>Orientation</label>
        <span className="heading-row">
          <Compass headingDeg={plan.headingDeg} />
          <span className="heading-input">
            <input
              id={headingId}
              type="number"
              inputMode="numeric"
              min={0}
              max={359}
              value={plan.headingDeg}
              onChange={(event) => setHeading(Number(event.target.value))}
            />
            <span className="heading-unit" aria-hidden="true">
              °
            </span>
          </span>
          <span className="heading-steppers">
            <button type="button" className="btn sm ghost icon-btn step-up" aria-label="Augmenter l'orientation" onClick={() => setHeading(plan.headingDeg + HEADING_STEP_DEG)}>
              <Icon name="chevron" size={14} />
            </button>
            <button type="button" className="btn sm ghost icon-btn" aria-label="Diminuer l'orientation" onClick={() => setHeading(plan.headingDeg - HEADING_STEP_DEG)}>
              <Icon name="chevron" size={14} />
            </button>
          </span>
        </span>
        <small className="mut">Cap {deg3(plan.headingDeg)}° · aperçu seulement, le simulateur applique la géométrie du scénario.</small>
      </div>

      <div className="planner-field">
        <span className="planner-field-label">Aperçu de la trajectoire</span>
        <TrackPreview />
      </div>
    </Panel>
  );
}
