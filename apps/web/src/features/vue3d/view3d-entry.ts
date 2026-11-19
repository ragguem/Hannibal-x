// Standalone page (view3d.html): the WebGL engine owns its DOM, so it runs outside React and builds
// its own adapters. `?mission=<id>` follows a mission; `?demo` or no mission plays the built-in demo.
import { HttpApi } from "../../services/http-api";
import { SseStream } from "../../services/sse-stream";
import { attach } from "./engine/view3d.js";
import { toScene } from "./to-scene";
import "./view3d.css";

async function enableMocks() {
  if (import.meta.env.VITE_API_MOCKS !== "1") return;
  const { worker } = await import("../../mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
}

const missionId = new URLSearchParams(location.search).get("mission");
const api = new HttpApi();
const stream = new SseStream(api);

void enableMocks().then(() => {
  attach({
    console: missionId ? `/missions/${encodeURIComponent(missionId)}` : "/",
    subscribe: (onScene, onDown) => {
      if (!missionId) return () => undefined;
      return stream.subscribe(missionId, {
        onEvent: (event) => {
          if (event.type === "situation") onScene(toScene(event.mission));
        },
        onStatus: (status) => {
          if (status === "closed") onDown();
        },
      });
    },
    sendHelm: (order) => {
      if (missionId) api.setHelm(missionId, order).catch((e: unknown) => console.warn("barre refusée", e));
    },
  });
});
