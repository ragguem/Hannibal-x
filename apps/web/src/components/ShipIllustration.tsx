import { useId } from "react";

/** Side view of a frigate at sea; decorative, sized by its container. */
export function ShipIllustration({ pennant = "F 712" }: { pennant?: string }) {
  const uid = useId();
  const sky = `${uid}-sky`;
  const sea = `${uid}-sea`;
  const hull = `${uid}-hull`;
  return (
    <svg className="ship-illustration" viewBox="0 0 480 220" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id={sky} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#24456f" />
          <stop offset="1" stopColor="#0e223b" />
        </linearGradient>
        <linearGradient id={sea} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#123257" />
          <stop offset="1" stopColor="#06111f" />
        </linearGradient>
        <linearGradient id={hull} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9aabc4" />
          <stop offset="1" stopColor="#56657d" />
        </linearGradient>
      </defs>
      <rect width="480" height="150" fill={`url(#${sky})`} />
      <rect y="148" width="480" height="72" fill={`url(#${sea})`} />
      <path className="ship-coast" d="M0 150 L40 138 L90 144 L140 132 L170 150 Z" />
      <g className="ship-superstructure">
        <path d="M150 128 L330 128 L322 104 L270 104 L262 82 L214 82 L206 104 L168 104 Z" />
        <rect x="226" y="56" width="5" height="28" />
        <rect x="210" y="62" width="38" height="4" />
        <path d="M290 104 L300 88 L312 88 L316 104 Z" />
        <rect x="120" y="120" width="26" height="8" />
        <rect x="108" y="122" width="24" height="3" />
      </g>
      <path className="ship-windows" d="M220 92 h30" />
      <path d="M70 128 L400 128 L388 160 L96 160 Z" fill={`url(#${hull})`} />
      <path className="ship-waterline" d="M92 152 L392 152" />
      <text className="ship-pennant" x="128" y="148">
        {pennant}
      </text>
      <path className="ship-wake" d="M390 158 C420 162 450 160 480 166 M96 160 C70 166 40 164 0 170 M150 172 C220 176 300 176 360 170" />
    </svg>
  );
}
