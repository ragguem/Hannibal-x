import type { KeyboardEvent } from "react";
import { Link } from "react-router";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import type { FleetShip } from "./dashboard-sample";

/** Invented coastlines: a mock-up backdrop, not a chart. The real map comes with its own feature. */
const LAND = [
  "M-1000 -1000H2000V40H1000C900 70 820 40 760 60C700 80 640 50 600 90C570 120 520 100 480 80C430 60 380 90 330 70C260 40 200 80 140 60C90 45 40 70 0 60H-1000Z",
  "M-1000 470H0C80 440 150 470 230 450C300 430 360 470 430 480C520 495 600 450 690 470C780 490 860 450 1000 470H2000V1560H-1000Z",
  "M600 140C630 130 660 150 650 175C640 200 610 195 600 175C592 160 590 148 600 140Z",
];

/** Sea, coasts and grid run past the 1000 × 560 frame so a tall or wide panel shows no empty band. */
const GRID = Array.from({ length: 29 }, (_, i) => (i - 9) * 100);

interface OperationalMapProps {
  ships: FleetShip[];
  zone: { x: number; y: number; radius: number };
  selected: string;
  onSelect: (name: string) => void;
}

export function OperationalMap({ ships, zone, selected, onSelect }: OperationalMapProps) {
  const selectOnKey = (name: string) => (event: KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(name);
    }
  };

  return (
    <Panel
      id="dash-map"
      title="Carte opérationnelle"
      icon="map"
      className="dash-map"
      actions={
        <div className="map-toolbar">
          <span className="segmented" role="group" aria-label="Mode de la carte">
            <button type="button" className="btn sm" aria-pressed="true">
              2D
            </button>
            <Link to="/vue3d" className="btn sm">
              3D
            </Link>
          </span>
          <button type="button" className="btn sm ghost" disabled title="Arrive avec la fonctionnalité Carte">
            Couches
          </button>
          <button type="button" className="btn sm ghost icon-btn" disabled aria-label="Zoom avant">
            <Icon name="plus" size={14} />
          </button>
          <button type="button" className="btn sm ghost icon-btn" disabled aria-label="Zoom arrière">
            <Icon name="minus" size={14} />
          </button>
          <button type="button" className="btn sm ghost icon-btn" disabled aria-label="Plein écran">
            <Icon name="expand" size={14} />
          </button>
        </div>
      }
    >
      <div className="map-frame">
        <svg viewBox="0 0 1000 560" preserveAspectRatio="xMidYMid meet" role="group" aria-label="Situation de la flotte">
          <defs>
            <radialGradient id="map-sea" cx="50%" cy="45%" r="75%">
              <stop offset="0%" stopColor="#0f2a4a" />
              <stop offset="100%" stopColor="#081526" />
            </radialGradient>
            <radialGradient id="map-zone">
              <stop offset="0%" stopColor="#ff5d5d" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#ff5d5d" stopOpacity="0.05" />
            </radialGradient>
          </defs>
          <rect x="-1000" y="-1000" width="3000" height="2560" fill="#081526" />
          <rect width="1000" height="560" fill="url(#map-sea)" />
          <g className="map-grid">
            {GRID.map((at) => (
              <g key={at}>
                <line x1={at} y1="-1000" x2={at} y2="1560" />
                <line x1="-1000" y1={at} x2="2000" y2={at} />
              </g>
            ))}
          </g>
          {LAND.map((d) => (
            <path key={d} className="map-land" d={d} />
          ))}

          <g className="map-zone">
            <circle cx={zone.x} cy={zone.y} r={zone.radius} fill="url(#map-zone)" />
            <circle cx={zone.x} cy={zone.y} r={zone.radius * 0.55} />
            <path d={`M${String(zone.x)} ${String(zone.y - 16)}l16 28h-32z`} className="map-zone-mark" />
          </g>

          {ships.map((ship) => (
            <g
              key={ship.name}
              className={`map-ship ${ship.tone} ${ship.status} ${ship.name === selected ? "on" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={`${ship.name}, cap ${String(ship.headingDeg)}°`}
              aria-pressed={ship.name === selected}
              onClick={() => onSelect(ship.name)}
              onKeyDown={selectOnKey(ship.name)}
            >
              {ship.track && <path className="map-track" d={ship.track} />}
              <path
                className="map-ship-mark"
                d="M0 -11L8 9L0 5L-8 9Z"
                transform={`translate(${String(ship.x)} ${String(ship.y)}) rotate(${String(ship.headingDeg)})`}
              />
              <g transform={`translate(${String(ship.x + 14)} ${String(ship.y - 22)})`}>
                <rect className="map-label" width={ship.name.length * 9 + 14} height="20" rx="4" />
                <text x="7" y="14">
                  {ship.name}
                </text>
              </g>
            </g>
          ))}

          <g className="map-north" transform="translate(32 40)">
            <path d="M0 -14L7 6L0 2L-7 6Z" />
            <text y="22" textAnchor="middle">
              N
            </text>
          </g>
          <g className="map-scale" transform="translate(24 530)">
            <path d="M0 0H200M0 -5V5M100 -4V4M200 -5V5" />
            <text y="-8">0</text>
            <text x="92" y="-8">
              25
            </text>
            <text x="186" y="-8">
              50 nq
            </text>
          </g>
        </svg>
      </div>
    </Panel>
  );
}
