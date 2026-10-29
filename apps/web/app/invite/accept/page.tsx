import { SignUp } from "@clerk/nextjs";
import Link from "next/link";
import { redirect } from "next/navigation";

import { clerkAppearance } from "@/lib/clerk-appearance";
import { DEV_MOCK_AUTH } from "@/lib/dev-mode";

// Clerk invitation emails link here with a `__clerk_ticket` token. Without a
// ticket there is nothing to accept, since self-registration is disabled.
export default async function InviteAcceptPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (DEV_MOCK_AUTH) redirect("/dashboard"); // no Clerk in dev mock mode
  const { __clerk_ticket: ticket } = await searchParams;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#F8FAFC] p-6">
      {ticket ? (
        <SignUp
          routing="hash"
          signInUrl="/login"
          forceRedirectUrl="/dashboard"
          appearance={clerkAppearance}
        />
      ) : (
        <div className="max-w-sm space-y-2 text-center">
          <h1 className="text-lg font-semibold text-[#0F172A]">
            Invitation required
          </h1>
          <p className="text-sm text-[#64748B]">
            QuotePulse GMC is invite-only. Open the link from your invitation
            email, or ask an administrator to invite you.
          </p>
          <Link
            href="/login"
            className="text-sm font-medium text-[#0052CC] hover:underline"
          >
            Back to sign in
          </Link>
        </div>
      )}
    </main>
  );
}
