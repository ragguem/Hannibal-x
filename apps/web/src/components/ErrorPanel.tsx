interface ErrorPanelProps {
  message: string;
  onRetry?: (() => void) | undefined;
}

export function ErrorPanel({ message, onRetry }: ErrorPanelProps) {
  return (
    <div className="error-panel" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn sm" onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  );
}
