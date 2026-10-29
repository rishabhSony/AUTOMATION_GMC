"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "cn";
import { AlertTriangleIcon, UsersIcon } from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCan } from "@/components/providers/session-user";
import {
  DEMOGRAPHY_PAGE_SIZE,
  useDemography,
  useRecalculateAge,
} from "@/lib/api/queries";
import type { AgeBasisMode, DemographyRow } from "@/lib/api/types";
import { formatInr, isoToDdMmYyyy } from "@/lib/format";

const ROW_HEIGHT = 36; // UI brief §3.3

// Strict 7-column order (BRD §9.2) with the brief's widths.
const COLUMNS: {
  label: string;
  width: number;
  render: (r: DemographyRow) => React.ReactNode;
}[] = [
  {
    label: "Age",
    width: 80,
    render: (r) => (
      <span className="flex items-center gap-1 font-mono">
        {String(r.age).padStart(2, "0")}
        {r.flags.under18_employee && (
          <span title="Worker under statutory age 18">
            <AlertTriangleIcon className="size-3.5 text-[#F59E0B]" />
          </span>
        )}
      </span>
    ),
  },
  {
    label: "Date of Birth",
    width: 120,
    render: (r) => <Mono>{r.date_of_birth ?? "—"}</Mono>,
  },
  {
    label: "Sum Insured",
    width: 130,
    render: (r) => <Mono>{formatInr(r.sum_insured)}</Mono>,
  },
  {
    label: "Relationship",
    width: 120,
    render: (r) => (
      <span
        title={
          r.flags.orphan_dependent
            ? "No primary employee with this EmpCode"
            : undefined
        }
      >
        {r.relationship}
        {r.flags.orphan_dependent && (
          <span className="ml-1 text-[#9A3412]">!</span>
        )}
      </span>
    ),
  },
  {
    label: "Name",
    width: 240,
    render: (r) => (
      <span
        className="truncate"
        title={
          r.flags.duplicate ? "Duplicate EmpCode + Name + Relationship" : r.name
        }
      >
        {r.name}
        {r.flags.duplicate && (
          <span className="ml-1 text-[#9A3412]">(dup)</span>
        )}
      </span>
    ),
  },
  { label: "EmpCode", width: 110, render: (r) => <Mono>{r.emp_code}</Mono> },
  { label: "Gender", width: 90, render: (r) => r.gender },
];
const GRID_TEMPLATE = COLUMNS.map((c) => `${c.width}px`).join(" ");
const GRID_WIDTH = COLUMNS.reduce((sum, c) => sum + c.width, 0);

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[13px]">{children}</span>;
}

