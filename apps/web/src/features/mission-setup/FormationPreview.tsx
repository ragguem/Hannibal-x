import { memo } from "react";

interface FormationPreviewProps {
  guide: string;
  ships: string[];
  player: string | undefined;
}

const SPACING = 34;

/** Fleet order at start: guide ahead, the others astern in column (the scenario summary carries no geometry). */
export const FormationPreview = memo(function FormationPreview({ guide, ships, player }: FormationPreviewProps) {
  const order = [guide, ...ships.filter((s) => s !== guide)];
  const height = SPACING * order.length + 20;
  return (
    <figure className="card preview">
      <figcaption className="lbl">Aperçu de la formation</figcaption>
      <svg viewBox={`0 0 220 ${height}`} role="img" aria-label={`Colonne : ${order.join(", ")}`}>
        <line x1="70" y1="10" x2="70" y2={height - 10} className="track" />
        {order.map((ship, i) => {
          const y = 22 + i * SPACING;
          const cls = ship === player ? "hull me" : ship === guide ? "hull guide" : "hull";
          return (
            <g key={ship} transform={`translate(70 ${y})`}>
              <path d="M0 -12 L6 6 L0 2 L-6 6 Z" className={cls} />
              <text x="18" y="5">
                {ship.toUpperCase()}
                {ship === guide ? " · guide" : ""}
                {ship === player ? " · vous" : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
});
