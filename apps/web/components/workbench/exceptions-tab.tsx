"use client";

import { cn } from "cn";
import {
  AlertTriangleIcon,
  ArrowUpRightIcon,
  CheckCircle2Icon,
} from "lucide-react";
import Link from "next/link";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCan } from "@/components/providers/session-user";
import { ApproveSublimitForm } from "@/components/workbench/approve-sublimit";
import {
  JustificationField,
  justificationOk,
} from "@/components/workbench/justification-field";
import { StatusPill } from "@/components/workbench/status-pill";
import {
  useExceptions,
  useExtractions,
  useResolveException,
  useSublimits,
} from "@/lib/api/queries";
import type { DemographyException, SublimitRow } from "@/lib/api/types";
import { formatDateTime, formatInr } from "@/lib/format";

const VIEWS = ["open", "resolved", "all"] as const;
const REVIEW_STATUSES = new Set(["Review Required", "Conflict", "Ambiguous"]);

export function ExceptionsQueue({ caseId }: { caseId: string }) {
  const [view, setView] = useQueryState(
    "view",
    parseAsStringLiteral(VIEWS).withDefault("open"),
  );
  const exceptions = useExceptions(caseId, {
    resolved: view === "all" ? null : view === "resolved",
  });
  const sublimits = useSublimits(caseId);
  const grid = useExtractions(caseId);

  const unmatched = (sublimits.data ?? []).filter(
    (s) =>
      s.match_status === "Unmatched / Review Required" &&
      !s.is_underwriter_approved,
  );
  const reviewFields = (grid.data?.rows ?? []).filter(
    (r) => REVIEW_STATUSES.has(r.source_status) && !r.is_manual_override,
  );

  return (
    <div className="flex flex-col gap-8">
      <Section
        title="Unmatched Procedure Sub-Limits"
        count={sublimits.isPending ? undefined : unmatched.length}
      >
        {sublimits.isError ? (
          <ErrorText message={sublimits.error.message} />
        ) : unmatched.length === 0 && !sublimits.isPending ? (
          <Clear text="Every extracted sub-limit matches an Option tier or is approved." />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {unmatched.map((s) => (
              <SublimitCard key={s.procedure_name} caseId={caseId} row={s} />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Quote Fields Needing Review"
        count={grid.isPending ? undefined : reviewFields.length}
      >
        {grid.isError ? (
          <ErrorText message={grid.error.message} />
        ) : reviewFields.length === 0 && !grid.isPending ? (
          <Clear text="No conflicting or unverified quote fields." />
        ) : (
          <ul className="divide-y divide-[#E2E8F0] rounded-md border border-[#E2E8F0] bg-white">
            {reviewFields.map((r) => (
              <li
                key={r.quote_field}
                className="flex items-center gap-3 px-4 py-2.5 text-sm"
              >
                <StatusPill label={r.source_status} />
                <span className="font-medium">{r.quote_field}</span>
                <span className="truncate text-[#64748B]">
                  {r.evidence.verification ?? r.proposed_details ?? ""}
                </span>
                <Link
                  href={`/cases/${caseId}/quote?evidence=${encodeURIComponent(r.quote_field)}`}
                  className="ml-auto flex shrink-0 items-center gap-1 text-xs text-[#0052CC] hover:underline"
                >
                  Review evidence <ArrowUpRightIcon className="size-3" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Demographic Anomalies"
        count={exceptions.data?.total}
        actions={
          <div className="flex rounded-md border border-[#E2E8F0] bg-white p-0.5">
            {VIEWS.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v === "open" ? null : v)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs capitalize transition-colors duration-150",
                  view === v
                    ? "bg-[#0052CC] text-white"
                    : "text-[#334155] hover:bg-[#F1F5F9]",
                )}
              >
                {v}
              </button>
            ))}
          </div>
        }
      >
        {exceptions.isError ? (
          <ErrorText message={exceptions.error.message} />
        ) : exceptions.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : exceptions.data.rows.length === 0 ? (
          <Clear
            text={
              view === "open"
                ? "No open demographic exceptions."
                : "Nothing to show."
            }
          />
        ) : (
          <>
            <div className="flex flex-wrap gap-2 text-xs text-[#64748B]">
              {exceptions.data.counts.map((c) => (
                <span
                  key={c.exception_type}
                  className="rounded-full border border-[#E2E8F0] bg-white px-2 py-0.5"
                >
                  {c.label ?? c.exception_type}: {c.open} open / {c.total}
                </span>
              ))}
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {exceptions.data.rows.map((e) => (
                <ExceptionCard key={e.id} caseId={caseId} exception={e} />
              ))}
            </div>
          </>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  count,
  actions,
  children,
}: {
  title: string;
  count: number | undefined;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="font-heading text-xl font-semibold tracking-[-0.01em]">
          {title}
        </h2>
        {count !== undefined && (
          <span className="rounded-full bg-[#F1F5F9] px-2 font-mono text-xs">
            {count}
          </span>
        )}
        <div className="ml-auto">{actions}</div>
      </div>
      {children}
    </section>
  );
}

const ErrorText = ({ message }: { message: string }) => (
  <p className="text-sm text-[#991B1B]">{message}</p>
);

const Clear = ({ text }: { text: string }) => (
  <p className="flex items-center gap-2 text-sm text-[#64748B]">
    <CheckCircle2Icon className="size-4 text-[#16A34A]" /> {text}
  </p>
);

/** UI brief §4.3 triage card for an unmatched sub-limit. */
function SublimitCard({ caseId, row }: { caseId: string; row: SublimitRow }) {
  const canApprove = useCan("approveSublimit");
  return (
    <article className="flex flex-col gap-3 rounded-md border border-[#E2E8F0] bg-white p-4">
      <header className="flex items-center gap-2">
        <AlertTriangleIcon className="size-4 text-[#F59E0B]" />
        <h3 className="text-xs font-semibold tracking-wider text-[#334155] uppercase">
          Unmatched Procedure Sub-Limit
        </h3>
        <StatusPill label="Review Required" className="ml-auto" />
      </header>
      <dl className="grid grid-cols-[130px_1fr] gap-y-1 text-sm">
        <dt className="text-[#64748B]">Procedure</dt>
        <dd className="font-medium">{row.procedure_name}</dd>
        <dt className="text-[#64748B]">Extracted Amount</dt>
        <dd className="font-mono">{row.extracted_amount_raw}</dd>
        <dt className="text-[#64748B]">Option Matrix</dt>
        <dd className="font-mono text-xs">
          {Object.entries(row.options)
            .map(([k, v]) => `${k.replace("Option ", "Opt ")} ${formatInr(v)}`)
            .join(" | ")}
        </dd>
        {row.evidence.page && (
          <>
            <dt className="text-[#64748B]">Source</dt>
            <dd className="text-xs">Page {row.evidence.page}</dd>
          </>
        )}
      </dl>
      {row.evidence.excerpt && (
        <blockquote className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2 font-mono text-xs">
          {row.evidence.excerpt}
        </blockquote>
      )}
      {canApprove ? (
        <ApproveSublimitForm caseId={caseId} row={row} />
      ) : (
        <p className="text-xs text-[#64748B]">Awaiting underwriter sign-off.</p>
      )}
    </article>
  );
}

function ExceptionCard({
  caseId,
  exception: e,
}: {
  caseId: string;
  exception: DemographyException;
}) {
  const canResolve = useCan("resolveException");
  const [action, setAction] = useState("");
  const resolve = useResolveException(caseId);

  const submit = (isResolved: boolean) =>
    resolve.mutate(
      {
        exceptionId: e.id,
        resolution_action: action.trim(),
        is_resolved: isResolved,
      },
      {
        onSuccess: () => {
          toast.success(
            isResolved ? "Exception resolved and logged" : "Exception reopened",
          );
          setAction("");
        },
        onError: (err) => toast.error(err.message),
      },
    );

  return (
    <article
      className={cn(
        "flex flex-col gap-2 rounded-md border bg-white p-4",
        e.severity === "critical" && !e.is_resolved
          ? "border-[#FECACA]"
          : "border-[#E2E8F0]",
      )}
    >
      <header className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">{e.exception_label}</h3>
        <span
          className={cn(
            "rounded-full px-2 font-mono text-[11px] font-semibold uppercase",
            e.severity === "critical"
              ? "bg-[#FEE2E2] text-[#991B1B]"
              : "bg-[#FFF7ED] text-[#9A3412]",
          )}
        >
          {e.severity}
        </span>
        {e.is_resolved && <StatusPill label="Approved" className="ml-auto" />}
      </header>
      <p className="text-sm text-[#334155]">{e.error_message}</p>
      {e.member_name && (
        <p className="font-mono text-xs text-[#64748B]">
          Row {e.source_row_number} · {e.employee_code} · {e.member_name} ·{" "}
          {e.relationship}
        </p>
      )}
      {e.is_resolved ? (
        <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2 text-xs">
          <p className="text-[#334155]">{e.resolution_action}</p>
          <p className="mt-1 text-[#64748B]">
            Resolved by {e.resolved_by ?? "—"}
          </p>
          {canResolve && (
            <div className="mt-2 flex flex-col gap-2">
              <JustificationField
                id={`reopen-${e.id}`}
                label="Reason to reopen"
                value={action}
                onChange={setAction}
              />
              <Button
                variant="outline"
                size="sm"
                className="w-fit"
                disabled={!justificationOk(action) || resolve.isPending}
                onClick={() => submit(false)}
              >
                Reopen
              </Button>
            </div>
          )}
        </div>
      ) : canResolve ? (
        <div className="flex flex-col gap-2">
          <JustificationField
            id={`resolve-${e.id}`}
            label="Resolution action (mandatory)"
            value={action}
            onChange={setAction}
          />
          <Button
            size="sm"
            className="w-fit"
            disabled={!justificationOk(action) || resolve.isPending}
            onClick={() => submit(true)}
          >
            Resolve & Log
          </Button>
        </div>
      ) : (
        <p className="text-xs text-[#64748B]">
          Raised {formatDateTime(e.created_at)} · awaiting an ops analyst or
          underwriter.
        </p>
      )}
    </article>
  );
}
