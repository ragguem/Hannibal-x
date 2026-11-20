import { Icon } from "../../components/Icon";
import { PLANNER_STEPS, type PlannerStepId } from "./planner-config";

interface PlannerHeaderProps {
  activeStep: PlannerStepId;
  onStepSelect: (step: PlannerStepId) => void;
}

/** In-page jump without a history entry: Back leaves the planner instead of replaying the steps. */
function revealPanel(headingId: string) {
  const heading = document.getElementById(headingId);
  heading?.scrollIntoView({ behavior: "smooth", block: "start" });
  heading?.focus({ preventScroll: true });
}

export function PlannerHeader({ activeStep, onStepSelect }: PlannerHeaderProps) {
  return (
    <header className="card planner-header">
      <div className="planner-title">
        <span className="planner-emblem" aria-hidden="true">
          <Icon name="crosshair" size={30} />
        </span>
        <div>
          <h1>Mission Planner</h1>
          <p className="mut">Préparez et configurez votre mission</p>
        </div>
      </div>
      <nav className="planner-steps-nav" aria-label="Étapes de préparation">
        <ol className="planner-steps">
          {PLANNER_STEPS.map((step, index) => (
            <li key={step.id} className={step.id === activeStep ? "planner-step active" : "planner-step"}>
              <a
                href={`#${step.anchor}`}
                aria-current={step.id === activeStep ? "step" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  onStepSelect(step.id);
                  revealPanel(step.anchor);
                }}
              >
                <span className="planner-step-index">{index + 1}</span>
                <span className="planner-step-text">
                  <b>{step.title}</b>
                  <small>{step.subtitle}</small>
                </span>
              </a>
              {index < PLANNER_STEPS.length - 1 && (
                <span className="planner-step-separator" aria-hidden="true">
                  <Icon name="chevron" size={18} />
                </span>
              )}
            </li>
          ))}
        </ol>
      </nav>
    </header>
  );
}
