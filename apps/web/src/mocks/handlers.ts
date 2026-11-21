import { http, HttpResponse, type HttpResponseResolver } from "msw";
import type {
  ChangePassword,
  Classification,
  CommandDecision,
  CreateUser,
  DoctrineQuestion,
  SetHelm,
  SignIn,
  StartMission,
  SubmitOrder,
} from "../socle/ports";
import { FakeBackend, FakeError, type FakeState } from "./fake-backend";

export interface Persistence {
  load(): FakeState | null;
  save(state: FakeState): void;
}

/** Shared by every tab and by the 3D page's frame, so they see the same session and missions. */
export const localStoragePersistence = (key = "hx-mocks-v2"): Persistence => ({
  load: () => {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as FakeState) : null;
  },
  save: (state) => localStorage.setItem(key, JSON.stringify(state)),
});

const errorBody = (e: FakeError) =>
  HttpResponse.json({ code: e.code, message: e.message, request_id: null }, { status: e.status });

export function createHandlers(backend = new FakeBackend(), persistence?: Persistence) {
  /** Runs `action` against the latest persisted state and answers the contract's way. */
  const handle =
    (
      action: (args: { params: Record<string, string>; body: unknown; url: URL }) => unknown,
      status = 200,
    ): HttpResponseResolver =>
    async ({ request, params }) => {
      const stored = persistence?.load();
      if (stored) backend.state = stored;
      const isForm = request.headers.get("Content-Type")?.startsWith("multipart/form-data") ?? false;
      const body: unknown =
        request.method === "GET" || request.method === "DELETE"
          ? null
          : isForm
            ? await request.formData()
            : await request.json().catch(() => null);
      try {
        const result = action({ params: params as Record<string, string>, body, url: new URL(request.url) });
        persistence?.save(backend.state);
        if (status === 204 || result === undefined) return new HttpResponse(null, { status: 204 });
        return HttpResponse.json(result as Record<string, unknown>, { status });
      } catch (e) {
        if (e instanceof FakeError) return errorBody(e);
        throw e;
      }
    };

  const sessionGet: HttpResponseResolver = () => {
    const stored = persistence?.load();
    if (stored) backend.state = stored;
    const session = backend.readSession();
    return session
      ? HttpResponse.json(session)
      : HttpResponse.json({ code: "unauthenticated", message: "Session absente.", request_id: null }, { status: 401 });
  };

  /** `situation` every 0.25 s, then `phase` once the mission ends — as `GET /v1/missions/{id}/events`. */
  const events: HttpResponseResolver = ({ params }) => {
    const missionId = String(params.missionId);
    const encoder = new TextEncoder();
    let timer: ReturnType<typeof setInterval> | undefined;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const push = () => {
          const stored = persistence?.load();
          if (stored) backend.state = stored;
          try {
            const mission = backend.readMission(missionId);
            controller.enqueue(encoder.encode(`event: situation\ndata: ${JSON.stringify(mission)}\n\n`));
            if (mission.phase === "ended") {
              controller.enqueue(encoder.encode(`event: phase\ndata: {"phase":"ended"}\n\n`));
              clearInterval(timer);
              controller.close();
            }
          } catch {
            clearInterval(timer);
            controller.error(new Error("mission indisponible"));
          }
        };
        push();
        timer = setInterval(push, 250);
      },
      cancel() {
        clearInterval(timer);
      },
    });
    return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } });
  };

  const b = backend;
  return [
    http.get("*/v1/session", sessionGet),
    http.post(
      "*/v1/session",
      handle(({ body }) => {
        const { username, password } = body as SignIn;
        return b.signIn(username, password);
      }),
    ),
    http.delete(
      "*/v1/session",
      handle(() => {
        b.signOut();
      }, 204),
    ),
    http.get("*/v1/scenarios", handle(() => b.listScenarios())),
    http.post("*/v1/missions", handle(({ body }) => b.startMission(body as StartMission), 201)),
    http.get("*/v1/missions/:missionId/events", events),
    http.get("*/v1/missions/:missionId", handle(({ params }) => b.readMission(params.missionId!))),
    http.delete(
      "*/v1/missions/:missionId",
      handle(({ params }) => {
        b.stopMission(params.missionId!);
      }, 204),
    ),
    http.post(
      "*/v1/missions/:missionId/orders",
      handle(({ params, body }) => b.submitOrder(params.missionId!, body as SubmitOrder)),
    ),
    http.post(
      "*/v1/missions/:missionId/simulations",
      handle(({ params, body }) => b.simulateOrder(params.missionId!, (body as { text: string }).text)),
    ),
    http.get("*/v1/missions/:missionId/recommendations", handle(({ params }) => b.listRecommendations(params.missionId!))),
    http.post("*/v1/missions/:missionId/helm", handle(({ params, body }) => b.setHelm(params.missionId!, body as SetHelm))),
    http.post(
      "*/v1/missions/:missionId/contacts/:contactId/classification",
      handle(({ params, body }) => {
        b.classifyContact(params.missionId!, params.contactId!, (body as { classification: Classification }).classification);
      }, 204),
    ),
    http.post(
      "*/v1/missions/:missionId/requests/:ship/reply",
      handle(({ params, body }) => {
        b.replyRequest(params.missionId!, params.ship!, (body as { approve: boolean }).approve);
      }, 204),
    ),
    http.put(
      "*/v1/missions/:missionId/autopilot",
      handle(({ params, body }) => {
        b.setAutopilot(params.missionId!, (body as { enabled: boolean }).enabled);
      }, 204),
    ),
    http.post(
      "*/v1/missions/:missionId/voice",
      handle(({ params, body }) => {
        const form = body as FormData;
        const audio = form.get("audio");
        const parentId = form.get("parent_id");
        return b.submitVoiceOrder(
          params.missionId!,
          audio instanceof Blob ? audio : new Blob(),
          typeof parentId === "string" ? parentId : undefined,
        );
      }),
    ),
    http.get(
      "*/v1/audit",
      handle(({ url }) => {
        const q = url.searchParams;
        return b.readAudit({
          missionId: q.get("mission_id") ?? undefined,
          afterSeq: Number(q.get("after_seq") ?? 0),
          limit: Number(q.get("limit") ?? 100),
        });
      }),
    ),
    http.get("*/v1/audit/integrity", handle(() => b.verifyAudit())),
    http.get("*/v1/audit/:commandId/audio", ({ params }) => {
      try {
        const recording = b.readRecording(String(params.commandId));
        return new HttpResponse(recording, { headers: { "Content-Type": recording.type || "audio/wav" } });
      } catch (e) {
        if (e instanceof FakeError) return errorBody(e);
        throw e;
      }
    }),
    http.get("*/v1/commands/:commandId", handle(({ params }) => b.readCommand(params.commandId!))),
    http.post("*/v1/commands/:commandId/explanation", handle(({ params }) => b.explainCommand(params.commandId!))),
    http.post("*/v1/doctrine/questions", handle(({ body }) => b.askDoctrine(body as DoctrineQuestion))),
    http.get("*/v1/doctrine/publications", handle(() => ({ publications: b.listPublications() }))),
    http.get("*/v1/glossary", handle(({ url }) => b.searchGlossary(url.searchParams.get("q") ?? ""))),
    http.get("*/v1/users", handle(() => ({ users: b.listUsers() }))),
    http.post("*/v1/users", handle(({ body }) => b.createUser(body as CreateUser), 201)),
    http.put("*/v1/users/:userId/role", handle(({ params, body }) => b.changeUserRole(params.userId!, (body as { role: string }).role))),
    http.post("*/v1/users/:userId/disable", handle(({ params }) => b.disableUser(params.userId!))),
    http.post("*/v1/users/:userId/enable", handle(({ params }) => b.enableUser(params.userId!))),
    http.post("*/v1/users/:userId/password-reset", handle(({ params }) => b.resetUserPassword(params.userId!))),
    http.get("*/v1/roles", handle(() => ({ roles: b.listRoles() }))),
    http.put(
      "*/v1/session/password",
      handle(({ body }) => {
        b.changeOwnPassword(body as ChangePassword);
      }, 204),
    ),
    http.post(
      "*/v1/commands/:commandId/decision",
      handle(({ params, body }) => b.decideCommand(params.commandId!, (body as { decision: CommandDecision }).decision)),
    ),
  ];
}
