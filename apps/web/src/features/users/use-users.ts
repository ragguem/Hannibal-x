import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { ChangePassword, CreateUser } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useUsers() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.users, queryFn: () => api.listUsers() });
}

export function useRoles() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.roles, queryFn: () => api.listRoles(), staleTime: 5 * 60_000 });
}

export type UserAction =
  | { kind: "create"; body: CreateUser }
  | { kind: "role"; userId: string; role: string }
  | { kind: "disable"; userId: string }
  | { kind: "enable"; userId: string }
  | { kind: "reset"; userId: string };

/** One mutation for every account action: the list is re-read after each, whatever the outcome. */
export function useUserAction() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: UserAction) => {
      switch (action.kind) {
        case "create":
          return api.createUser(action.body);
        case "role":
          return { user: await api.changeUserRole(action.userId, action.role) };
        case "disable":
          return { user: await api.disableUser(action.userId) };
        case "enable":
          return { user: await api.enableUser(action.userId) };
        case "reset":
          return api.resetUserPassword(action.userId);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
  });
}

/** The server revokes every session on success: the user must sign in again. */
export function useChangeOwnPassword() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ChangePassword) => api.changeOwnPassword(body),
    onSuccess: () => {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== queryKeys.session[0] });
      queryClient.setQueryData(queryKeys.session, null);
    },
  });
}
