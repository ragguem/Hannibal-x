import { Navigate, useLocation, useNavigate } from "react-router";
import type { LoginState } from "../app/guards";
import { LoginForm } from "../features/session/LoginForm";
import { useSession } from "../features/session/use-session";

/** Only same-app paths are honoured, so a crafted `from` cannot send the user off-site. */
const safeTarget = (from: string | undefined) => (from?.startsWith("/") && !from.startsWith("//") ? from : "/");

export function LoginPage() {
  const { data: session } = useSession();
  const navigate = useNavigate();
  const target = safeTarget((useLocation().state as LoginState | null)?.from);

  if (session) return <Navigate to={target} replace />;
  return (
    <main className="page narrow login-page">
      <p className="brand">
        HANNIBAL <span>X</span>
      </p>
      <LoginForm onSignedIn={() => void navigate(target, { replace: true })} />
    </main>
  );
}
