/** Local wall-clock time of an ISO instant, to the second. */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString("fr-FR", { hour12: false });
}
