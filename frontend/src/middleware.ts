import { NextRequest, NextResponse } from "next/server";

const PUBLIC = ["/login"];

/**
 * Redirect while keeping the public request host (LAN IP, localhost,
 * Cloudflare / Tailscale hostname). Next bound to 127.0.0.1 often fills
 * nextUrl with localhost:3000 even when Host / X-Forwarded-* say otherwise.
 */
function redirectTo(req: NextRequest, pathname: string) {
  const forwardedHost = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const hostHeader = req.headers.get("host")?.split(",")[0]?.trim();
  const host = forwardedHost || hostHeader || req.nextUrl.host;

  const protoHeader = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const proto =
    protoHeader === "http" || protoHeader === "https"
      ? protoHeader
      : req.nextUrl.protocol.replace(":", "") || "http";

  // Build from scratch so origin port (:3000) never leaks into Location.
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return NextResponse.redirect(new URL(`${proto}://${host}${path}`));
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("rms_token")?.value;
  const isPublic = PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isApi = pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();

  if (!token && !isPublic && pathname !== "/") {
    return redirectTo(req, "/login");
  }

  if (token && (pathname === "/login" || pathname === "/")) {
    return redirectTo(req, "/dashboard");
  }

  if (!token && pathname === "/") {
    return redirectTo(req, "/login");
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
