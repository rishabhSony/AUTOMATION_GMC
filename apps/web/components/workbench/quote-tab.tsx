"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { cn } from "cn";
import { ArrowUpRightIcon, FileSearchIcon, PencilIcon } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";
import { Fragment, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCan } from "@/components/providers/session-user";
import { EvidenceDrawer } from "@/components/workbench/evidence-drawer";
import {
  MANUAL_FIELDS,
  ManualInputCell,
} from "@/components/workbench/manual-input-cell";
import { OverrideDialog } from "@/components/workbench/override-dialog";
import { SECTION_LABELS } from "@/components/workbench/sections";
import { StatusPill } from "@/components/workbench/status-pill";
import { useCase, useExtractions } from "@/lib/api/queries";
import type { CaseDetail, QuoteRow } from "@/lib/api/types";

// The API also rejects grid overrides of Zone: it is derived from PIN / District.
const NOT_OVERRIDABLE = new Set([...Object.keys(MANUAL_FIELDS), "Zone"]);

const CONFIDENCE_DOT = {
  High: "bg-[#16A34A]",
  Medium: "bg-[#F59E0B]",
  Low: "bg-[#EF4444]",
};

/**
 * Manual-input rows and Zone always show, even before RFQ extraction has run;
 * their values come from the `cases` columns, which are the source of truth.
 */
function withManualRows(rows: QuoteRow[], c: CaseDetail): QuoteRow[] {
  const present = new Set(rows.map((r) => r.quote_field));
  const row = (
    quote_field: string,
    section: string,
    source_status: QuoteRow["source_status"],
    confidence: QuoteRow["confidence"] = "High",
  ): QuoteRow => ({
    id: `manual-${quote_field}`,
    section,
    quote_field,
    coverage_details: null,
    proposed_details: null,
    source_status,
    confidence,
    confidence_score: confidence === "High" ? 1 : 0.4,
    is_manual_override: false,
    evidence: { file: null, page: null, excerpt: null, verification: null },
  });
  const zoneKnown = !!c.zone && c.zone !== "Review Required";
  const synthetic = [
    row("Rater Type", "quotation", "Fixed"),
    row("Brokerage %", "quotation", "Manual"),
    row("Zone", "quotation", zoneKnown ? "AI Derived" : "Review Required",
        zoneKnown ? "High" : "Low"), // prettier-ignore
    row("PIN Code", "policyholder", "Manual"),
    row("State", "policyholder", "Manual"),
    row("District", "policyholder", "Manual"),
  ].filter((r) => !present.has(r.quote_field));
  // Keep each synthetic row next to its section so section headers aren't repeated.
  const merged = [...rows];
  for (const s of synthetic) {
    const last = merged.findLastIndex((r) => r.section === s.section);
    merged.splice(last === -1 ? merged.length : last + 1, 0, s);
  }
  return merged;
}

const column = createColumnHelper<QuoteRow>();

