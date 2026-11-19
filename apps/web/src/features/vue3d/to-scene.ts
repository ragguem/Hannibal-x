import type { Mission } from "../../socle/ports";

/** The state shape the 3D engine was written against (legacy app_v3), kept so the engine moves unchanged. */
export interface Scene {
  phase: Mission["phase"];
  ended: boolean;
  titre: string;
  t: number;
  duree: number;
  player: string;
  guide: string;
  form: string;
  manual: boolean;
  helm: { cap: number; kn: number; rudder: number };
  station: { x: number; y: number; err: number } | null;
  ships: { name: string; x: number; y: number; hdg: number; sog: number; role: string; etat: string }[];
  contacts: {
    id: string;
    type: string;
    cls: string;
    cap: number;
    vit: number;
    x: number;
    y: number;
    range_nm: number | null;
    brg: number | null;
    cpa_nm: number | null;
  }[];
  msgs: { t: number; from: string; to: string; kind: string; en: string; fr: string }[];
}

export function toScene(m: Mission): Scene {
  return {
    phase: m.phase,
    ended: m.phase === "ended",
    titre: m.title,
    t: m.elapsed_s,
    duree: m.duration_s,
    player: m.player_ship,
    guide: m.guide_ship,
    form: m.formation,
    manual: m.manual_helm,
    helm: { cap: m.helm.course_deg, kn: m.helm.speed_kn, rudder: m.helm.rudder },
    station: m.station ? { x: m.station.east_m, y: m.station.north_m, err: Math.round(m.station.offset_m) } : null,
    ships: m.ships.map((s) => ({
      name: s.name,
      x: s.east_m,
      y: s.north_m,
      hdg: s.heading_deg,
      sog: s.speed_mps,
      role: s.role,
      etat: s.status_for_player,
    })),
    contacts: m.contacts.map((c) => ({
      id: c.id,
      type: c.category,
      cls: c.classification,
      cap: c.course_deg,
      vit: Math.round(c.speed_kn),
      x: c.east_m,
      y: c.north_m,
      range_nm: c.range_nm ?? null,
      brg: c.bearing_deg ?? null,
      cpa_nm: c.cpa_nm ?? null,
    })),
    msgs: m.radio_messages.map((r) => ({
      t: r.sent_at_s,
      from: r.sender,
      to: r.recipient,
      kind: r.kind,
      en: r.text_en,
      fr: r.text_fr,
    })),
  };
}
