import { useId, useState, type SyntheticEvent } from "react";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { useSession } from "../features/session/use-session";
import { useRoles, useUserAction, useUsers } from "../features/users/use-users";
import { describeError } from "../services/api-error";
import type { IssuedPassword, RoleView, UserView } from "../socle/ports";

function TemporaryPasswordNotice({ issued, onDismiss }: { issued: IssuedPassword; onDismiss: () => void }) {
  return (
    <div className="card row wrap" role="status">
      <p className="grow">
        Mot de passe provisoire de <b>{issued.user.username}</b> : <code className="mono">{issued.temporary_password}</code>
        <br />
        <small className="mut">Affiché une seule fois. L'utilisateur le remplacera après sa première connexion.</small>
      </p>
      <button type="button" className="btn sm ghost" onClick={onDismiss}>
        J'ai transmis le mot de passe
      </button>
    </div>
  );
}

function NewUserForm({ roles, onCreate, busy }: { roles: RoleView[]; onCreate: (username: string, role: string) => void; busy: boolean }) {
  const ids = { username: useId(), role: useId() };
  const [username, setUsername] = useState("");
  const [role, setRole] = useState(roles[0]?.code ?? "");
  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    onCreate(username.trim(), role);
    setUsername("");
  };
  return (
    <form className="card row wrap" aria-label="Nouveau compte" onSubmit={submit}>
      <label htmlFor={ids.username} className="lbl">
        Identifiant
      </label>
      <input
        id={ids.username}
        className="mono"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        pattern="[a-z0-9._\-]{3,32}"
        title="3 à 32 caractères : minuscules, chiffres, point, tiret ou souligné"
        required
      />
      <label htmlFor={ids.role} className="lbl">
        Rôle
      </label>
      <select id={ids.role} value={role} onChange={(e) => setRole(e.target.value)}>
        {roles.map((r) => (
          <option key={r.code} value={r.code}>
            {r.label}
          </option>
        ))}
      </select>
      <button type="submit" className="btn green" disabled={busy}>
        Créer le compte
      </button>
    </form>
  );
}

interface UserRowProps {
  user: UserView;
  roles: RoleView[];
  isSelf: boolean;
  busy: boolean;
  onAction: ReturnType<typeof useUserAction>["mutate"];
}

function UserRow({ user, roles, isSelf, busy, onAction }: UserRowProps) {
  const disabled = user.disabled_at !== null;
  return (
    <tr>
      <td className="mono">
        {user.username}
        {isSelf && <small className="mut block">vous</small>}
      </td>
      <td>
        <select
          aria-label={`Rôle de ${user.username}`}
          value={user.role}
          disabled={isSelf || busy}
          onChange={(e) => onAction({ kind: "role", userId: user.id, role: e.target.value })}
        >
          {roles.map((r) => (
            <option key={r.code} value={r.code}>
              {r.label}
            </option>
          ))}
        </select>
      </td>
      <td>{disabled ? <span className="chip warn">Désactivé</span> : <span className="chip">Actif</span>}</td>
      <td>{user.password_changed_at === null ? "Provisoire" : "Personnel"}</td>
      <td className="row">
        {disabled ? (
          <button type="button" className="btn sm" disabled={busy} onClick={() => onAction({ kind: "enable", userId: user.id })}>
            Réactiver
          </button>
        ) : (
          <button
            type="button"
            className="btn sm"
            disabled={isSelf || busy}
            onClick={() => onAction({ kind: "disable", userId: user.id })}
          >
            Désactiver
          </button>
        )}
        <button type="button" className="btn sm ghost" disabled={busy} onClick={() => onAction({ kind: "reset", userId: user.id })}>
          Réinitialiser le mot de passe
        </button>
      </td>
    </tr>
  );
}

/** Accounts of the back-office (`user:manage`). Temporary passwords are shown once, then only their state. */
export function UsersPage() {
  const users = useUsers();
  const roles = useRoles();
  const { data: session } = useSession();
  const action = useUserAction();
  const [issued, setIssued] = useState<IssuedPassword | null>(null);

  const run: UserRowProps["onAction"] = (next) =>
    action.mutate(next, {
      onSuccess: (result) => setIssued("temporary_password" in result ? result : null),
    });

  if (users.isPending || roles.isPending) return <Loading label="Chargement des comptes…" />;
  if (users.isError || roles.isError) {
    return <ErrorPanel message={describeError(users.error ?? roles.error).message} onRetry={() => void users.refetch()} />;
  }

  return (
    <main className="page">
      <h1>Utilisateurs</h1>
      <p className="mut">
        Un compte désactivé ne peut plus se connecter et ses sessions sont coupées. Vous ne pouvez ni vous désactiver ni
        changer votre propre rôle.
      </p>
      {issued && <TemporaryPasswordNotice issued={issued} onDismiss={() => setIssued(null)} />}
      {action.isError && (
        <p className="chip warn" role="alert">
          {describeError(action.error).message}
        </p>
      )}
      <NewUserForm roles={roles.data} busy={action.isPending} onCreate={(username, role) => run({ kind: "create", body: { username, role } })} />
      <table className="table">
        <caption className="visually-hidden">Comptes</caption>
        <thead>
          <tr>
            <th scope="col">Identifiant</th>
            <th scope="col">Rôle</th>
            <th scope="col">État</th>
            <th scope="col">Mot de passe</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.data.map((user) => (
            <UserRow
              key={user.id}
              user={user}
              roles={roles.data}
              isSelf={user.username === session?.username}
              busy={action.isPending}
              onAction={run}
            />
          ))}
        </tbody>
      </table>
    </main>
  );
}
