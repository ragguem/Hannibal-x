import type { SetHelm } from "../../../socle/ports";
import type { Scene } from "../to-scene";

export interface EngineLink {
  subscribe(onScene: (scene: Scene) => void, onDown: () => void): () => void;
  sendHelm(order: SetHelm): void;
  console: string;
}

/** Plugs the live feed into the engine; without it (or with `?demo`) the engine plays its demo. */
export function attach(link: EngineLink): () => void;
