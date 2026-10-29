"use client";

import { cn } from "cn";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useCan } from "@/components/providers/session-user";
import { ApproveSublimitForm } from "@/components/workbench/approve-sublimit";
import { StatusPill } from "@/components/workbench/status-pill";
import { useSublimits } from "@/lib/api/queries";
import type { SublimitRow } from "@/lib/api/types";
import { formatInr } from "@/lib/format";

const TIERS = ["Option 1", "Option 2", "Option 3", "Option 4"] as const;

export function SublimitsWorkbench({ caseId }: { caseId: string }) {
  const { data, isPending, isError, error } = useSublimits(caseId);
  const canApprove = useCan("approveSublimit");
  const [selected, setSelected] = useState<SublimitRow | null>(null);

  if (isError) return <p className="text-sm text-[#991B1B]">{error.message}</p>;
  if (isPending)
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );

  return (
    <>
      <div className="overflow-x-auto rounded-md border border-[#E2E8F0] bg-white">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-left text-xs text-[#64748B]">
            <tr>
              <th className="h-9 px-3 font-medium">Procedure</th>
              {TIERS.map((t) => (
                <th key={t} className="px-3 text-right font-medium">
                  {t}
                </th>
              ))}
              <th className="px-3 font-medium">RFQ Amount</th>
              <th className="px-3 font-medium">Match</th>
              <th className="px-3 font-medium">Approval</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => {
              const matched = r.matched_option?.startsWith("Option")
                ? r.matched_option
                : null;
              const needsReview =
                r.match_status !== "Matched" && !r.is_underwriter_approved;
              return (
                <tr
                  key={r.procedure_name}
                  className={cn(
                    "h-10 border-b border-[#E2E8F0] last:border-0",
                    needsReview &&
                      r.match_status !== "Not Found" &&
                      "bg-[#FFF7ED]/60",
                  )}
                >
                  <td className="px-3 font-medium">{r.procedure_name}</td>
                  {TIERS.map((t) => (
                    <td
                      key={t}
                      className={cn(
                        "px-3 text-right font-mono text-[13px]",
                        matched === t && "font-semibold text-[#166534]",
                      )}
                    >
                      {formatInr(r.options[t])}
                    </td>
                  ))}
                  <td
                    className="max-w-48 truncate px-3 font-mono text-[13px]"
                    title={r.evidence.excerpt ?? undefined}
                  >
                    {r.extracted_amount_raw ?? "—"}
                  </td>
                  <td className="px-3">
                    <div className="flex items-center gap-1.5">
                      <StatusPill label={r.match_status} />
                      {matched && <StatusPill label={matched} />}
                    </div>
                  </td>
                  <td className="px-3">
                    {r.is_underwriter_approved ? (
                      <span title={r.approval_justification ?? undefined}>
                        <StatusPill label="Approved" />
                      </span>
                    ) : canApprove ? (
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => setSelected(r)}
                      >
                        {needsReview ? "Resolve" : "Override"}
                      </Button>
                    ) : (
                      <span className="text-xs text-[#64748B]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Dialog
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent className="sm:max-w-lg">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle>{selected.procedure_name}</DialogTitle>
                <DialogDescription>
                  RFQ amount: {selected.extracted_amount_raw ?? "not stated"} ·{" "}
                  {selected.match_status}
                </DialogDescription>
              </DialogHeader>
              <ApproveSublimitForm
                key={selected.procedure_name}
                caseId={caseId}
                row={selected}
                onDone={() => setSelected(null)}
              />
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
