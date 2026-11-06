import { NextResponse, type NextRequest } from "next/server";

/**
 * Coarse, fast redirect for signed-out visitors before dashboard pages render.
 * This only checks that a session cookie is present — it does NOT authorise anything.
 * Django validates the session and enforces roles on every API request.
 */
export function proxy(request: NextRequest) {
  if (!request.cookies.has("sessionid")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
