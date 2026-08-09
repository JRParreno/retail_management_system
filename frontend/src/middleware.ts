import { NextRequest, NextResponse } from "next/server";

const PUBLIC = ["/login"];

/**
 * Redirect while keeping the browser-facing host.
 *
 * - Local `next dev --experimental-https` on :3000 → keep Host (incl. port).
 * - Cloudflare / Tailscale / Nginx on 443 → use X-Forwarded-Host and drop :3000.
 * Ignoring Host and blindly using X-Forwarded-Host without a port caused
 * https://127.0.0.1/login loops in local development.
 */
function redirectTo(req: NextRequest, pathname: string) {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const hostHeader = req.headers.get("host")?.split(",")[0]?.trim() || "";
  const forwardedHost = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const protoHeader = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();

  // Direct hit on Next's listen port (local HTTPS / LAN :3000) — never strip port.
  const directPort = hostHeader.match(/:(\d+)$/)?.[1];
  if (directPort && directPort !== "80" && directPort !== "443") {
    const proto = req.nextUrl.protocol.replace(":", "") || "https";
    return NextResponse.redirect(new URL(`${proto}://${hostHeader}${path}`));
  }

  const host = forwardedHost || hostHeader || req.nextUrl.host;
  const proto =
    protoHeader === "http" || protoHeader === "https"
      ? protoHeader
      : req.nextUrl.protocol.replace(":", "") || "https";

  return NextResponse.redirect(new URL(`${proto}://${host}${path}`));
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("rms_token")?.value;
  const isPublic = PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isApi = pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();

  // Protect app routes. Do not bounce /login → /dashboard on cookie presence
  // alone — an expired rms_token would loop (middleware ↔ layout).
  if (!token && !isPublic) {
    return redirectTo(req, "/login");
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
