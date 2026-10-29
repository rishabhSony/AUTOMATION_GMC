import { SignIn } from "@clerk/nextjs";

import { redirect } from "next/navigation";

import { clerkAppearance } from "@/lib/clerk-appearance";
import { DEV_MOCK_AUTH } from "@/lib/dev-mode";
import { safeRedirectPath } from "@/lib/safe-redirect";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (DEV_MOCK_AUTH) redirect("/dashboard"); // no Clerk in dev mock mode
  const params = await searchParams;
  const redirectTo = safeRedirectPath(params.redirect);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#F8FAFC] p-6">
      {params.notice === "invite-only" && (
        <p role="status" className="text-sm text-[#334155]">
          Account registration is invite-only.
        </p>
      )}
      <SignIn
        routing="hash"
        withSignUp={false}
        forceRedirectUrl={redirectTo}
        appearance={clerkAppearance}
      />
    </main>
  );
}
