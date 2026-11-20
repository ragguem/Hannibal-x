import { memo, useRef, useState } from "react";
import { deg3 } from "../../components/format";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";
import { columnLayout, scaleBarKm } from "./formation-layout";
import type { FormationPlan } from "./planner-config";

interface FormationMapProps {
  /** Guide first. */
  order: string[];
  guide: string;
  player: string;
  plan: FormationPlan;
}

const VIEW_WIDTH = 1000;
const VIEW_HEIGHT = 560;
const BASE_PX_PER_KM = 18;
const ZOOM_LEVELS = [0.5, 0.75, 1, 1.5, 2] as const;
const DEFAULT_ZOOM_INDEX = 2;
const SHIP_TONES = ["blue", "green", "amber", "teal"] as const;
const HULL_PATH = "M0 -20 C7 -10 8 6 6 17 L-6 17 C-8 6 -7 -10 0 -20 Z";

function MapToolbar({
  zoomIndex,
  onZoom,
  onRecenter,
  onFullscreen,
}: {
  zoomIndex: number;
  onZoom: (index: number) => void;
  onRecenter: () => void;
  onFullscreen: () => void;
}) {
  return (
    <div className="map-toolbar">
      <span className="segmented" role="group" aria-label="Mode d'affichage">
        <button type="button" className="btn sm" aria-pressed="true">
          2D
        </button>
        <button type="button" className="btn sm" aria-pressed="false" disabled title="Vue 3D disponible une fois la mission lancée">
          3D
        </button>
      </span>
      <button type="button" className="btn sm ghost" disabled title="Couches : prochaine version">
        <Icon name="layers" size={14} /> Couches
      </button>
      <button
        type="button"
        className="btn sm ghost icon-btn"
        aria-label="Zoom arrière"
        disabled={zoomIndex === 0}
        onClick={() => onZoom(zoomIndex - 1)}
      >
        <Icon name="minus" size={14} />
      </button>
      <button
        type="button"
        className="btn sm ghost icon-btn"
        aria-label="Zoom avant"
        disabled={zoomIndex === ZOOM_LEVELS.length - 1}
        onClick={() => onZoom(zoomIndex + 1)}
      >
        <Icon name="plus" size={14} />
      </button>
      <button type="button" className="btn sm ghost icon-btn" aria-label="Plein écran" onClick={onFullscreen}>
        <Icon name="expand" size={14} />
      </button>
      <button type="button" className="btn sm ghost icon-btn" aria-label="Recentrer" onClick={onRecenter}>
        <Icon name="crosshair" size={14} />
      </button>
    </div>
  );
}

