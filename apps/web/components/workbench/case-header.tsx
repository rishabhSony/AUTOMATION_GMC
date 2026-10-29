"use client";

import { cn } from "cn";
import { ChevronRightIcon, DownloadIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/workbench/status-pill";
import { useApi } from "@/lib/api/client";
import { useCase } from "@/lib/api/queries";

const TABS = [
  { slug: "pipeline", label: "Pipeline" },
  { slug: "quote", label: "Quote Review" },
  { slug: "treatments", label: "Modern Treatments" },
  { slug: "sublimits", label: "Procedure Sub-Limits" },
  { slug: "demography", label: "Demography" },
  { slug: "exceptions", label: "Exceptions" },
  { slug: "audit", label: "Audit Trail" },
] as const;

export function CaseHeader({ caseId }: { caseId: string }) {
  const pathname = usePathname();
  const { data: c, isError, error } = useCase(caseId);
  const active = TABS.find((t) => pathname.endsWith(`/${t.slug}`))?.slug;

  return (
    <div className="sticky top-14 z-20 border-b border-[#E2E8F0] bg-white">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-end justify-between gap-4 px-6 pt-4">
        <div className="flex flex-col gap-1">
          <nav className="flex items-center gap-1 text-xs text-[#64748B]">
            <Link href="/dashboard" className="hover:text-[#0F172A]">
              Dashboard
            </Link>
            <ChevronRightIcon className="size-3" />
            <span>{c ? `${c.company_name} (${c.case_number})` : "Case"}</span>
          </nav>
          {isError ? (
            <p className="text-sm text-[#991B1B]">{error.message}</p>
          ) : c ? (
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-heading text-[28px] leading-9 font-bold tracking-[-0.02em]">
                {c.company_name}
              </h1>
              <StatusPill label={c.status_label} />
              <span className="text-xs text-[#64748B]">
                {c.proposal_type ?? "—"} · Assignee {c.assignee_name ?? "—"}
              </span>
            </div>
          ) : (
            <Skeleton className="h-9 w-72" />
          )}
        </div>
        <div className="flex gap-2 pb-1">
          <ExportButton
            caseId={caseId}
            kind="quote-excel"
            label="Quote Sheet"
          />
          <ExportButton
            caseId={caseId}
            kind="demography-excel"
            label="Demography (7-col)"
          />
        </div>
      </div>
      <nav className="mx-auto flex max-w-[1400px] gap-1 overflow-x-auto px-6 pt-3">
        {TABS.map((t) => (
          <Link
            key={t.slug}
            href={`/cases/${caseId}/${t.slug}`}
            className={cn(
              "flex items-center gap-1.5 border-b-2 px-3 pb-2 text-sm font-medium whitespace-nowrap transition-colors duration-150",
              active === t.slug
                ? "border-[#0066FF] text-[#0F172A]"
                : "border-transparent text-[#64748B] hover:text-[#0F172A]",
            )}
          >
            {t.label}
            {t.slug === "exceptions" &&
              c &&
              c.counts.open_exceptions + c.counts.unmatched_sublimits > 0 && (
                <span className="rounded-full bg-[#FFF7ED] px-1.5 font-mono text-[11px] font-semibold text-[#9A3412]">
                  {c.counts.open_exceptions + c.counts.unmatched_sublimits}
                </span>
              )}
          </Link>
        ))}
      </nav>
    </div>
  );
}

function ExportButton({
  caseId,
  kind,
  label,
}: {
  caseId: string;
  kind: "quote-excel" | "demography-excel";
  label: string;
}) {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          const name = await api.download(`/cases/${caseId}/export/${kind}`);
          toast.success(`Downloaded ${name}`, {
            description: "A copy is archived in outputs/analysis.",
          });
        } catch (e) {
          toast.error(`Export failed: ${(e as Error).message}`);
        } finally {
          setBusy(false);
        }
      }}
    >
      <DownloadIcon />
      {busy ? "Generating…" : label}
    </Button>
  );
}
