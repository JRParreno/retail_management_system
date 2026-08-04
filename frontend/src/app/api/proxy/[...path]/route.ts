import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { getBackendUrl } from "@/lib/api";

type Params = { params: Promise<{ path: string[] }> };

async function proxy(req: NextRequest, { params }: Params) {
  const { path } = await params;
  const token = (await cookies()).get("rms_token")?.value;
  const url = new URL(req.url);
  const target = `${getBackendUrl()}/api/v1/${path.join("/")}${url.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const branchId = (await cookies()).get("rms_branch_id")?.value;
  if (branchId) headers.set("X-Branch-Id", branchId);

  const init: RequestInit = {
    method: req.method,
    headers,
    duplex: "half",
  } as RequestInit;

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const res = await fetch(target, init);
  const body = await res.arrayBuffer();
  return new NextResponse(body, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
