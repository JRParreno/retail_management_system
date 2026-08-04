import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";

import { getBackendUrl } from "@/lib/api";
import { formatApiDetail, log } from "@/lib/logger";

const COOKIE = "rms_token";

export async function POST(req: NextRequest) {
  const requestId = randomUUID();
  let body: { username?: string; password?: string };
  try {
    body = await req.json();
  } catch (err) {
    log.warn("Login invalid JSON body", {
      requestId,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { detail: "Invalid request body", request_id: requestId },
      { status: 400, headers: { "X-Request-Id": requestId } },
    );
  }

  const form = new URLSearchParams();
  form.set("username", String(body.username ?? ""));
  form.set("password", String(body.password ?? ""));

  let res: Response;
  try {
    res = await fetch(`${getBackendUrl()}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Request-Id": requestId,
      },
      body: form.toString(),
    });
  } catch (err) {
    log.error("Login backend unreachable", {
      requestId,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { detail: "Backend unavailable", request_id: requestId },
      { status: 503, headers: { "X-Request-Id": requestId } },
    );
  }

  if (!res.ok) {
    let detail = "Login failed";
    const upstreamId =
      res.headers.get("x-request-id") ?? requestId;
    try {
      const data = await res.json();
      detail = formatApiDetail(data.detail, detail);
    } catch {
      /* ignore */
    }
    if (res.status >= 500) {
      log.error("Login failed", {
        status: res.status,
        detail,
        requestId: upstreamId,
      });
    } else {
      log.warn("Login rejected", {
        status: res.status,
        detail,
        requestId: upstreamId,
        username: String(body.username ?? ""),
      });
    }
    return NextResponse.json(
      { detail, request_id: upstreamId },
      { status: res.status, headers: { "X-Request-Id": upstreamId } },
    );
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
  response.headers.set("X-Request-Id", requestId);
  return response;
}
