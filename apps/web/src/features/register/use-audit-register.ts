import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import { queryKeys } from "../../socle/query-keys";

export const AUDIT_PAGE_SIZE = 200;

/** Pages follow `seq`: each one starts after the last event of the previous one. */
export function useAuditRegister(missionId: string) {
  const api = useApi();
  return useInfiniteQuery({
    queryKey: queryKeys.audit(missionId),
    queryFn: ({ pageParam }) => api.readAudit({ missionId, afterSeq: pageParam, limit: AUDIT_PAGE_SIZE }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_after_seq ?? undefined,
  });
}

export function useAuditIntegrity() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.auditIntegrity, queryFn: () => api.verifyAudit() });
}

export function useRecordingUrl(): (commandId: string) => string {
  const api = useApi();
  return (commandId) => api.recordingUrl(commandId);
}
