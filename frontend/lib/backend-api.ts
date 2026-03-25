import "server-only";

const DEFAULT_BACKEND_API_BASE = "http://127.0.0.1:8000";
const BACKEND_TIMEOUT_MS = 30_000;

export class BackendRequestError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status: number, detail: string) {
    super(message);
    this.name = "BackendRequestError";
    this.status = status;
    this.detail = detail;
  }
}

function getBackendApiBaseUrl(): string {
  const configured = process.env.BACKEND_API_BASE_URL ?? DEFAULT_BACKEND_API_BASE;
  const normalized = configured.endsWith("/") ? configured.slice(0, -1) : configured;

  try {
    const parsed = new URL(normalized);
    return parsed.toString().replace(/\/$/, "");
  } catch {
    throw new Error(
      "Invalid BACKEND_API_BASE_URL value. Expected a full URL like http://127.0.0.1:8000."
    );
  }
}

async function tryJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function callBackend(
  path: string,
  init?: RequestInit & { timeoutMs?: number }
): Promise<unknown> {
  const baseUrl = getBackendApiBaseUrl();
  const url = `${baseUrl}${path}`;

  const controller = new AbortController();
  const timeoutMs = init?.timeoutMs ?? BACKEND_TIMEOUT_MS;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });

    const payload = await tryJson(response);

    if (!response.ok) {
      const detail =
        payload &&
        typeof payload === "object" &&
        "detail" in payload &&
        typeof (payload as { detail?: unknown }).detail === "string"
          ? ((payload as { detail: string }).detail ?? "Backend request failed.")
          : `Backend request failed with status ${response.status}.`;

      throw new BackendRequestError(detail, response.status, detail);
    }

    return payload;
  } catch (error) {
    if (error instanceof BackendRequestError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      throw new BackendRequestError(
        "Backend request timed out. Verify the API is running and reachable.",
        504,
        "timeout"
      );
    }

    throw new BackendRequestError(
      "Unable to reach backend API. Verify BACKEND_API_BASE_URL and backend server status.",
      502,
      error instanceof Error ? error.message : "unknown_error"
    );
  } finally {
    clearTimeout(timeout);
  }
}
