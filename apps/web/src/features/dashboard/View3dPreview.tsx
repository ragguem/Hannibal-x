import { Link } from "react-router";
import { Icon } from "../../components/Icon";
import { Panel } from "../../components/Panel";

/** Still picture of the 3D view; the live scene stays on its own page so the dashboard does not load three.js. */
export function View3dPreview() {
  return (
    <Panel
      id="dash-3d"
      title="Vue 3D · vue d'ensemble"
      icon="cube"
      className="dash-3d"
      actions={
        <Link to="/vue3d" className="btn sm ghost icon-btn" aria-label="Ouvrir la vue 3D">
          <Icon name="expand" size={14} />
        </Link>
      }
    >
      <Link to="/vue3d" className="preview-3d" aria-label="Ouvrir la vue 3D">
        <svg viewBox="0 0 400 160" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs>
            <linearGradient id="preview-sky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1b3355" />
              <stop offset="55%" stopColor="#0e2440" />
              <stop offset="100%" stopColor="#081526" />
            </linearGradient>
          </defs>
          <rect width="400" height="160" fill="url(#preview-sky)" />
          <path d="M0 70H400" className="preview-horizon" />
          {[
            [70, 110, 1.2],
            [180, 95, 1],
            [260, 120, 1.3],
            [330, 88, 0.8],
          ].map(([x, y, s]) => (
            <g key={`${String(x)}-${String(y)}`} transform={`translate(${String(x)} ${String(y)}) scale(${String(s)})`}>
              <path className="preview-wake" d="M-60 4C-40 8 -20 6 0 3" />
              <path className="preview-hull" d="M-30 0H30L22 8H-24Z" />
              <path className="preview-deck" d="M-14 0V-8H8V0M-4 -8V-16H2V-8" />
            </g>
          ))}
        </svg>
      </Link>
    </Panel>
  );
}
