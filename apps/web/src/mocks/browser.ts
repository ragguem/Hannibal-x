import { setupWorker } from "msw/browser";
import { createHandlers, localStoragePersistence } from "./handlers";

export const worker = setupWorker(...createHandlers(undefined, localStoragePersistence()));
