import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { hasPermission, useSession } from "../features/session/use-session";
import { describeError } from "../services/api-error";
import type { PermissionCode } from "../socle/ports";

export interface LoginState {
  from?: string;
}

export function RequireSession() {
  const session = useSession();
  const location = useLocation();
  if (session.isPending) return <Loading label="Vérification de la session…" />;
  if (session.isError) {
    return <ErrorPanel message={describeError(session.error).message} onRetry={() => void session.refetch()} />;
  }
  if (!session.data) {
    const state: LoginState = { from: location.pathname + location.search };
    return <Navigate to="/login" replace state={state} />;
  }
  return <Outlet />;
}

export function RequirePermission({ permission, children }: { permission: PermissionCode; children: ReactNode }) {
  const { data } = useSession();
  if (!hasPermission(data, permission)) {
    return (
      <main className="page narrow">
        <h1>Accès refusé</h1>
        <p>Votre rôle ne donne pas accès à cet écran.</p>
      </main>
    );
  }
  return children;
}
