import { NextRequest, NextResponse } from "next/server";

const PUBLIC = ["/login"];

/**
 * nextUrl.host is the bind address (127.0.0.1:3000) behind Nginx.
 * Use forwarded Host / Proto so redirects stay on the LAN/public URL.
 */
function externalOrigin(req: NextRequest): string {
  const proto =
    req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
    req.nextUrl.protocol.replace(":", "") ||
    "http";
  const host =
    req.headers.get("x-forwarded-host")?.split(",")[0]?.trim() ||
    req.headers.get("host") ||
    req.nextUrl.host;
  return `${proto}://${host}`;
}

function redirectPath(req: NextRequest, pathname: string) {
  return NextResponse.redirect(new URL(pathname, externalOrigin(req)));
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("rms_token")?.value;
  const isPublic = PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isApi = pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();

  if (!token && !isPublic && pathname !== "/") {
    return redirectPath(req, "/login");
  }

  if (token && (pathname === "/login" || pathname === "/")) {
    return redirectPath(req, "/dashboard");
  }

  if (!token && pathname === "/") {
    return redirectPath(req, "/login");
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
