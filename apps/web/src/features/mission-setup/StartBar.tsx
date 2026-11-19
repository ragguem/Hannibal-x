import { ErrorPanel } from "../../components/ErrorPanel";
import { describeError } from "../../services/api-error";

interface StartOptions {
  autopilot: boolean;
  manualHelm: boolean;
}

interface StartBarProps {
  options: StartOptions;
  onOptionsChange: (options: StartOptions) => void;
  canStart: boolean;
  pending: boolean;
  error: unknown;
  onStart: () => void;
}

export function StartBar({ options, onOptionsChange, canStart, pending, error, onStart }: StartBarProps) {
  return (
    <section className="card start-bar" aria-label="Lancement">
      <label className="check">
        <input
          type="checkbox"
          checked={options.autopilot}
          onChange={(e) => onOptionsChange({ ...options, autopilot: e.target.checked })}
        />
        Mode automatique (les ordres du guide sont exécutés sans vous)
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={options.manualHelm}
          onChange={(e) => onOptionsChange({ ...options, manualHelm: e.target.checked })}
        />
        Barre manuelle (vous tenez le cap et la vitesse)
      </label>
      {error !== null && error !== undefined && (
        <ErrorPanel message={describeError(error).message} onRetry={describeError(error).retryable ? onStart : undefined} />
      )}
      <div className="row">
        <button type="button" className="btn green" disabled={!canStart || pending} onClick={onStart}>
          Démarrer la mission
        </button>
        <span role="status" className="mut">
          {pending ? "Démarrage : mise en place de la flotte dans le simulateur…" : ""}
        </span>
      </div>
    </section>
  );
}
