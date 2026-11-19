import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { PermissionCode, SessionView, SignIn } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useSession() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.session, queryFn: () => api.readSession(), staleTime: 60_000 });
}

export const hasPermission = (session: SessionView | null | undefined, permission: PermissionCode): boolean =>
  session?.permissions.includes(permission) ?? false;

/** True when the signed-in user holds `permission`; screens hide what the server would refuse anyway. */
export function usePermission(permission: PermissionCode): boolean {
  return hasPermission(useSession().data, permission);
}

export function useSignIn() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SignIn) => api.signIn(body),
    onSuccess: (session) => queryClient.setQueryData(queryKeys.session, session),
  });
}

export function useSignOut() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.signOut(),
    onSettled: () => {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== queryKeys.session[0] });
      queryClient.setQueryData(queryKeys.session, null);
    },
  });
}
