import { sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as schema from "./schema";

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set (apps/web/.env.local)");
}

const client = postgres(process.env.DATABASE_URL);

export const db = drizzle(client, { schema });

export type Db = typeof db;
export type Tx = Parameters<Parameters<Db["transaction"]>[0]>[0];
export type UserRole = (typeof schema.userRoleEnum.enumValues)[number];

export type RlsContext = {
  userId?: string;
  role?: UserRole;
  clerkUserId?: string;
};

/**
 * Runs `fn` in a transaction with the RLS session settings applied
 * (`app.current_user_id`, `app.current_user_role`, `app.current_clerk_user_id`).
 * Settings are transaction-local, so they never leak across pooled connections.
 */
export function withRlsContext<T>(
  ctx: RlsContext,
  fn: (tx: Tx) => Promise<T>,
): Promise<T> {
  return db.transaction(async (tx) => {
    await tx.execute(sql`
      select
        set_config('app.current_user_id', ${ctx.userId ?? ""}, true),
        set_config('app.current_user_role', ${ctx.role ?? ""}, true),
        set_config('app.current_clerk_user_id', ${ctx.clerkUserId ?? ""}, true)
    `);
    return fn(tx);
  });
}

/**
 * Trusted server-side context (seed, verified Clerk webhooks). Runs with the
 * admin role, which every RLS policy allows. Never call it with user input.
 */
export function withSystemContext<T>(fn: (tx: Tx) => Promise<T>): Promise<T> {
  return withRlsContext({ role: "admin" }, fn);
}

export async function closeDb() {
  await client.end();
}
