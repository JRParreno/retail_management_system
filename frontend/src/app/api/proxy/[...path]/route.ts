import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";

import { getBackendUrl } from "@/lib/api";
import { log } from "@/lib/logger";

type Params = { params: Promise<{ path: string[] }> };

async function proxy(req: NextRequest, { params }: Params) {
  const { path } = await params;
  const token = (await cookies()).get("rms_token")?.value;
  const url = new URL(req.url);
  const apiPath = path.join("/");
  const target = `${getBackendUrl()}/api/v1/${apiPath}${url.search}`;
  const requestId =
    req.headers.get("x-request-id")?.trim() || randomUUID();

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const branchId = (await cookies()).get("rms_branch_id")?.value;
  if (branchId) headers.set("X-Branch-Id", branchId);
  headers.set("X-Request-Id", requestId);

  const init: RequestInit = {
    method: req.method,
    headers,
    duplex: "half",
  } as RequestInit;

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  let res: Response;
  try {
    res = await fetch(target, init);
  } catch (err) {
    log.error("Proxy backend unreachable", {
      path: apiPath,
      method: req.method,
      requestId,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      {
        detail: "Backend unavailable. Please try again.",
        request_id: requestId,
      },
      {
        status: 503,
        headers: { "X-Request-Id": requestId },
      },
    );
  }

  const body = await res.arrayBuffer();
  const upstreamId = res.headers.get("x-request-id") ?? requestId;

  if (res.status >= 500) {
    log.error("Proxy upstream error", {
      path: apiPath,
      method: req.method,
      status: res.status,
      requestId: upstreamId,
    });
  } else if (res.status >= 400 && res.status !== 401 && res.status !== 404) {
    log.warn("Proxy upstream client error", {
      path: apiPath,
      method: req.method,
      status: res.status,
      requestId: upstreamId,
    });
  }

  return new NextResponse(body, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
      "X-Request-Id": upstreamId,
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
