import { useState } from "react";
import { Link } from "react-router";
import { clock } from "../../components/format";
import type { StreamStatus } from "../../socle/ports";

const STREAM_LABEL: Record<StreamStatus, string> = {
  connecting: "connexion…",
  live: "temps réel",
  polling: "flux coupé · relecture 2 s",
  closed: "flux fermé",
};

interface MissionBarProps {
  missionId: string;
  title: string;
  playerShip: string;
  elapsed: number;
  duration: number;
  running: boolean;
  streamStatus: StreamStatus;
  autopilot: boolean;
  onAutopilot: (enabled: boolean) => void;
  onStop: () => void;
  stopping: boolean;
}

export function MissionBar(props: MissionBarProps) {
  const { missionId, title, playerShip, elapsed, duration, running, streamStatus, autopilot } = props;
  const [confirming, setConfirming] = useState(false);
  return (
    <header className="mission-bar card">
      <div>
        <h1>{title}</h1>
        <span className="mut">
          Vous êtes <b>{playerShip.toUpperCase()}</b>
        </span>
      </div>
      <time className="mono clock" aria-label="Temps de mission">
        {clock(elapsed)} / {clock(duration)}
      </time>
      <span className={streamStatus === "live" ? "chip" : "chip warn"} role="status">
        <span className={streamStatus === "live" ? "dot ok" : "dot"} aria-hidden="true" />
        {STREAM_LABEL[streamStatus]}
      </span>
      <span className="grow" />
      {running && (
        <button
          type="button"
          className={autopilot ? "btn sm amber" : "btn sm"}
          aria-pressed={autopilot}
          onClick={() => props.onAutopilot(!autopilot)}
        >
          Mode automatique
        </button>
      )}
      <Link className="btn sm" to={`/vue3d/${encodeURIComponent(missionId)}`}>
        Vue 3D
      </Link>
      {running &&
        (confirming ? (
          <>
            <button type="button" className="btn sm amber" disabled={props.stopping} onClick={props.onStop}>
              Confirmer l'arrêt
            </button>
            <button type="button" className="btn sm ghost" onClick={() => setConfirming(false)}>
              Annuler
            </button>
          </>
        ) : (
          <button type="button" className="btn sm" onClick={() => setConfirming(true)}>
            Arrêter la mission
          </button>
        ))}
    </header>
  );
}
