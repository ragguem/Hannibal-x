import { useCallback, useState } from "react";
import { useParams } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { ContactList } from "../features/contacts/ContactList";
import { DoctrinePanel } from "../features/doctrine/DoctrinePanel";
import { OrderExplanation } from "../features/doctrine/OrderExplanation";
import { ShipTable } from "../features/fleet/ShipTable";
import { HelmPanel } from "../features/helm/HelmPanel";
import { Debrief } from "../features/mission/Debrief";
import { GuideOrders } from "../features/mission/GuideOrders";
import { MissionBar } from "../features/mission/MissionBar";
import { ObjectiveList } from "../features/mission/ObjectiveList";
import { useMission, useMissionActions, useMissionStream } from "../features/mission/use-mission";
import { DecisionBar } from "../features/orders/DecisionBar";
import { InterpretationCard } from "../features/orders/InterpretationCard";
import { OrderForm } from "../features/orders/OrderForm";
import { SimulationReport } from "../features/orders/SimulationReport";
import { Radar } from "../features/radar/Radar";
import { RadioLog } from "../features/radio/RadioLog";
import { RecommendationList } from "../features/recommendations/RecommendationList";
import { RequestList } from "../features/requests/RequestList";
import { usePermission } from "../features/session/use-session";
import { VoiceCapture } from "../features/voice/VoiceCapture";
import { describeError } from "../services/api-error";
import type { Classification, Simulation, VoiceOrderOutcome } from "../socle/ports";

export function ConsolePage() {
  const { missionId = "" } = useParams();
  // Keyed so that switching mission resets the draft, the simulation and the pending command.
  return <Console key={missionId} missionId={missionId} />;
}

function Console({ missionId }: { missionId: string }) {
  const mission = useMission(missionId);
  const streamStatus = useMissionStream(missionId);
  const { stop, autopilot, classify, reply, helm } = useMissionActions(missionId);
  const canPlay = usePermission("mission:play");
  const canSubmit = usePermission("command:submit");
  const canDecide = usePermission("command:decide");
  const canAskDoctrine = usePermission("doctrine:ask");
  const [draft, setDraft] = useState("");
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [commandId, setCommandId] = useState<string | null>(null);
  const [voiceOutcome, setVoiceOutcome] = useState<VoiceOrderOutcome | null>(null);
  const [correctionOf, setCorrectionOf] = useState<string | null>(null);

  const onVoiceOutcome = useCallback((outcome: VoiceOrderOutcome) => {
    setVoiceOutcome(outcome);
    setCorrectionOf(null);
    if (outcome.command_id) setCommandId(outcome.command_id);
  }, []);
  const onCorrect = (transcript: string, correctedId: string | null) => {
    setDraft(transcript);
    setCorrectionOf(correctedId);
    setVoiceOutcome(null);
  };

  const classifyMutate = classify.mutate;
  const onClassify = useCallback(
    (contactId: string, classification: Classification) => classifyMutate({ contactId, classification }),
    [classifyMutate],
  );
  const replyMutate = reply.mutate;
  const onReply = useCallback((ship: string, approve: boolean) => replyMutate({ ship, approve }), [replyMutate]);

  if (mission.isPending) return <Loading label="Chargement de la mission…" />;
  if (mission.isError) {
    return <ErrorPanel message={describeError(mission.error).message} onRetry={() => void mission.refetch()} />;
  }

  const m = mission.data;
  const running = m.phase === "running";
  const me = m.ships.find((s) => s.name === m.player_ship);

  return (
    <main className="page console">
      <MissionBar
        missionId={m.id}
        title={m.title}
        playerShip={m.player_ship}
        elapsed={m.elapsed_s}
        duration={m.duration_s}
        running={running}
        streamStatus={streamStatus}
        autopilot={m.autopilot}
        onAutopilot={(enabled) => autopilot.mutate(enabled)}
        onStop={() => stop.mutate()}
        stopping={stop.isPending}
      />
      {stop.error && <ErrorPanel message={describeError(stop.error).message} />}

      {!running && m.debrief ? (
        <Debrief debrief={m.debrief} />
      ) : (
        <div className="console-grid">
          <div className="stack">
            <Radar
              ships={m.ships}
              contacts={m.contacts}
              player={m.player_ship}
              station={m.station}
              tracks={simulation?.track_by_ship}
            />
            <ContactList contacts={m.contacts} onClassify={onClassify} disabled={!running || !canPlay} />
          </div>

          <div className="stack">
            <VoiceCapture
              missionId={m.id}
              canSubmit={running && canSubmit}
              correctionOf={correctionOf}
              onOutcome={onVoiceOutcome}
            />
            {voiceOutcome && (
              <InterpretationCard
                outcome={voiceOutcome}
                canSubmit={running && canSubmit}
                onCorrect={onCorrect}
                onDismiss={() => setVoiceOutcome(null)}
              />
            )}
            <OrderForm
              missionId={m.id}
              draft={draft}
              onDraftChange={setDraft}
              canSubmit={running && canSubmit}
              correctionOf={correctionOf}
              onCancelCorrection={() => setCorrectionOf(null)}
              onCommand={setCommandId}
              onSimulation={setSimulation}
            />
            {commandId && (
              <DecisionBar commandId={commandId} canDecide={canDecide} onDismiss={() => setCommandId(null)} />
            )}
            {commandId && canAskDoctrine && <OrderExplanation key={commandId} commandId={commandId} />}
            {simulation && <SimulationReport simulation={simulation} onClose={() => setSimulation(null)} />}
            <GuideOrders pending={m.pending_orders} planned={m.planned_orders} elapsed={m.elapsed_s} />
            <RecommendationList missionId={m.id} running={running} onUse={setDraft} />
            <RequestList requests={m.authorization_requests} canDecide={canDecide} onReply={onReply} />
            {m.manual_helm && me && running && (
              <HelmPanel
                helm={m.helm}
                headingDeg={me.heading_deg}
                speedMps={me.speed_mps}
                stationOffsetM={m.station?.offset_m}
                onHelm={(order) => helm.mutate(order)}
              />
            )}
          </div>

          <div className="stack">
            <ObjectiveList objectives={m.objectives} />
            <ShipTable ships={m.ships} player={m.player_ship} />
            <RadioLog messages={m.radio_messages} />
            {canAskDoctrine && <DoctrinePanel />}
          </div>
        </div>
      )}
    </main>
  );
}
