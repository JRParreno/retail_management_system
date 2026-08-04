"use client";

import { toast } from "sonner";

import { formatApiDetail, log } from "@/lib/logger";

export class ClientApiError extends Error {
  status: number;
  requestId?: string;

  constructor(status: number, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

export async function clientApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/proxy${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...options.headers,
      },
    });
  } catch (err) {
    log.error("API network failure", {
      path,
      method: options.method ?? "GET",
      error: err instanceof Error ? err.message : String(err),
    });
    throw new ClientApiError(0, "Network error — check your connection");
  }

  const requestId =
    res.headers.get("x-request-id") ?? res.headers.get("X-Request-Id") ?? undefined;

  if (!res.ok) {
    let detail = res.statusText;
    let resolvedRequestId = requestId;
    try {
      const data = await res.json();
      detail = formatApiDetail(data.detail ?? data, res.statusText);
      if (!resolvedRequestId && typeof data.request_id === "string") {
        resolvedRequestId = data.request_id;
      }
    } catch {
      /* ignore */
    }

    log.error("API request failed", {
      path,
      method: options.method ?? "GET",
      status: res.status,
      detail,
      requestId: resolvedRequestId,
    });
    throw new ClientApiError(res.status, detail, resolvedRequestId);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function toastError(err: unknown) {
  if (err instanceof ClientApiError) {
    const suffix = err.requestId ? ` (ref: ${err.requestId.slice(0, 8)})` : "";
    toast.error(`${err.message}${suffix}`);
    return;
  }
  const message = err instanceof Error ? err.message : "Something went wrong";
  log.error("UI toast error", { detail: message });
  toast.error(message);
}
