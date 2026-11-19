import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { hasPermission, useSession, useSignOut } from "../features/session/use-session";

export function Layout() {
  const { data: session } = useSession();
  const signOut = useSignOut();
  const navigate = useNavigate();

  const leave = () => {
    signOut.mutate(undefined, { onSettled: () => void navigate("/login", { replace: true }) });
  };

  return (
    <div className="shell">
      <header className="top-bar">
        <Link to="/" className="brand">
          HANNIBAL <span>X</span>
        </Link>
        <span className="grow" />
        {hasPermission(session, "doctrine:ask") && (
          <NavLink to="/doctrine" className="btn sm ghost">
            Doctrine
          </NavLink>
        )}
        {hasPermission(session, "audit:read") && (
          <NavLink to="/registre" className="btn sm ghost">
            Registre
          </NavLink>
        )}
        {session && (
          <span className="mut">
            {session.username} · {session.role}
          </span>
        )}
        <button type="button" className="btn sm ghost" disabled={signOut.isPending} onClick={leave}>
          Se déconnecter
        </button>
      </header>
      <Outlet />
    </div>
  );
}
