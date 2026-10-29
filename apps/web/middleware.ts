import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest } from "next/server";

import { DEV_MOCK_AUTH } from "@/lib/dev-mode";

// First line of defence only: pages under app/(app)/ re-check the session in their layout.
const PROTECTED_PREFIXES = [
  "/dashboard",
  "/cases",
  "/admin",
  "/settings",
  "/onboarding",
];
const SIGN_UP_PREFIXES = ["/signup", "/sign-up", "/register"];

const matchesPrefix = (req: NextRequest, prefixes: string[]) =>
  prefixes.some(
    (p) =>
      req.nextUrl.pathname === p || req.nextUrl.pathname.startsWith(`${p}/`),
  );

// Dev mock mode (lib/dev-mode.ts): no Clerk calls; every visitor is the mock user.
function devMockMiddleware(req: NextRequest) {
  if (req.nextUrl.pathname === "/" || matchesPrefix(req, ["/login"])) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }
  if (matchesPrefix(req, SIGN_UP_PREFIXES)) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }
  return NextResponse.next();
}

export default DEV_MOCK_AUTH
  ? devMockMiddleware
  : clerkMiddleware(async (auth, req) => {
      // Registration is invite-only (App Flow §10): send direct sign-up attempts to /login.
      if (matchesPrefix(req, SIGN_UP_PREFIXES)) {
        return NextResponse.redirect(
          new URL("/login?notice=invite-only", req.url),
        );
      }

      const { userId } = await auth();

      if (req.nextUrl.pathname === "/") {
        return NextResponse.redirect(
          new URL(userId ? "/dashboard" : "/login", req.url),
        );
      }

      if (!userId && matchesPrefix(req, PROTECTED_PREFIXES)) {
        const loginUrl = new URL("/login", req.url);
        loginUrl.searchParams.set(
          "redirect",
          req.nextUrl.pathname + req.nextUrl.search,
        );
        return NextResponse.redirect(loginUrl);
      }
    });

export const config = {
  matcher: [
    // Skip Next.js internals and static files, unless found in search params
    // (api/health is the container probe: no auth.)
    "/((?!_next|api/health|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api(?!/health)|trpc)(.*)",
  ],
};
