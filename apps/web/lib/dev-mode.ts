/**
 * Offline dev mode (no Clerk keys): NEXT_PUBLIC_ENABLE_DEV_MOCK_AUTH=true with `bun run dev`.
 * The signed-in user is a seeded `users` row picked by role from a cookie, and API calls
 * carry X-Dev-User-Id / X-Dev-User-Role instead of a Clerk token (the API must run with
 * ENABLE_DEV_MOCK_AUTH=true). Never active in a production build.
 */
export const DEV_MOCK_AUTH =
  process.env.NEXT_PUBLIC_ENABLE_DEV_MOCK_AUTH === "true" &&
  process.env.NODE_ENV !== "production";

export const DEV_ROLE_COOKIE = "qp_dev_role";

export const DEV_ROLES = [
  "admin",
  "underwriter",
  "sales_rm",
  "ops_analyst",
] as const;
export type DevRole = (typeof DEV_ROLES)[number];

export const isDevRole = (value: unknown): value is DevRole =>
  DEV_ROLES.includes(value as DevRole);
