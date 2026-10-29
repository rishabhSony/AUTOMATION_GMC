"use server";

import { cookies } from "next/headers";

import { DEV_MOCK_AUTH, DEV_ROLE_COOKIE, isDevRole } from "@/lib/dev-mode";

/** Dev Role Switcher: picks which seeded user the mock session acts as. */
export async function setDevRole(role: string) {
  if (!DEV_MOCK_AUTH) throw new Error("Dev mock auth is disabled");
  if (!isDevRole(role)) throw new Error(`Unknown role: ${role}`);
  (await cookies()).set(DEV_ROLE_COOKIE, role, {
    path: "/",
    sameSite: "lax",
    httpOnly: true,
  });
}
