export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <p className="loading" role="status">
      {label}
    </p>
  );
}
