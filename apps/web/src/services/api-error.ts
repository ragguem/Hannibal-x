/** A failed API call, carrying the server's `ErrorBody` when there is one. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly dependency: string | null;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, dependency: string | null = null, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.dependency = dependency;
    this.requestId = requestId;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

interface ErrorBodyLike {
  code?: unknown;
  message?: unknown;
  dependency?: unknown;
  request_id?: unknown;
}

const text = (value: unknown): string | null => (typeof value === "string" && value !== "" ? value : null);

export function toApiError(status: number, body: unknown): ApiError {
  const b = (typeof body === "object" && body !== null ? body : {}) as ErrorBodyLike;
  return new ApiError(
    status,
    text(b.code) ?? `http_${status}`,
    text(b.message) ?? `Erreur ${status}`,
    text(b.dependency),
    text(b.request_id),
  );
}

export const networkError = (cause: unknown): ApiError =>
  new ApiError(0, "network", cause instanceof Error ? cause.message : "Serveur injoignable");

export interface ErrorView {
  message: string;
  retryable: boolean;
}

/** What the operator reads. 401 is handled globally (back to sign-in), never shown here. */
export function describeError(error: unknown): ErrorView {
  if (!isApiError(error)) return { message: "Erreur inattendue.", retryable: true };
  if (error.status === 0) return { message: "Serveur injoignable : vérifier la connexion.", retryable: true };
  if (error.status === 403) return { message: "Action non autorisée pour votre rôle.", retryable: false };
  if (error.status === 404) return { message: "Introuvable : la mission est peut-être terminée.", retryable: false };
  if (error.status === 503) {
    const what = error.dependency ? ` (${error.dependency})` : "";
    return { message: `Service indisponible${what}. ${error.message}`, retryable: true };
  }
  return { message: error.message, retryable: error.status >= 500 || error.status === 429 };
}
