import { ErrorPanel } from "../../components/ErrorPanel";
import { Icon } from "../../components/Icon";
import { describeError } from "../../services/api-error";

interface LaunchPanelProps {
  canStart: boolean;
  pending: boolean;
  error: unknown;
  onStart: () => void;
}

export function LaunchPanel({ canStart, pending, error, onStart }: LaunchPanelProps) {
  const failure = error === null || error === undefined ? null : describeError(error);
  return (
    <section className="planner-launch" aria-label="Lancement">
      <button type="button" className="btn launch-btn" disabled={!canStart || pending} onClick={onStart}>
        <Icon name="play" size={22} />
        <span>Démarrer la mission</span>
      </button>
      <button type="button" className="btn save-plan-btn" disabled title="Sauvegarde des plans : prochaine version">
        <Icon name="save" size={18} />
        <span className="grow">Sauvegarder le plan</span>
        <Icon name="chevron" size={16} />
      </button>
      <span role="status" className="mut launch-status">
        {pending ? "Démarrage : mise en place de la flotte dans le simulateur…" : ""}
      </span>
      {failure && <ErrorPanel message={failure.message} onRetry={failure.retryable ? onStart : undefined} />}
    </section>
  );
}
