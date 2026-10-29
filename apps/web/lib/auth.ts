import "server-only";

import { auth } from "@clerk/nextjs/server";
import { and, asc, desc, eq, sql } from "drizzle-orm";
import { cookies } from "next/headers";
import { cache } from "react";

import { withRlsContext, withSystemContext, type Tx } from "@/db";
import { users } from "@/db/schema";
import { DEV_MOCK_AUTH, DEV_ROLE_COOKIE, isDevRole } from "@/lib/dev-mode";

export type CurrentUser = typeof users.$inferSelect;

/**
 * Resolves the Clerk session to the internal `users` row, or null when signed out,
 * not yet synced by the webhook, or deactivated. Cached per request.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  if (DEV_MOCK_AUTH) return getDevMockUser();
  const { userId: clerkUserId } = await auth();
  if (!clerkUserId) return null;

  // RLS lets a session read its own row by Clerk id (users_select_policy).
  const [user] = await withRlsContext({ clerkUserId }, (tx) =>
    tx.select().from(users).where(eq(users.clerkUserId, clerkUserId)).limit(1),
  );
  return user?.isActive ? user : null;
});

/**
 * Returns a runner that executes queries in a transaction scoped to the current
 * user, with `app.current_user_id` / `app.current_user_role` set for RLS.
 * Throws when there is no active, synced user.
 */
export async function getAuthenticatedDb() {
  const user = await getCurrentUser();
  if (!user)
    throw new Error(
      "Unauthenticated: no active QuotePulse user for this session",
    );

  return <T>(fn: (tx: Tx) => Promise<T>) =>
    withRlsContext(
      { userId: user.id, role: user.role, clerkUserId: user.clerkUserId },
      fn,
    );
}

/** For pages/actions restricted by role (e.g. `/admin/*` → "admin"). Throws on mismatch. */
export async function requireRole(...roles: CurrentUser["role"][]) {
  const user = await getCurrentUser();
  if (!user || !roles.includes(user.role)) throw new Error("Forbidden");
  return user;
}

/** True when a session exists (always, in dev mock mode). */
export async function isSignedIn(): Promise<boolean> {
  if (DEV_MOCK_AUTH) return true;
  return !!(await auth()).userId;
}

/**
 * Dev mock mode only: the active seeded user for the role chosen in the Dev Role
 * Switcher (cookie), defaulting to admin. Placeholder `seed_*` accounts are preferred.
 */
async function getDevMockUser(): Promise<CurrentUser | null> {
  if (!DEV_MOCK_AUTH) return null;
  const chosen = (await cookies()).get(DEV_ROLE_COOKIE)?.value;
  const role = isDevRole(chosen) ? chosen : "admin";
  const [user] = await withSystemContext((tx) =>
    tx
      .select()
      .from(users)
      .where(and(eq(users.role, role), eq(users.isActive, true)))
      .orderBy(
        desc(sql`${users.clerkUserId} like 'seed_%'`),
        asc(users.createdAt),
      )
      .limit(1),
  );
  return user ?? null;
}
