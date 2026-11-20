import { minutes } from "../../components/format";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { ShipIllustration } from "../../components/ShipIllustration";
import type { ScenarioSummary } from "../../socle/ports";

interface MissionBriefingProps {
  scenario: ScenarioSummary;
  player: string;
}

export function MissionBriefing({ scenario, player }: MissionBriefingProps) {
  const instructions = [
    `Tenir le poste de ${player.toUpperCase()}`,
    `Suivre les ordres du guide ${scenario.guide_ship.toUpperCase()}`,
    `Durée prévue : ${minutes(scenario.duration_s)}`,
  ];
  return (
    <Panel id="planner-briefing" title="Briefing de mission" icon="book" collapsible className="planner-briefing">
      <div className="briefing-body">
        <span className="briefing-thumb" aria-hidden="true">
          <ShipIllustration />
        </span>
        <div className="briefing-text">
          <h3>{scenario.title}</h3>
          <p>{scenario.briefing ?? scenario.summary ?? "Pas de briefing pour ce scénario."}</p>
          <ul className="briefing-checklist">
            {instructions.map((instruction) => (
              <li key={instruction}>
                <Icon name="check" size={16} /> {instruction}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
