import { useEffect, useRef } from "react";
import { deg3, knots } from "../../components/format";
import type { Helm, SetHelm } from "../../socle/ports";

interface HelmPanelProps {
  helm: Helm;
  headingDeg: number;
  speedMps: number;
  stationOffsetM?: number | undefined;
  onHelm: (order: SetHelm) => void;
}

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/** Manual helm: ← → hold the rudder, ↑ ↓ change speed. Keys are ignored while typing an order. */
export function HelmPanel({ helm, headingDeg, speedMps, stationOffsetM, onHelm }: HelmPanelProps) {
  const send = useRef(onHelm);
  useEffect(() => {
    send.current = onHelm;
  });

  useEffect(() => {
    const held = { left: false, right: false };
    let rudder = 0;
    const applyRudder = () => {
      const next = held.left === held.right ? 0 : held.left ? -1 : 1;
      if (next !== rudder) {
        rudder = next;
        send.current({ rudder: next });
      }
    };
    const down = (e: KeyboardEvent) => {
      if (typing(e.target) || e.repeat) return;
      if (e.key === "ArrowLeft") held.left = true;
      else if (e.key === "ArrowRight") held.right = true;
      else if (e.key === "ArrowUp") send.current({ speed_change_kn: 1 });
      else if (e.key === "ArrowDown") send.current({ speed_change_kn: -1 });
      else return;
      e.preventDefault();
      applyRudder();
    };
    const up = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") held.left = false;
      else if (e.key === "ArrowRight") held.right = false;
      else return;
      applyRudder();
    };
    const release = () => {
      held.left = held.right = false;
      applyRudder();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", release);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", release);
    };
  }, []);

  const rudderLabel = helm.rudder < 0 ? "bâbord" : helm.rudder > 0 ? "tribord" : "au milieu";
  return (
    <section className="card helm" aria-labelledby="helm-title">
      <h2 id="helm-title" className="lbl">
        Barre manuelle
      </h2>
      <p className="mono" role="status">
        Barre {rudderLabel} · cap {deg3(headingDeg)}° (ordonné {deg3(helm.course_deg)}°) · {knots(speedMps)} kn (ordonné{" "}
        {Math.round(helm.speed_kn)})
        {stationOffsetM !== undefined && ` · poste à ${Math.round(stationOffsetM)} m`}
      </p>
      <div className="row wrap">
        <button type="button" className="btn sm" onClick={() => onHelm({ course_change_deg: -5 })}>
          Cap −5°
        </button>
        <button type="button" className="btn sm" onClick={() => onHelm({ course_change_deg: 5 })}>
          Cap +5°
        </button>
        <button type="button" className="btn sm" onClick={() => onHelm({ speed_change_kn: -1 })}>
          −1 kn
        </button>
        <button type="button" className="btn sm" onClick={() => onHelm({ speed_change_kn: 1 })}>
          +1 kn
        </button>
        <button type="button" className="btn sm" onClick={() => onHelm({ rudder: 0 })}>
          Barre au milieu
        </button>
      </div>
      <small className="mut">Clavier : ← → barre (maintenir) · ↑ ↓ vitesse</small>
    </section>
  );
}
