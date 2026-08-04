import { cookies } from "next/headers";

import { apiFetch } from "@/lib/api";
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
  } catch {
    return null;
  }
}