export function QuoteWorkbench({ caseId }: { caseId: string }) {
  const grid = useExtractions(caseId);
  const caseQuery = useCase(caseId);
  const canEdit = useCan("editQuote");
  const [evidenceField, setEvidenceField] = useQueryState(
    "evidence",
    parseAsString,
  );
  const [overrideField, setOverrideField] = useState<string | null>(null);
  const [zonePulse, setZonePulse] = useState(false);

  const c = caseQuery.data;
  const rows = useMemo(
    () => (grid.data && c ? withManualRows(grid.data.rows, c) : []),
    [grid.data, c],
  );

  const columns = useMemo(
    () => [
      column.accessor("quote_field", {
        header: "Quote Fields",
        size: 260,
        cell: (ctx) => <span className="font-medium">{ctx.getValue()}</span>,
      }),
      column.accessor("coverage_details", {
        header: "Coverage Details",
        size: 320,
        cell: (ctx) => (
          <span className="text-[#334155]">{ctx.getValue() ?? "—"}</span>
        ),
      }),
      column.accessor("proposed_details", {
        header: "Proposed Details",
        size: 320,
        cell: (ctx) => {
          const manual = MANUAL_FIELDS[ctx.row.original.quote_field];
          if (manual && c)
            return (
              <ManualInputCell
                caseId={caseId}
                field={manual}
                value={c[manual]}
                disabled={!canEdit}
                onZoneChange={() => {
                  setZonePulse(true);
                  setTimeout(() => setZonePulse(false), 1200);
                }}
              />
            );
          const value =
            ctx.row.original.quote_field === "Zone" && c
              ? c.zone
              : ctx.getValue();
          return (
            <span className="font-semibold text-[#0F172A]">{value ?? "—"}</span>
          );
        },
      }),
      column.accessor("source_status", {
        header: "Source Status",
        size: 160,
        cell: (ctx) => <StatusPill label={ctx.getValue()} />,
      }),
      column.accessor("confidence", {
        header: "Confidence",
        size: 160,
        cell: (ctx) => {
          const r = ctx.row.original;
          return (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setEvidenceField(r.quote_field)}
                className="flex items-center gap-1.5 rounded px-1 py-0.5 text-xs hover:bg-[#F1F5F9]"
                title="Open source evidence"
              >
                <span
                  className={cn(
                    "size-2 rounded-full",
                    CONFIDENCE_DOT[r.confidence],
                  )}
                />
                {r.confidence} {Math.round(r.confidence_score * 100)}%
                <ArrowUpRightIcon className="size-3 text-[#0052CC]" />
              </button>
              {canEdit && !NOT_OVERRIDABLE.has(r.quote_field) && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  title="Override with justification"
                  onClick={() => setOverrideField(r.quote_field)}
                >
                  <PencilIcon />
                </Button>
              )}
            </div>
          );
        },
      }),
    ],
    [c, caseId, canEdit, setEvidenceField],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (r) => r.quote_field,
  });

  if (grid.isError || caseQuery.isError)
    return (
      <p className="text-sm text-[#991B1B]">
        Could not load the quote grid:{" "}
        {(grid.error ?? caseQuery.error)?.message}
      </p>
    );
  if (grid.isPending || caseQuery.isPending)
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 10 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );

  const extracted = grid.data.rows.length > 0;
  const byField = new Map(rows.map((r) => [r.quote_field, r]));
  let section: string | null = null;

  return (
    <div className="flex flex-col gap-3">
      {!extracted && (
        <div className="flex items-center gap-3 rounded-md border border-[#E2E8F0] bg-white p-4 text-sm text-[#334155]">
          <FileSearchIcon className="size-5 text-[#94A3B8]" />
          RFQ extraction hasn&apos;t run for this case yet. The manual inputs
          below can already be filled in.
        </div>
      )}
      <div className="overflow-x-auto rounded-md border border-[#E2E8F0] bg-white">
        <table className="w-full min-w-[1220px] table-fixed text-sm">
          <colgroup>
            {table.getAllLeafColumns().map((col) => (
              <col key={col.id} style={{ width: col.getSize() }} />
            ))}
          </colgroup>
          <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-left text-xs text-[#64748B]">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h, i) => (
                  <th
                    key={h.id}
                    className={cn(
                      "h-9 px-3 font-medium",
                      i === 0 && "sticky left-0 z-10 bg-[#F8FAFC]",
                    )}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => {
              const header = row.original.section !== section;
              section = row.original.section;
              return (
                <Fragment key={row.id}>
                  {header && (
                    <tr className="bg-[#F1F5F9]">
                      <td
                        colSpan={5}
                        className="h-8 px-3 text-[11px] font-semibold tracking-wider text-[#475569] uppercase"
                      >
                        {SECTION_LABELS[row.original.section] ??
                          row.original.section}
                      </td>
                    </tr>
                  )}
                  <tr
                    className={cn(
                      "h-10 border-b border-[#E2E8F0] align-middle last:border-0",
                      row.original.quote_field === "Zone" &&
                        zonePulse &&
                        "animate-pulse bg-[#F0FDFA]",
                    )}
                  >
                    {row.getVisibleCells().map((cell, i) => (
                      <td
                        key={cell.id}
                        className={cn(
                          "truncate px-3 py-1",
                          i === 0 && "sticky left-0 bg-white",
                        )}
                        title={
                          typeof cell.getValue() === "string"
                            ? (cell.getValue() as string)
                            : undefined
                        }
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </td>
                    ))}
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <EvidenceDrawer
        caseId={caseId}
        row={evidenceField ? byField.get(evidenceField) : undefined}
        onClose={() => setEvidenceField(null)}
      />
      <OverrideDialog
        caseId={caseId}
        row={overrideField ? byField.get(overrideField) : undefined}
        onClose={() => setOverrideField(null)}
      />
    </div>
  );
}
