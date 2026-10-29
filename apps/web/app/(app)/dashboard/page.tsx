import { UserButton } from "@clerk/nextjs";

import { getCurrentUser } from "@/lib/auth";

// Placeholder until the cases dashboard (Phase 7); confirms the Clerk → users bridge.
export default async function DashboardPage() {
  const user = await getCurrentUser();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#F8FAFC] p-6">
      <UserButton />
      {user ? (
        <p className="text-sm text-[#334155]">
          Signed in as {user.fullName} ({user.email}) · role: {user.role}
        </p>
      ) : (
        <p className="max-w-sm text-center text-sm text-[#64748B]">
          Your account is signed in but not provisioned in QuotePulse yet, or it
          has been deactivated. Contact an administrator.
        </p>
      )}
    </main>
  );
}
