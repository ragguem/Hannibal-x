const PATHS = {
  ship: "M3 16h18l-2.5 4h-13zM6 15V10h12v5M9 10V6h6v4M12 3v3",
  target: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2",
  check: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M8 12l3 3l5-6",
  alert: "M12 3l10 18H2zM12 10v5M12 18v.5",
  weather: "M7 18h10a4 4 0 0 0 0-8a6 6 0 0 0-11.5 2A3 3 0 0 0 7 18",
  map: "M3 6l6-2l6 2l6-2v14l-6 2l-6-2l-6 2zM9 4v14M15 6v14",
  list: "M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1",
  cube: "M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5",
  bell: "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 7v5l3 2",
  home: "M3 11l9-7l9 7M5 10v10h14V10",
  gauge: "M4 18a8 8 0 1 1 16 0M12 18l4-6",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9c-4.5-1-8-4-8-9V6z",
  book: "M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6M20 4v14h-6",
  pin: "M12 21s-6-6-6-11a6 6 0 0 1 12 0c0 5-6 11-6 11M12 8a2 2 0 1 0 0 4a2 2 0 1 0 0-4",
  user: "M12 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8M4 20a8 8 0 0 1 16 0",
  arrow: "M5 12h14M13 6l6 6l-6 6",
  chevron: "M6 9l6 6l6-6",
  logout: "M10 4H5v16h5M14 8l4 4l-4 4M18 12H9",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  info: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 8h.01M11 12h1v5h1",
  play: "M8 5v14l11-7z",
  save: "M5 4h11l3 3v13H5zM8 4v5h7V4M8 20v-6h8v6",
  star: "M12 3l2.7 5.6l6.1.9l-4.4 4.3l1 6.1L12 17l-5.4 2.9l1-6.1L3.2 9.5l6.1-.9z",
  formation: "M12 4a2 2 0 1 0 0 4a2 2 0 1 0 0-4M5 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4M19 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4M12 8v4l-6 4M12 12l6 4",
  crosshair: "M12 3v4M12 17v4M3 12h4M17 12h4M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  layers: "M12 4l9 5l-9 5l-9-5zM3 14l9 5l9-5",
} as const;

export type IconName = keyof typeof PATHS;

/** Line icon drawn in the current text colour; decorative unless given a `title`. */
export function Icon({ name, size = 18, title }: { name: IconName; size?: number; title?: string }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
