import { formatApiDetail, log } from "@/lib/logger";

const BACKEND =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://127.0.0.1:8000";

export function getBackendUrl() {
  return BACKEND.replace(/\/$/, "");
}

export class ApiError extends Error {
  status: number;
  requestId?: string;

  constructor(status: number, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

type FetchOptions = RequestInit & { token?: string | null };

export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { token, headers, ...rest } = options;
  let res: Response;
  try {
    res = await fetch(`${getBackendUrl()}${path}`, {
      ...rest,
      headers: {
        ...(rest.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      cache: "no-store",
    });
  } catch (err) {
    log.error("Server API network failure", {
      path,
      method: rest.method ?? "GET",
      error: err instanceof Error ? err.message : String(err),
    });
    throw new ApiError(0, "Backend unavailable");
  }

  const requestId =
    res.headers.get("x-request-id") ?? res.headers.get("X-Request-Id") ?? undefined;

  if (!res.ok) {
    let detail = res.statusText;
    let bodyRequestId = requestId;
    try {
      const data = await res.json();
      detail = formatApiDetail(data.detail ?? data, res.statusText);
      if (!bodyRequestId && typeof data.request_id === "string") {
        bodyRequestId = data.request_id;
      }
    } catch {
      /* ignore */
    }
    if (res.status >= 500 || (res.status !== 401 && res.status !== 404)) {
      log.error("Server API request failed", {
        path,
        method: rest.method ?? "GET",
        status: res.status,
        detail,
        requestId: bodyRequestId,
      });
    }
    throw new ApiError(res.status, detail, bodyRequestId);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
