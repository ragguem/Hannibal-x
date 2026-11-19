import { useId, useState, type SyntheticEvent } from "react";
import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError, isApiError } from "../../services/api-error";
import { useSignIn } from "./use-session";

export function LoginForm({ onSignedIn }: { onSignedIn: () => void }) {
  const signIn = useSignIn();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const userId = useId();
  const passwordId = useId();

  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    signIn.mutate({ username: username.trim(), password }, { onSuccess: onSignedIn });
  };

  const error = signIn.error
    ? isApiError(signIn.error) && signIn.error.status === 401
      ? "Identifiant ou mot de passe incorrect."
      : describeError(signIn.error).message
    : null;

  return (
    <form className="card login" onSubmit={submit} aria-labelledby={`${userId}-title`}>
      <h1 id={`${userId}-title`}>Connexion</h1>
      <label htmlFor={userId}>Identifiant</label>
      <input
        id={userId}
        name="username"
        autoComplete="username"
        required
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <label htmlFor={passwordId}>Mot de passe</label>
      <input
        id={passwordId}
        name="password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error && <ErrorPanel message={error} />}
      <button type="submit" className="btn green" disabled={signIn.isPending}>
        {signIn.isPending ? "Connexion…" : "Se connecter"}
      </button>
    </form>
  );
}
