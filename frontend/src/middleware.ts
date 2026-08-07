import { NextRequest, NextResponse } from "next/server";

const PUBLIC = ["/login"];

/**
 * Redirect while keeping the request host (LAN IP / localhost).
 * Avoid `new URL("/path")` without a base — that throws Invalid URL.
 * Prefer cloning nextUrl over a relative Location header (Next 15 can
 * mis-parse relative redirects when bound to 0.0.0.0 + HTTPS).
 */
function redirectTo(req: NextRequest, pathname: string) {
  const url = req.nextUrl.clone();
  url.pathname = pathname.startsWith("/") ? pathname : `/${pathname}`;
  url.search = "";
  return NextResponse.redirect(url);
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
