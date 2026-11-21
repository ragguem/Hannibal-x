import { FakeBackend, FakeError } from "../mocks/fake-backend";
import { ApiError } from "../services/api-error";
import type { ApiPort, StreamHandlers, StreamPort } from "../socle/ports";

/** ApiPort straight onto the fake backend: same answers as the MSW mocks, without HTTP. */
export function fakeApi(backend = new FakeBackend()): ApiPort {
  const run = <T>(action: () => T): Promise<T> => {
    try {
      return Promise.resolve(action());
    } catch (e) {
      if (e instanceof FakeError) return Promise.reject(new ApiError(e.status, e.code, e.message));
      return Promise.reject(e instanceof Error ? e : new Error(String(e)));
    }
  };
  return {
    readSession: () => run(() => backend.readSession()),
    signIn: ({ username, password }) => run(() => backend.signIn(username, password)),
    signOut: () => run(() => backend.signOut()),
    listScenarios: () => run(() => backend.listScenarios()),
    startMission: (body) => run(() => backend.startMission(body)),
    readMission: (id) => run(() => backend.readMission(id)),
    stopMission: (id) => run(() => backend.stopMission(id)),
    submitOrder: (id, body) => run(() => backend.submitOrder(id, body)),
    simulateOrder: (id, text) => run(() => backend.simulateOrder(id, text)),
    readCommand: (id) => run(() => backend.readCommand(id)),
    decideCommand: (id, decision) => run(() => backend.decideCommand(id, decision)),
    listRecommendations: (id) => run(() => backend.listRecommendations(id)),
    setHelm: (id, body) => run(() => backend.setHelm(id, body)),
    classifyContact: (id, contactId, classification) => run(() => backend.classifyContact(id, contactId, classification)),
    replyRequest: (id, ship, approve) => run(() => backend.replyRequest(id, ship, approve)),
    setAutopilot: (id, enabled) => run(() => backend.setAutopilot(id, enabled)),
    submitVoiceOrder: (id, recording, parentId) => run(() => backend.submitVoiceOrder(id, recording, parentId)),
    readAudit: (query) => run(() => backend.readAudit(query)),
    verifyAudit: () => run(() => backend.verifyAudit()),
    recordingUrl: (commandId) => `/v1/audit/${commandId}/audio`,
    askDoctrine: (body) => run(() => backend.askDoctrine(body)),
    listPublications: () => run(() => backend.listPublications()),
    searchGlossary: (query) => run(() => backend.searchGlossary(query)),
    explainCommand: (commandId) => run(() => backend.explainCommand(commandId)),
    listUsers: () => run(() => backend.listUsers()),
    listRoles: () => run(() => backend.listRoles()),
    createUser: (body) => run(() => backend.createUser(body)),
    changeUserRole: (userId, role) => run(() => backend.changeUserRole(userId, role)),
    disableUser: (userId) => run(() => backend.disableUser(userId)),
    enableUser: (userId) => run(() => backend.enableUser(userId)),
    resetUserPassword: (userId) => run(() => backend.resetUserPassword(userId)),
    changeOwnPassword: (body) => run(() => backend.changeOwnPassword(body)),
    listShipClasses: () => run(() => backend.listShipClasses()),
    createShipClass: (body) => run(() => backend.createShipClass(body)),
    listShips: () => run(() => backend.listShips()),
    createShip: (body) => run(() => backend.createShip(body)),
    changeShipClass: (shipId, classCode) => run(() => backend.changeShipClass(shipId, classCode)),
    retireShip: (shipId) => run(() => backend.retireShip(shipId)),
    reactivateShip: (shipId) => run(() => backend.reactivateShip(shipId)),
  };
}

/** StreamPort driven by the test: `push` delivers events to every subscriber. */
export class ManualStream implements StreamPort {
  readonly subscribers = new Map<string, StreamHandlers>();

  subscribe(missionId: string, handlers: StreamHandlers): () => void {
    this.subscribers.set(missionId, handlers);
    handlers.onStatus("live");
    return () => {
      this.subscribers.delete(missionId);
    };
  }

  push(missionId: string, ...events: Parameters<StreamHandlers["onEvent"]>) {
    for (const e of events) this.subscribers.get(missionId)?.onEvent(e);
  }
}
