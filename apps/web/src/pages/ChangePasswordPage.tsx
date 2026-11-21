import { useId, useState, type SyntheticEvent } from "react";
import { useNavigate } from "react-router";
import { useChangeOwnPassword } from "../features/users/use-users";
import { describeError } from "../services/api-error";

const MIN_LENGTH = 12;

export function ChangePasswordPage() {
  const ids = { current: useId(), next: useId(), confirm: useId() };
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const change = useChangeOwnPassword();
  const navigate = useNavigate();
  const mismatch = confirm !== "" && confirm !== next;

  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mismatch) return;
    change.mutate(
      { current_password: current, new_password: next },
      { onSuccess: () => void navigate("/login", { replace: true }) },
    );
  };

  return (
    <main className="page narrow">
      <h1>Changer de mot de passe</h1>
      <p className="mut">Au moins {MIN_LENGTH} caractères. Vous vous reconnecterez ensuite avec le nouveau mot de passe.</p>
      <form className="card stack" onSubmit={submit}>
        <label htmlFor={ids.current} className="lbl">
          Mot de passe actuel
        </label>
        <input id={ids.current} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        <label htmlFor={ids.next} className="lbl">
          Nouveau mot de passe
        </label>
        <input
          id={ids.next}
          type="password"
          autoComplete="new-password"
          minLength={MIN_LENGTH}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
        <label htmlFor={ids.confirm} className="lbl">
          Confirmation
        </label>
        <input
          id={ids.confirm}
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          aria-invalid={mismatch}
          required
        />
        {mismatch && <small className="mut">Les deux saisies diffèrent.</small>}
        {change.isError && (
          <p className="chip warn" role="alert">
            {describeError(change.error).message}
          </p>
        )}
        <button type="submit" className="btn green" disabled={change.isPending || mismatch}>
          Changer le mot de passe
        </button>
      </form>
    </main>
  );
}
