import { NextRequest, NextResponse } from "next/server";

import { getBackendUrl } from "@/lib/api";

const COOKIE = "rms_token";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const form = new URLSearchParams();
  form.set("username", String(body.username ?? ""));
  form.set("password", String(body.password ?? ""));

  const res = await fetch(`${getBackendUrl()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });

  if (!res.ok) {
    let detail = "Login failed";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : detail;
    } catch {
      /* ignore */
    }
    return NextResponse.json({ detail }, { status: res.status });
  }

  const token = (await res.json()) as { access_token: string };
  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE, token.access_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 8,
  });
  return response;
}
