/**
 * Invented figures for the dashboard mock-up. Each panel will read its own server data in a later feature;
 * until then nothing here comes from a mission, a publication or the register.
 */

export type Tone = "blue" | "green" | "amber" | "red" | "teal";

export interface Indicator {
  id: string;
  label: string;
  value: string;
  trend?: string;
  tone: Tone;
  progress?: number;
}

export type MissionStatus = "active" | "planned" | "done";

export interface MissionSummary {
  id: string;
  name: string;
  description: string;
  ships: number;
  period: string;
  status: MissionStatus;
  progress: number;
}

export type ShipStatus = "at_sea" | "in_transit" | "offline";

export interface FleetShip {
  name: string;
  status: ShipStatus;
  speedKn: number | null;
  signal: 0 | 1 | 2 | 3 | 4;
  /** Position on the mock map, in the map's 1000 × 560 frame. */
  x: number;
  y: number;
  headingDeg: number;
  track: string;
  tone: Tone;
}

export interface ShipDetail {
  name: string;
  identifier: string;
  mission: string;
  position: string;
  speedKn: number;
  headingDeg: number;
  state: string;
  lastContact: string;
  responsible: string;
  speedHistory: number[];
}

export type EventKind = "ok" | "info" | "warning";

export interface LoggedEvent {
  time: string;
  kind: EventKind;
  label: string;
  author: string;
}

export type AlertLevel = "critical" | "warning" | "info";

export interface RaisedAlert {
  time: string;
  level: AlertLevel;
  title: string;
  detail: string;
  action: string;
}

export const SAMPLE_INDICATORS: Indicator[] = [
  { id: "fleet", label: "Navires en flotte", value: "5", trend: "+1", tone: "blue" },
  { id: "missions", label: "Missions actives", value: "2", trend: "+0", tone: "teal" },
  { id: "ready", label: "Navires opérationnels", value: "4", tone: "green", progress: 80 },
  { id: "alerts", label: "Alerte active", value: "1", tone: "red" },
  { id: "weather", label: "Mer calme", value: "18 °C", tone: "amber" },
];

export const SAMPLE_MISSIONS: MissionSummary[] = [
  {
    id: "TRANSIT-001",
    name: "TRANSIT-001",
    description: "Formation côtière, exercice",
    ships: 2,
    period: "19/11 – 20/11",
    status: "active",
    progress: 65,
  },
  {
    id: "EXERCICE-ALPHA",
    name: "EXERCICE-ALPHA",
    description: "Manœuvres tactiques",
    ships: 3,
    period: "20/11 – 21/11",
    status: "planned",
    progress: 0,
  },
  {
    id: "SURVEILLANCE-DELTA",
    name: "SURVEILLANCE-DELTA",
    description: "Surveillance de zone",
    ships: 1,
    period: "17/11 – 18/11",
    status: "done",
    progress: 100,
  },
];

export const SAMPLE_FLAGSHIP: FleetShip = {
  name: "HANNIBAL",
  status: "at_sea",
  speedKn: 18.5,
  signal: 4,
  x: 470,
  y: 150,
  headingDeg: 87,
  track: "M300 230 C 360 190, 420 160, 470 150",
  tone: "blue",
};

export const SAMPLE_FLEET: FleetShip[] = [
  SAMPLE_FLAGSHIP,
  { name: "ALFA", status: "at_sea", speedKn: 16.2, signal: 4, x: 290, y: 270, headingDeg: 20, track: "M330 400 C 320 350, 300 300, 290 270", tone: "green" },
  { name: "CHARLIE", status: "in_transit", speedKn: 17.8, signal: 3, x: 560, y: 280, headingDeg: 120, track: "M560 280 C 600 300, 640 330, 680 360", tone: "amber" },
  { name: "DELTA", status: "at_sea", speedKn: 12.0, signal: 3, x: 520, y: 360, headingDeg: 60, track: "M400 420 C 440 400, 480 380, 520 360", tone: "teal" },
  { name: "ECHO", status: "offline", speedKn: null, signal: 0, x: 760, y: 170, headingDeg: 0, track: "", tone: "blue" },
];

export const SAMPLE_SHIP_DETAIL: ShipDetail = {
  name: "HANNIBAL",
  identifier: "SHP-001",
  mission: "TRANSIT-001",
  position: "36,7421° N · 10,2534° E",
  speedKn: 18.5,
  headingDeg: 87,
  state: "Opérationnel",
  lastContact: "21:54:20 (il y a 12 s)",
  responsible: "Cdt Alpha",
  speedHistory: [14, 15, 15.5, 16, 15.8, 16.5, 17, 17.6, 18, 18.2, 18.5],
};

export const SAMPLE_EVENTS: LoggedEvent[] = [
  { time: "21:54:20", kind: "ok", label: "Position mise à jour : HANNIBAL", author: "Système" },
  { time: "21:52:13", kind: "info", label: "Changement de cap : ALFA (087°)", author: "Système" },
  { time: "21:50:45", kind: "warning", label: "Alerte de zone : zone interdite approchée", author: "Système" },
  { time: "21:48:37", kind: "info", label: "Mission TRANSIT-001 : progression 50 %", author: "Opérateur 1" },
  { time: "21:46:12", kind: "ok", label: "Connexion du navire DELTA", author: "Système" },
];

export const SAMPLE_ALERTS: RaisedAlert[] = [
  { time: "21:50:45", level: "critical", title: "Alerte de zone", detail: "Approche d'une zone interdite", action: "Voir" },
  { time: "21:47:32", level: "warning", title: "Communication", detail: "Perte temporaire avec ALFA", action: "Détails" },
  { time: "21:40:18", level: "info", title: "Météo", detail: "Rafales de vent : 35 nd", action: "Détails" },
];

/** Restricted area drawn on the mock map. */
export const SAMPLE_ALERT_ZONE = { x: 760, y: 300, radius: 70 };
