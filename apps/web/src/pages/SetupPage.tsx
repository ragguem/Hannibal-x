import { useState } from "react";
import { useNavigate } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { ExecutionSettings } from "../features/mission-setup/ExecutionSettings";
import { FleetRoster } from "../features/mission-setup/FleetRoster";
import { FormationMap } from "../features/mission-setup/FormationMap";
import { FormationSettings } from "../features/mission-setup/FormationSettings";
import { LaunchPanel } from "../features/mission-setup/LaunchPanel";
import { MissionBriefing } from "../features/mission-setup/MissionBriefing";
import { PlannerHeader } from "../features/mission-setup/PlannerHeader";
import {
  DEFAULT_EXECUTION_OPTIONS,
  DEFAULT_FORMATION_PLAN,
  fleetOrder,
  type PlannerStepId,
} from "../features/mission-setup/planner-config";
import { ScenarioList } from "../features/mission-setup/ScenarioList";
import { useScenarios, useStartMission } from "../features/mission-setup/use-mission-setup";
import { describeError } from "../services/api-error";

export function SetupPage() {
  const scenarios = useScenarios();
  const start = useStartMission();
  const navigate = useNavigate();
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [chosenShip, setChosenShip] = useState<string | null>(null);
  const [options, setOptions] = useState(DEFAULT_EXECUTION_OPTIONS);
  const [formationPlan, setFormationPlan] = useState(DEFAULT_FORMATION_PLAN);
  const [activeStep, setActiveStep] = useState<PlannerStepId>("scenario");

  if (scenarios.isPending) return <Loading label="Chargement des scénarios…" />;
  if (scenarios.isError) {
    return <ErrorPanel message={describeError(scenarios.error).message} onRetry={() => void scenarios.refetch()} />;
  }

  const scenario = scenarios.data.find((s) => s.id === scenarioId) ?? scenarios.data[0];
  const ship = chosenShip && scenario?.playable_ships.includes(chosenShip) ? chosenShip : scenario?.playable_ships[0];

  const launch = () => {
    if (!scenario || !ship) return;
    start.mutate(
      { scenario_id: scenario.id, player_ship: ship, autopilot: options.autopilot, manual_helm: options.manualHelm },
      { onSuccess: (mission) => void navigate(`/missions/${encodeURIComponent(mission.id)}`) },
    );
  };

  if (!scenario || !ship) {
    return (
      <main className="page planner">
        <PlannerHeader activeStep={activeStep} onStepSelect={setActiveStep} />
        <p className="card mut">Aucun scénario jouable n'est disponible.</p>
      </main>
    );
  }

  const order = fleetOrder(scenario.guide_ship, scenario.playable_ships);

  return (
    <main className="page planner">
      <PlannerHeader activeStep={activeStep} onStepSelect={setActiveStep} />
      <div className="planner-main">
        <div className="planner-side">
          <div onFocus={() => setActiveStep("scenario")}>
            <ScenarioList scenarios={scenarios.data} selectedId={scenario.id} onSelect={setScenarioId} />
          </div>
          <div onFocus={() => setActiveStep("fleet")}>
            <FleetRoster ships={order} guide={scenario.guide_ship} selected={ship} onSelect={setChosenShip} />
          </div>
        </div>
        <FormationMap order={order} guide={scenario.guide_ship} player={ship} plan={formationPlan} />
        <div className="planner-settings" onFocus={() => setActiveStep("formation")}>
          <FormationSettings guide={scenario.guide_ship} plan={formationPlan} onPlanChange={setFormationPlan} />
        </div>
      </div>
      <div className="planner-footer" onFocus={() => setActiveStep("execution")}>
        <ExecutionSettings
          options={options}
          onOptionsChange={setOptions}
          durationS={scenario.duration_s}
          shipCount={order.length}
        />
        <MissionBriefing scenario={scenario} player={ship} />
        <LaunchPanel canStart={!start.isSuccess} pending={start.isPending || start.isSuccess} error={start.error} onStart={launch} />
      </div>
    </main>
  );
}
