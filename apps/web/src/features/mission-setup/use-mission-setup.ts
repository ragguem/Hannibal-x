import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { StartMission } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useScenarios() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.scenarios, queryFn: () => api.listScenarios(), staleTime: 5 * 60_000 });
}

/** The 201 already carries the first situation: seed the cache so the console renders without a round trip. */
export function useStartMission() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StartMission) => api.startMission(body),
    onSuccess: (mission) => queryClient.setQueryData(queryKeys.mission(mission.id), mission),
  });
}