export function DemographyWorkbench({ caseId }: { caseId: string }) {
  const [flaggedOnly, setFlaggedOnly] = useQueryState(
    "flagged",
    parseAsBoolean.withDefault(false),
  );
  const query = useDemography(caseId, flaggedOnly);
  const rows = query.data?.pages.flatMap((p) => p.rows) ?? [];
  const first = query.data?.pages[0];
  const total = first?.total ?? 0;

  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: total,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 20,
  });
  const items = virtualizer.getVirtualItems();
  const lastIndex = items.at(-1)?.index ?? 0;
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query;

  // Load the next 1,000-row page as the viewport nears the end of what's loaded.
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && lastIndex >= rows.length - 50)
      void fetchNextPage();
  }, [lastIndex, rows.length, hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (query.isError)
    return <p className="text-sm text-[#991B1B]">{query.error.message}</p>;

  const metrics = first?.metrics;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-md border border-[#E2E8F0] bg-white px-4 py-3 text-sm">
        <Stat label="Total Lives" value={metrics?.group_size} />
        <Stat label="Primary Members" value={metrics?.primary_members_count} />
        <Stat
          label="SME Flag"
          value={
            metrics
              ? metrics.sme_flag
                ? "Yes (≤250)"
                : "No (>250)"
              : undefined
          }
        />
        {metrics && (
          <AgeBasisSwitcher
            key={`${metrics.age_basis_mode}-${metrics.proposal_start_date}`}
            caseId={caseId}
            mode={metrics.age_basis_mode}
            startDate={metrics.proposal_start_date}
          />
        )}
        <label className="ml-auto flex items-center gap-2 text-xs text-[#334155]">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => setFlaggedOnly(e.target.checked || null)}
          />
          Flagged rows only
        </label>
      </div>

      {query.isPending ? (
        <div className="flex flex-col gap-1">
          {Array.from({ length: 12 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      ) : total === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-md border border-[#E2E8F0] bg-white px-6 py-16 text-center">
          <UsersIcon className="size-10 text-[#94A3B8]" />
          <p className="font-heading font-semibold">
            {flaggedOnly ? "No flagged members" : "No census processed yet"}
          </p>
          <p className="max-w-md text-sm text-[#64748B]">
            {flaggedOnly
              ? "Every member passed the integrity checks."
              : "Upload and process the member census to see the standardized 7-column roster."}
          </p>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="h-[calc(100vh-330px)] min-h-80 overflow-auto rounded-md border border-[#E2E8F0] bg-white"
        >
          <div style={{ minWidth: GRID_WIDTH }}>
            <div
              role="row"
              className="sticky top-0 z-10 grid h-9 items-center border-b border-[#E2E8F0] bg-[#F8FAFC] text-xs font-medium text-[#64748B]"
              style={{ gridTemplateColumns: GRID_TEMPLATE }}
            >
              {COLUMNS.map((c) => (
                <div key={c.label} role="columnheader" className="px-3">
                  {c.label}
                </div>
              ))}
            </div>
            <div
              className="relative"
              style={{ height: virtualizer.getTotalSize() }}
            >
              {items.map((item) => {
                const r = rows[item.index];
                return (
                  <div
                    key={item.key}
                    role="row"
                    className={cn(
                      "absolute inset-x-0 grid items-center border-b border-[#E2E8F0] text-sm",
                      r?.flags.has_exception && "bg-[#FFF7ED]/50",
                    )}
                    style={{
                      height: ROW_HEIGHT,
                      transform: `translateY(${item.start}px)`,
                      gridTemplateColumns: GRID_TEMPLATE,
                    }}
                  >
                    {r ? (
                      COLUMNS.map((c) => (
                        <div
                          key={c.label}
                          role="cell"
                          className="flex min-w-0 px-3"
                        >
                          {c.render(r)}
                        </div>
                      ))
                    ) : (
                      <Skeleton className="col-span-7 mx-3 h-4" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {total > 0 && (
        <p className="text-xs text-[#64748B]">
          {rows.length.toLocaleString("en-IN")} of{" "}
          {total.toLocaleString("en-IN")} members loaded ·{" "}
          {DEMOGRAPHY_PAGE_SIZE.toLocaleString("en-IN")} per page
        </p>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: number | string | null | undefined;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs text-[#64748B]">{label}:</span>
      {value === undefined ? (
        <Skeleton className="h-4 w-10" />
      ) : (
        <span className="font-mono font-semibold">
          {typeof value === "number"
            ? value.toLocaleString("en-IN")
            : (value ?? "—")}
        </span>
      )}
    </div>
  );
}

/** Segmented Current Date / Policy Proposal Start Date toggle + Recalculate (§3.3). */
function AgeBasisSwitcher({
  caseId,
  mode: savedMode,
  startDate,
}: {
  caseId: string;
  mode: AgeBasisMode;
  startDate: string | null;
}) {
  const canRecalculate = useCan("recalculateAge");
  const [mode, setMode] = useState<AgeBasisMode>(savedMode);
  const [date, setDate] = useState(startDate ?? "");
  const recalc = useRecalculateAge(caseId);
  const today = new Date().toISOString().slice(0, 10);
  const dirty =
    mode !== savedMode ||
    (mode === "policy_proposal_start_date" && date !== (startDate ?? ""));
  const valid = mode === "current_date" || !!date;

  const options: { value: AgeBasisMode; label: string }[] = [
    { value: "current_date", label: `Current Date (${isoToDdMmYyyy(today)})` },
    {
      value: "policy_proposal_start_date",
      label: "Policy Proposal Start Date",
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-[#64748B]">Age Mode:</span>
      <div className="flex rounded-md border border-[#E2E8F0] p-0.5">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            disabled={!canRecalculate}
            onClick={() => setMode(o.value)}
            className={cn(
              "rounded px-2.5 py-1 text-xs transition-colors duration-150",
              mode === o.value
                ? "bg-[#0052CC] text-white"
                : "text-[#334155] hover:bg-[#F1F5F9]",
              !canRecalculate && "cursor-not-allowed",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      {mode === "policy_proposal_start_date" && (
        <Input
          type="date"
          value={date}
          disabled={!canRecalculate}
          onChange={(e) => setDate(e.target.value)}
          className="h-7 w-40 font-mono text-xs"
        />
      )}
      {canRecalculate && (
        <Button
          size="sm"
          disabled={!dirty || !valid || recalc.isPending}
          onClick={() =>
            recalc.mutate(
              {
                basis_mode: mode,
                proposal_start_date:
                  mode === "policy_proposal_start_date" ? date : null,
              },
              {
                onSuccess: (res) =>
                  toast.success(
                    `Ages recalculated as of ${isoToDdMmYyyy(res.basis_date)}: ${res.ages_changed.toLocaleString("en-IN")} changed, ${res.under18_employees} under-18 employees`,
                  ),
                onError: (e) => toast.error(e.message),
              },
            )
          }
        >
          {recalc.isPending ? "Recalculating…" : "Recalc"}
        </Button>
      )}
    </div>
  );
}
