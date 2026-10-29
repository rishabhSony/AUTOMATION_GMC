import "server-only";

import { auth } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { cache } from "react";

import { withRlsContext, type Tx } from "@/db";
import { users } from "@/db/schema";

export type CurrentUser = typeof users.$inferSelect;

/**
 * Resolves the Clerk session to the internal `users` row, or null when signed out,
 * not yet synced by the webhook, or deactivated. Cached per request.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
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
