"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { cn } from "cn";
import { FolderOpenIcon, PlusIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  debounce,
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
  useQueryStates,
} from "nuqs";

import { useCan } from "@/components/providers/session-user";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/workbench/status-pill";
import { useCases } from "@/lib/api/queries";
import {
  CASE_STATUSES,
  type CaseListItem,
  type CaseStatus,
} from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { isOnboardingDone } from "@/lib/onboarding";

const PAGE_SIZE = 25;

const FILTERS: { label: string; statuses: CaseStatus[] }[] = [
  { label: "All", statuses: [] },
  { label: "Needs Review", statuses: ["review_required"] },
  { label: "In Progress", statuses: ["draft", "uploaded", "processing"] },
  { label: "Ready for Quote", statuses: ["ready_for_quote"] },
  { label: "Completed", statuses: ["completed"] },
  { label: "Failed", statuses: ["failed"] },
];

// Cases that haven't finished processing open on the pipeline screen.
const caseHref = (c: CaseListItem) =>
  `/cases/${c.id}/${["draft", "uploaded", "processing", "failed"].includes(c.status) ? "pipeline" : "quote"}`;

const sameSet = (a: CaseStatus[], b: CaseStatus[]) =>
  a.length === b.length && a.every((s) => b.includes(s));

const column = createColumnHelper<CaseListItem>();
const columns = [
  column.accessor("case_number", {
    header: "Case",
    cell: (c) => <span className="font-mono text-[13px]">{c.getValue()}</span>,
  }),
  column.accessor("company_name", {
    header: "Company",
    cell: (c) => <span className="font-medium">{c.getValue()}</span>,
  }),
  column.accessor("status_label", {
    header: "Status",
    cell: (c) => <StatusPill label={c.getValue()} />,
  }),
  column.accessor("assignee_name", {
    header: "Assignee",
    cell: (c) => c.getValue() ?? "—",
  }),
  column.accessor("group_size", {
    header: "Lives",
    cell: (c) => (
      <span className="font-mono text-[13px]">{c.getValue() || "—"}</span>
    ),
  }),
  column.accessor("sme_flag", {
    header: "SME",
    cell: (c) =>
      c.row.original.group_size ? (c.getValue() ? "Yes" : "No") : "—",
  }),
  column.accessor("zone", { header: "Zone", cell: (c) => c.getValue() ?? "—" }),
  column.accessor("open_exceptions", {
    header: "Open Exceptions",
    cell: (c) => (
      <span
        className={cn(
          "font-mono text-[13px]",
          c.getValue() > 0 && "font-semibold text-[#9A3412]",
        )}
      >
        {c.getValue()}
      </span>
    ),
  }),
  column.accessor("updated_at", {
    header: "Updated",
    cell: (c) => (
      <span className="font-mono text-xs text-[#64748B]">
        {formatDateTime(c.getValue())}
      </span>
    ),
  }),
];

export function CasesDashboard() {
  const router = useRouter();
  // First visit in this browser: show the product tour once (App Flow /onboarding).
  useEffect(() => {
    if (!isOnboardingDone()) router.replace("/onboarding");
  }, [router]);
  const canCreate = useCan("editQuote");
  const [{ status, q, page }, setFilters] = useQueryStates({
    status: parseAsArrayOf(parseAsStringLiteral(CASE_STATUSES)).withDefault([]),
    q: parseAsString.withDefault(""),
    page: parseAsInteger.withDefault(1),
  });
  const { data, isPending, isError, error, isFetching } = useCases({
    status,
    q,
    page,
    pageSize: PAGE_SIZE,
  });

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const summary = data?.summary;
  const filtered = status.length > 0 || q !== "";

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-heading text-[28px] leading-9 font-bold tracking-[-0.02em]">
          Quotation Cases
        </h1>
        {canCreate && (
          <Button asChild>
            <Link href="/cases/new">
              <PlusIcon /> New Quote Case
            </Link>
          </Button>
        )}
      </div>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Total Cases" value={summary?.total} />
        <Metric
          label="Pending Underwriter Review"
          value={summary?.needs_review}
        />
        <Metric label="Quotes Prepared" value={summary?.prepared} />
        <Metric
          label="Avg Extraction Time"
          value={
            summary?.avg_pipeline_ms != null
              ? `${(summary.avg_pipeline_ms / 1000).toFixed(1)} s`
              : summary
                ? "—"
                : undefined
          }
        />
      </section>

      <section className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setFilters({ status: f.statuses, page: null })}
            className={cn(
              "h-7 rounded-full border px-3 text-xs font-medium transition-colors duration-150",
              sameSet(status, f.statuses)
                ? "border-[#0066FF] bg-[#0066FF] text-white"
                : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F1F5F9]",
            )}
          >
            {f.label}
          </button>
        ))}
        <div className="relative ml-auto w-full sm:w-72">
          <SearchIcon className="absolute top-2 left-2.5 size-4 text-[#64748B]" />
          <Input
            defaultValue={q}
            placeholder="Search company or case number"
            className="bg-white pl-8"
            onChange={(e) =>
              setFilters(
                { q: e.target.value || null, page: null },
                { limitUrlUpdates: debounce(300) },
              )
            }
          />
        </div>
      </section>

      <section className="overflow-x-auto rounded-md border border-[#E2E8F0] bg-white">
        {isError ? (
          <p className="p-6 text-sm text-[#991B1B]">
            Could not load cases: {error.message}
          </p>
        ) : isPending ? (
          <div className="flex flex-col gap-2 p-4">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
            <FolderOpenIcon className="size-10 text-[#94A3B8]" />
            <p className="font-heading font-semibold">
              No quotation cases found
            </p>
            <p className="max-w-md text-sm text-[#64748B]">
              {filtered
                ? "No cases match these filters."
                : "Upload an RFQ tender package and member census to generate your first automated GMC quote."}
            </p>
            {!filtered && canCreate && (
              <Button asChild className="mt-2">
                <Link href="/cases/new">
                  <PlusIcon /> Create First Quote Case
                </Link>
              </Button>
            )}
          </div>
        ) : (
          <table className={cn("w-full text-sm", isFetching && "opacity-70")}>
            <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-left text-xs text-[#64748B]">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      className="h-9 px-3 font-medium whitespace-nowrap"
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => router.push(caseHref(row.original))}
                  className="h-10 cursor-pointer border-b border-[#E2E8F0] last:border-0 hover:bg-[#F1F5F9]"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 whitespace-nowrap">
                      {cell.column.id === "case_number" ? (
                        <Link
                          href={caseHref(row.original)}
                          onClick={(e) => e.stopPropagation()}
                          className="text-[#0052CC] hover:underline"
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </Link>
                      ) : (
                        flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {data && data.total > PAGE_SIZE && (
        <nav className="flex items-center justify-end gap-2 text-xs text-[#64748B]">
          <span>
            Page {page} of {pages} · {data.total} cases
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setFilters({ page: page - 1 })}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setFilters({ page: page + 1 })}
          >
            Next
          </Button>
        </nav>
      )}
    </main>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string | undefined;
}) {
  return (
    <div className="rounded-md border border-[#E2E8F0] bg-white p-4">
      <p className="text-xs text-[#64748B]">{label}</p>
      {value === undefined ? (
        <Skeleton className="mt-2 h-7 w-16" />
      ) : (
        <p className="mt-1 font-mono text-2xl font-semibold">{value}</p>
      )}
    </div>
  );
}
