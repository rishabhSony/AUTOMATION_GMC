import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

// Resource-level guard for every signed-in route (dashboard, cases, admin, settings).
// Middleware redirects earlier with `?redirect=`; this catches anything it misses.
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/login");
  return children;
}
