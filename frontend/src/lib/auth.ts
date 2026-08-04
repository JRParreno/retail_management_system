import { cookies } from "next/headers";

import { ApiError, apiFetch } from "@/lib/api";
import { log } from "@/lib/logger";
import type { User } from "@/lib/types";

export const AUTH_COOKIE = "rms_token";

export async function getToken() {
  return (await cookies()).get(AUTH_COOKIE)?.value ?? null;
}

export async function getSessionUser(): Promise<User | null> {
  const token = await getToken();
  if (!token) return null;
  try {
    return await apiFetch<User>("/api/v1/auth/me", { token });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      return null;
    }
    log.error("Session lookup failed", {
      status: err instanceof ApiError ? err.status : undefined,
      detail: err instanceof Error ? err.message : String(err),
      requestId: err instanceof ApiError ? err.requestId : undefined,
    });
    return null;
  }
}
