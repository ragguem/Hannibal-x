import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import { queryKeys } from "../../socle/query-keys";

export function useCatalogScenarios() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.catalogScenarios, queryFn: () => api.listCatalogScenarios() });
}

export type ScenarioAction =
  | { kind: "import"; yaml: string }
  | { kind: "publish"; id: string; version: number }
  | { kind: "archive"; id: string };

export function useScenarioAction() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: ScenarioAction): Promise<unknown> => {
      switch (action.kind) {
        case "import":
          return api.importScenario(action.yaml);
        case "publish":
          return api.publishScenario(action.id, action.version);
        case "archive":
          return api.archiveScenario(action.id);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.catalogScenarios }),
  });
}
