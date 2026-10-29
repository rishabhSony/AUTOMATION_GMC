"use client";

import { HistoryIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuditTrail } from "@/lib/api/queries";
import { formatDateTime } from "@/lib/format";

const ACTION_LABELS: Record<string, string> = {
  manual_input_update: "Manual input",
  zone_recalc: "Zone re-derived",
  field_override: "Field override",
  sublimit_override: "Sub-limit approval",
  age_basis_recalc: "Age recalculation",
  exception_resolved: "Exception resolved",
  exception_reopened: "Exception reopened",
  ai_extraction: "AI extraction",
  case_export: "Export",
};

/** Compact one-line JSON for old/new values ({"brokerage_pct": "7.50"} → brokerage_pct: 7.50). */
function describe(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value !== "object") return String(value);
  return Object.entries(value as Record<string, unknown>)
    .map(
      ([k, v]) =>
        `${k}: ${v === null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v)}`,
    )
    .join(", ");
}

export function AuditTrail({ caseId }: { caseId: string }) {
  const { data, isPending, isError, error } = useAuditTrail(caseId);

  if (isError) return <p className="text-sm text-[#991B1B]">{error.message}</p>;
  if (isPending)
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  if (data.rows.length === 0)
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-[#E2E8F0] bg-white px-6 py-16 text-center">
        <HistoryIcon className="size-10 text-[#94A3B8]" />
        <p className="font-heading font-semibold">No changes recorded yet</p>
        <p className="max-w-md text-sm text-[#64748B]">
          Every override, recalculation, approval and export on this case
          appears here.
        </p>
      </div>
    );

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-[#64748B]">
        {data.total} entries, newest first. The log is append-only.
      </p>
      <div className="overflow-x-auto rounded-md border border-[#E2E8F0] bg-white">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-left text-xs text-[#64748B]">
            <tr>
              <th className="h-9 px-3 font-medium">Timestamp</th>
              <th className="px-3 font-medium">Reviewer</th>
              <th className="px-3 font-medium">Action</th>
              <th className="px-3 font-medium">Target</th>
              <th className="px-3 font-medium">Old Value</th>
              <th className="px-3 font-medium">New Value</th>
              <th className="px-3 font-medium">Justification</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr
                key={r.id}
                className="border-b border-[#E2E8F0] align-top last:border-0"
              >
                <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                  {formatDateTime(r.timestamp)}
                </td>
                <td className="px-3 py-2 text-xs">{r.user_email}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {ACTION_LABELS[r.action] ?? r.action}
                </td>
                <td className="max-w-56 px-3 py-2 font-mono text-xs break-words">
                  {r.target_entity}
                </td>
                <td className="max-w-64 px-3 py-2 font-mono text-xs break-words text-[#64748B]">
                  {describe(r.old_value)}
                </td>
                <td className="max-w-64 px-3 py-2 font-mono text-xs break-words">
                  {describe(r.new_value)}
                </td>
                <td className="max-w-72 px-3 py-2 text-xs text-[#334155]">
                  {r.justification_reason ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
