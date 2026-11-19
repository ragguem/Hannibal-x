import { describe, expect, it } from "vitest";
import { FakeBackend } from "../../mocks/fake-backend";
import { toScene } from "./to-scene";

describe("toScene", () => {
  it("translates a mission into the engine's legacy state", () => {
    const backend = new FakeBackend(() => 0);
    backend.signIn("instructeur", "demo");
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: true });
    const scene = toScene(mission);

    expect(scene).toMatchObject({ phase: "running", ended: false, titre: "Transit en colonne", player: "alfa", guide: "hannibal", manual: true });
    expect(scene.helm).toEqual({ cap: 20, kn: 12, rudder: 0 });
    expect(scene.ships[1]).toMatchObject({ name: "alfa", etat: "Vous", role: "escorte" });
    expect(scene.contacts[0]).toMatchObject({ id: "TRK021", cls: "inconnu", cap: 235, vit: 16, cpa_nm: 0.8 });
    expect(scene.msgs[0]).toMatchObject({ t: 0, from: "HANNIBAL", to: "TOUS", kind: "ordre" });
    expect(scene.station).toMatchObject({ err: 0 });
  });

  it("has no station when the player is the guide", () => {
    const backend = new FakeBackend(() => 0);
    backend.signIn("instructeur", "demo");
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "hannibal", autopilot: false, manual_helm: false });
    expect(toScene(mission).station).toBeNull();
  });
});
