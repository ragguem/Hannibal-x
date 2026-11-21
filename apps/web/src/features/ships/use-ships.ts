import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { CreateShip, ShipClass } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useShipClasses() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.shipClasses, queryFn: () => api.listShipClasses() });
}

export function useShips() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.ships, queryFn: () => api.listShips() });
}

export type ShipAction =
  | { kind: "create-class"; body: ShipClass }
  | { kind: "create"; body: CreateShip }
  | { kind: "class"; shipId: string; classCode: string }
  | { kind: "retire"; shipId: string }
  | { kind: "reactivate"; shipId: string };

/** One mutation for every catalog action: classes and ships are re-read after each, whatever the outcome. */
export function useShipAction() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: ShipAction): Promise<unknown> => {
      switch (action.kind) {
        case "create-class":
          return api.createShipClass(action.body);
        case "create":
          return api.createShip(action.body);
        case "class":
          return api.changeShipClass(action.shipId, action.classCode);
        case "retire":
          return api.retireShip(action.shipId);
        case "reactivate":
          return api.reactivateShip(action.shipId);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  });
}
