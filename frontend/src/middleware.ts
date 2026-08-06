import { NextRequest, NextResponse } from "next/server";

const PUBLIC = ["/login"];

/**
 * Use a relative Location so the browser stays on whatever host the user
 * opened (LAN IP / public IP via Nginx). Absolute redirects from nextUrl
 * incorrectly become https://localhost:3000 behind a reverse proxy.
 */
function redirectPath(pathname: string) {
  return new NextResponse(null, {
    status: 307,
    headers: {
      Location: pathname.startsWith("/") ? pathname : `/${pathname}`,
    },
  });
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("rms_token")?.value;
  const isPublic = PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isApi = pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();

  if (!token && !isPublic && pathname !== "/") {
    return redirectPath("/login");
  }

  if (token && (pathname === "/login" || pathname === "/")) {
    return redirectPath("/dashboard");
  }

  if (!token && pathname === "/") {
    return redirectPath("/login");
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
