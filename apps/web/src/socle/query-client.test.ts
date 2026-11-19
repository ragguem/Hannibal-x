import { describe, expect, it } from "vitest";
import { ApiError } from "../services/api-error";
import { createQueryClient, shouldRetry } from "./query-client";
import { queryKeys } from "./query-keys";

describe("query layer", () => {
  it("retries incidents, never answers", () => {
    expect(shouldRetry(0, new ApiError(503, "dependency_unavailable", "x"))).toBe(true);
    expect(shouldRetry(0, new ApiError(0, "network", "x"))).toBe(true);
    expect(shouldRetry(2, new ApiError(503, "x", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(404, "not_found", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(409, "conflict", "x"))).toBe(false);
  });

  it("drops the session on any 401 and keeps the rest of the cache", async () => {
    const client = createQueryClient();
    client.setQueryData(queryKeys.session, { username: "u", role: "r", permissions: [], expires_at: "" });
    client.setQueryData(queryKeys.mission("m-1"), { id: "m-1" });
    await client
      .query({ queryKey: ["probe"], queryFn: () => Promise.reject(new ApiError(401, "unauthenticated", "x")) })
      .catch(() => undefined);
    expect(client.getQueryData(queryKeys.session)).toBeNull();
    expect(client.getQueryData(queryKeys.mission("m-1"))).toEqual({ id: "m-1" });
  });
});
