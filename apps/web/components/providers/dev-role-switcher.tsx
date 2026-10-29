"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FlaskConicalIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";

import { setDevRole } from "@/app/(app)/dev-role-action";
import { useSessionUser } from "@/components/providers/session-user";
import { DEV_ROLES } from "@/lib/dev-mode";

const LABELS = {
  admin: "Admin",
  underwriter: "Underwriter",
  sales_rm: "Sales RM",
  ops_analyst: "Ops Analyst",
} as const;

/** Header control shown only in dev mock mode: switches the mock user's role. */
export function DevRoleSwitcher() {
  const user = useSessionUser();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, startTransition] = useTransition();

  return (
    <label
      className="flex items-center gap-2 rounded-full border border-[#FDE68A] bg-[#FEF3C7] py-1 pr-1 pl-2.5 text-xs font-medium text-[#92400E]"
      title="Dev mock auth: no Clerk. API calls send X-Dev-User-Id / X-Dev-User-Role."
    >
      <FlaskConicalIcon className="size-3.5" />
      Dev role
      <select
        aria-label="Dev role"
        value={user.role}
        disabled={pending}
        onChange={(e) => {
          const role = e.target.value;
          startTransition(async () => {
            try {
              await setDevRole(role);
              queryClient.clear(); // cached data was fetched as the previous role
              router.refresh();
              toast.success(
                `Now acting as ${LABELS[role as keyof typeof LABELS]}`,
              );
            } catch (err) {
              toast.error((err as Error).message);
            }
          });
        }}
        className="rounded-full border border-[#FDE68A] bg-white px-2 py-0.5 text-xs text-[#0F172A]"
      >
        {DEV_ROLES.map((r) => (
          <option key={r} value={r}>
            {LABELS[r]}
          </option>
        ))}
      </select>
    </label>
  );
}
