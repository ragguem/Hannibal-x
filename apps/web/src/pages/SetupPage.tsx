import { useState } from "react";
import { useNavigate } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { FormationPreview } from "../features/mission-setup/FormationPreview";
import { ScenarioList } from "../features/mission-setup/ScenarioList";
import { ShipPicker } from "../features/mission-setup/ShipPicker";
import { StartBar } from "../features/mission-setup/StartBar";
import { useScenarios, useStartMission } from "../features/mission-setup/use-mission-setup";
import { describeError } from "../services/api-error";

export function SetupPage() {
  const scenarios = useScenarios();
  const start = useStartMission();
  const navigate = useNavigate();
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [chosenShip, setChosenShip] = useState<string | null>(null);
  const [options, setOptions] = useState({ autopilot: false, manualHelm: false });

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

  return (
    <main className="page setup">
      <h1 className="visually-hidden">Préparation de la mission</h1>
      <ScenarioList scenarios={scenarios.data} selectedId={scenario?.id} onSelect={setScenarioId} />
      {scenario && ship && (
        <div className="stack">
          <section className="card" aria-labelledby="briefing-title">
            <h2 id="briefing-title" className="lbl amber">
              Briefing
            </h2>
            <h3>{scenario.title}</h3>
            <p>{scenario.briefing ?? scenario.summary ?? "Pas de briefing pour ce scénario."}</p>
          </section>
          <ShipPicker
            ships={scenario.playable_ships}
            guide={scenario.guide_ship}
            selected={ship}
            onSelect={setChosenShip}
          />
          <FormationPreview guide={scenario.guide_ship} ships={scenario.playable_ships} player={ship} />
          <StartBar
            options={options}
            onOptionsChange={setOptions}
            canStart={!start.isSuccess}
            pending={start.isPending || start.isSuccess}
            error={start.error}
            onStart={launch}
          />
        </div>
      )}
    </main>
  );
}
