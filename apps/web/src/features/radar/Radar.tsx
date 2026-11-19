import { memo, useState } from "react";
import type { Contact, Ship, Simulation } from "../../socle/ports";
import { inside, project, RANGES_NM, type RangeNm } from "./radar-geometry";

const R = 200;

interface RadarProps {
  ships: Ship[];
  contacts: Contact[];
  player: string;
  station?: { east_m: number; north_m: number } | null | undefined;
  tracks?: Simulation["track_by_ship"] | undefined;
}

export const Radar = memo(function Radar({ ships, contacts, player, station, tracks }: RadarProps) {
  const [range, setRange] = useState<RangeNm>(4);
  const me = ships.find((s) => s.name === player) ?? ships[0];
  const origin = me ? { east: me.east_m, north: me.north_m } : { east: 0, north: 0 };
  const at = (east: number, north: number) => project(east, north, origin, range, R);

  return (
    <section className="card radar" aria-labelledby="radar-title">
      <div className="row">
        <h2 id="radar-title" className="lbl grow">
          Radar · {range} NM
        </h2>
        <div role="group" aria-label="Échelle" className="row">
          {RANGES_NM.map((r) => (
            <button key={r} type="button" className="btn sm" aria-pressed={r === range} onClick={() => setRange(r)}>
              {r}
            </button>
          ))}
        </div>
      </div>
      <svg
        viewBox={`${-R - 10} ${-R - 10} ${2 * R + 20} ${2 * R + 20}`}
        role="img"
        aria-label={`Radar centré sur ${player.toUpperCase()}, ${ships.length} navires et ${contacts.length} contacts. Le détail est dans les tableaux.`}
      >
        <circle r={R} className="ring" />
        <circle r={R / 2} className="ring" />
        <line x1={0} y1={-R} x2={0} y2={R} className="ring" />
        <line x1={-R} y1={0} x2={R} y2={0} className="ring" />
        <text x={4} y={-R + 12} className="ring-label">
          N
        </text>
        {tracks &&
          Object.entries(tracks).map(([ship, points]) => (
            <polyline
              key={ship}
              className="sim-track"
              points={points.map((p) => {
                const q = at(p.east_m, p.north_m);
                return `${q.x},${q.y}`;
              }).join(" ")}
            />
          ))}
        {station && (() => {
          const p = at(station.east_m, station.north_m);
          return inside(p, R) ? <circle cx={p.x} cy={p.y} r={6} className="station" /> : null;
        })()}
        {contacts.map((c) => {
          const p = at(c.east_m, c.north_m);
          if (!inside(p, R)) return null;
          return (
            <g key={c.id} transform={`translate(${p.x} ${p.y})`} className={`contact ${c.classification}`}>
              <rect x={-5} y={-5} width={10} height={10} transform="rotate(45)" />
              <text x={9} y={4}>
                {c.id}
              </text>
            </g>
          );
        })}
        {ships.map((s) => {
          const p = at(s.east_m, s.north_m);
          if (!inside(p, R)) return null;
          return (
            <g
              key={s.name}
              transform={`translate(${p.x} ${p.y}) rotate(${s.heading_deg})`}
              className={s.name === player ? "ship me" : "ship"}
            >
              <path d="M0 -9 L5 6 L0 3 L-5 6 Z" />
              <text x={8} y={4} transform={`rotate(${-s.heading_deg})`}>
                {s.name.toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
});