/** Start formation drawn from the planner settings; the background is a stylised sea, not a chart. */
export const FormationMap = memo(function FormationMap({ order, guide, player, plan }: FormationMapProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const pxPerKm = BASE_PX_PER_KM * (ZOOM_LEVELS[zoomIndex] ?? 1);

  const placed = columnLayout(order, plan);
  const centerEast = placed.reduce((sum, ship) => sum + ship.eastKm, 0) / Math.max(placed.length, 1);
  const centerNorth = placed.reduce((sum, ship) => sum + ship.northKm, 0) / Math.max(placed.length, 1);
  const points = placed.map((ship) => ({
    ...ship,
    x: VIEW_WIDTH / 2 + (ship.eastKm - centerEast) * pxPerKm,
    y: VIEW_HEIGHT / 2 - (ship.northKm - centerNorth) * pxPerKm,
  }));
  const barKm = scaleBarKm(pxPerKm);
  const barPx = barKm * pxPerKm;

  const toggleFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else if (document.fullscreenEnabled) void frameRef.current?.requestFullscreen();
  };

  const description = `Formation en colonne au cap ${deg3(plan.headingDeg)}°, espacement ${String(plan.spacingKm)} km : ${order
    .map((ship) => ship.toUpperCase())
    .join(", ")}`;

  return (
    <Panel
      id="planner-map"
      title="Aperçu de la formation"
      icon="map"
      className="planner-map"
      actions={
        <MapToolbar
          zoomIndex={zoomIndex}
          onZoom={setZoomIndex}
          onRecenter={() => setZoomIndex(DEFAULT_ZOOM_INDEX)}
          onFullscreen={toggleFullscreen}
        />
      }
    >
      <div className="map-frame formation-frame" ref={frameRef}>
        <svg viewBox={`0 0 ${String(VIEW_WIDTH)} ${String(VIEW_HEIGHT)}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={description}>
          <defs>
            <radialGradient id="formation-sea" cx="50%" cy="50%" r="75%">
              <stop offset="0" stopColor="#123a66" />
              <stop offset="1" stopColor="#07172b" />
            </radialGradient>
            <radialGradient id="formation-glow">
              <stop offset="0" stopColor="#4aa3ff" stopOpacity="0.45" />
              <stop offset="1" stopColor="#4aa3ff" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect x="-500" y="-300" width="2000" height="1160" fill="url(#formation-sea)" />
          <g className="map-grid">
            {Array.from({ length: 13 }, (_, i) => (
              <line key={`v${String(i)}`} x1={i * 100 - 100} y1="-300" x2={i * 100 - 100} y2="860" />
            ))}
            {Array.from({ length: 9 }, (_, i) => (
              <line key={`h${String(i)}`} x1="-500" y1={i * 100 - 100} x2="1500" y2={i * 100 - 100} />
            ))}
          </g>
          <path className="map-land" d="M-500 -300 H1500 V40 C1300 70 1180 20 1040 60 C900 100 820 40 700 70 C560 105 470 50 330 80 C200 108 90 60 -500 90 Z" />
          <path className="map-land" d="M-500 860 V480 C-200 470 40 520 180 500 C320 480 420 530 560 515 C720 498 820 540 980 520 C1150 500 1300 530 1500 510 V860 Z" />
          <path className="map-land" d="M760 210 C790 190 840 196 850 222 C858 246 822 262 792 254 C766 246 748 228 760 210 Z" />

          <polyline className="formation-link" points={points.map((p) => `${String(p.x)},${String(p.y)}`).join(" ")} />

          {points.map((point, rank) => {
            const isGuide = point.name === guide;
            const isPlayer = point.name === player;
            const tone = SHIP_TONES[rank % SHIP_TONES.length] ?? "blue";
            const subtitle = isGuide ? "(Guide)" : isPlayer ? "(Vous)" : null;
            const labelHeight = subtitle ? 38 : 24;
            const labelOffsetY = rank % 2 === 0 ? -34 - labelHeight : 34;
            return (
              <g key={point.name} className={`formation-ship ${tone}${isPlayer ? " me" : ""}`} transform={`translate(${String(point.x)} ${String(point.y)})`}>
                <ellipse className="formation-glow" rx="34" ry="22" fill="url(#formation-glow)" />
                {isPlayer && <circle className="formation-ring" r="24" />}
                <path className="formation-hull" d={HULL_PATH} transform={`rotate(${String(plan.headingDeg)})`} />
                <g transform={`translate(0 ${String(labelOffsetY)})`}>
                  <rect className="formation-label" x="-52" width="104" height={labelHeight} rx="5" />
                  <text x="0" y="16" textAnchor="middle">
                    {point.name.toUpperCase()}
                  </text>
                  {subtitle && (
                    <text className="formation-subtitle" x="0" y="31" textAnchor="middle">
                      {subtitle}
                    </text>
                  )}
                </g>
              </g>
            );
          })}

          <g className="map-north" transform="translate(40 52)">
            <path d="M0 -24 L9 6 L0 0 L-9 6 Z" />
            <text x="0" y="24" textAnchor="middle">
              N
            </text>
          </g>
          <g className="map-scale" transform={`translate(30 ${String(VIEW_HEIGHT - 34)})`}>
            <path d={`M0 0 V-8 M0 0 H${String(barPx)} V-8 M${String(barPx / 2)} 0 V-5`} />
            <text x="0" y="18">
              0
            </text>
            <text x={barPx / 2} y="18" textAnchor="middle">
              {barKm / 2}
            </text>
            <text x={barPx} y="18" textAnchor="middle">
              {barKm} km
            </text>
          </g>
          <g className="formation-minimap" transform={`translate(${String(VIEW_WIDTH - 180)} 16)`}>
            <rect width="164" height="100" rx="6" />
            <path className="map-land" d="M0 0 H164 V22 C120 30 90 18 50 28 C30 33 12 26 0 30 Z M0 100 V78 C40 72 80 84 120 76 C140 72 152 78 164 74 V100 Z" />
            <rect className="formation-minimap-view" x="62" y="38" width="40" height="26" />
          </g>
        </svg>
      </div>
    </Panel>
  );
});
