import { useEffect, useState } from "react";
import { Link, matchPath, Outlet, useLocation, useNavigate } from "react-router";
import { Icon, type IconName } from "../components/Icon";
import { hasPermission, useSession, useSignOut } from "../features/session/use-session";
import type { PermissionCode } from "../socle/ports";
import { UserMenu } from "./UserMenu";

interface NavEntry {
  to: string;
  /** Route pattern that keeps the entry highlighted, e.g. the console under "Missions". */
  section: string;
  label: string;
  icon: IconName;
  permission?: PermissionCode;
}

const NAV: NavEntry[] = [
  { to: "/", section: "/", label: "Tableau de bord", icon: "home" },
  { to: "/missions/nouvelle", section: "/missions/*", label: "Missions", icon: "target", permission: "mission:play" },
  { to: "/doctrine", section: "/doctrine/*", label: "Doctrine", icon: "book", permission: "doctrine:ask" },
  { to: "/registre", section: "/registre/*", label: "Registre", icon: "list", permission: "audit:read" },
];

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

export function Layout() {
  const { data: session } = useSession();
  const signOut = useSignOut();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const now = useClock();

  const leave = () => {
    signOut.mutate(undefined, { onSettled: () => void navigate("/login", { replace: true }) });
  };

  return (
    <div className="shell">
      <header className="top-bar">
        <Link to="/" className="brand">
          <Icon name="shield" size={26} />
          <span className="brand-text">
            <span>
              HANNIBAL <span>X</span>
            </span>
            <small>Simulation et commandement maritime</small>
          </span>
        </Link>
        <nav className="main-nav" aria-label="Navigation principale">
          {NAV.filter((entry) => !entry.permission || hasPermission(session, entry.permission)).map((entry) => {
            const active = matchPath(entry.section, pathname) !== null;
            return (
              <Link
                key={entry.to}
                to={entry.to}
                className={active ? "nav-link active" : "nav-link"}
                aria-current={active ? "page" : undefined}
              >
                <Icon name={entry.icon} size={16} />
                <span className="nav-label">{entry.label}</span>
              </Link>
            );
          })}
        </nav>
        <span className="grow" />
        <span className="top-status">
          <span className="chip">
            <span className="dot ok" /> <span className="hide-sm">Connecté</span>
          </span>
          <span className="top-clock hide-sm">
            <Icon name="clock" size={16} />
            <span>
              <b className="mono">{now.toLocaleTimeString("fr-FR")}</b>
              <small className="mut">{now.toLocaleDateString("fr-FR")}</small>
            </span>
          </span>
          {session && (
            <UserMenu username={session.username} role={session.role} signingOut={signOut.isPending} onSignOut={leave} />
          )}
        </span>
      </header>
      <Outlet />
    </div>
  );
}
