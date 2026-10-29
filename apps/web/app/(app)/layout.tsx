import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AppProviders } from "@/components/providers/query-provider";
import { SessionUserProvider } from "@/components/providers/session-user";
import { DevRoleSwitcher } from "@/components/providers/dev-role-switcher";
import { getCurrentUser, isSignedIn } from "@/lib/auth";
import { DEV_MOCK_AUTH } from "@/lib/dev-mode";

const ROLE_LABELS = {
  admin: "Admin",
  underwriter: "Underwriter",
  sales_rm: "Sales RM",
  ops_analyst: "Ops Analyst",
} as const;

// Resource-level guard for every signed-in route (dashboard, cases, admin, settings).
// Middleware redirects earlier with `?redirect=`; this catches anything it misses.
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!(await isSignedIn())) redirect("/login");

  const user = await getCurrentUser();
  if (!user) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#F8FAFC] p-6">
        {!DEV_MOCK_AUTH && <UserButton />}
        <p className="max-w-sm text-center text-sm text-[#64748B]">
          {DEV_MOCK_AUTH
            ? "Dev mock auth found no active seeded user for this role. Run `bun run seed`."
            : "Your account is signed in but not provisioned in QuotePulse yet, or it has been deactivated. Contact an administrator."}
        </p>
      </main>
    );
  }

  return (
    <SessionUserProvider
      user={{
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        role: user.role,
      }}
    >
      <AppProviders>
        <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A]">
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-[#E2E8F0] bg-white px-6">
            <Link
              href="/dashboard"
              className="font-heading text-[15px] font-semibold tracking-tight"
            >
              QuotePulse <span className="text-[#0052CC]">GMC</span>
            </Link>
            <div className="flex items-center gap-3 text-xs text-[#64748B]">
              <Link href="/onboarding" className="hover:text-[#0F172A]">
                Product tour
              </Link>
              <span>
                {user.fullName} · {ROLE_LABELS[user.role]}
              </span>
              {DEV_MOCK_AUTH ? <DevRoleSwitcher /> : <UserButton />}
            </div>
          </header>
          {children}
        </div>
      </AppProviders>
    </SessionUserProvider>
  );
}
