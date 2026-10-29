"use client";

import { useQueryClient } from "@tanstack/react-query";
import { cn } from "cn";
import {
  CheckCircle2Icon,
  CircleDashedIcon,
  CircleIcon,
  Loader2Icon,
  MinusCircleIcon,
  XCircleIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePipelineLauncher } from "@/components/intake/use-pipeline-launcher";
import { useCan } from "@/components/providers/session-user";
import { queryKeys, usePipelineStatus } from "@/lib/api/queries";
import type { PipelineStage } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

const ICONS = {
  pending: <CircleIcon className="size-5 text-[#CBD5E1]" />,
  running: <Loader2Icon className="size-5 animate-spin text-[#0066FF]" />,
  done: <CheckCircle2Icon className="size-5 text-[#16A34A]" />,
  skipped: <MinusCircleIcon className="size-5 text-[#94A3B8]" />,
  failed: <XCircleIcon className="size-5 text-[#EF4444]" />,
};

const seconds = (s: PipelineStage) =>
  s.started_at && s.finished_at
    ? `${((Date.parse(s.finished_at) - Date.parse(s.started_at)) / 1000).toFixed(1)} s`
    : null;

/** Live 4-stage pipeline (App Flow route 7); polls /pipeline-status while it runs. */
export function PipelineScreen({ caseId }: { caseId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const canStart = useCan("editQuote");
  const { data, isPending, isError, error } = usePipelineStatus(caseId);
  const launcher = usePipelineLauncher(caseId, {
    onStarted: () => toast.success("Processing started"),
  });
  const redirected = useRef(false);

  const finished =
    data?.terminal && data.in_memory_run && data.status !== "failed";
  useEffect(() => {
    if (!finished || redirected.current) return;
    redirected.current = true;
    void queryClient.invalidateQueries({ queryKey: queryKeys.case(caseId) });
    toast.success("Pipeline complete. Opening the quote review.");
    const t = setTimeout(() => router.replace(`/cases/${caseId}/quote`), 1200);
    return () => clearTimeout(t);
  }, [finished, caseId, queryClient, router]);

  if (isError) return <p className="text-sm text-[#991B1B]">{error.message}</p>;
  if (isPending) return <Skeleton className="h-64 w-full" />;

  const running =
    data.status === "processing" && data.in_memory_run && !data.terminal;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold tracking-[-0.01em]">
          Ingestion Pipeline
        </h2>
        {data.started_at && (
          <span className="font-mono text-xs text-[#64748B]">
            Started {formatDateTime(data.started_at)}
          </span>
        )}
      </div>

      <ol className="flex flex-col rounded-md border border-[#E2E8F0] bg-white">
        {data.stages.map((s, i) => (
          <li
            key={s.key}
            className={cn(
              "flex gap-3 border-b border-[#E2E8F0] px-4 py-3.5 last:border-0",
              s.state === "running" && "bg-[#EFF6FF]/60",
            )}
          >
            <span className="mt-0.5">
              {data.in_memory_run
                ? ICONS[s.state]
                : ICONS[s.state === "done" ? "done" : "pending"]}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <p className="text-sm font-medium">
                <span className="mr-2 font-mono text-xs text-[#64748B]">
                  {i + 1}
                </span>
                {s.label}
              </p>
              {s.detail && (
                <p
                  className={cn(
                    "text-xs",
                    s.state === "failed" ? "text-[#991B1B]" : "text-[#64748B]",
                  )}
                >
                  {s.detail}
                </p>
              )}
            </div>
            {seconds(s) && (
              <span className="font-mono text-xs text-[#64748B]">
                {seconds(s)}
              </span>
            )}
          </li>
        ))}
      </ol>

      {running && (
        <p className="flex items-center gap-2 text-sm text-[#334155]">
          <CircleDashedIcon className="size-4 animate-spin" /> Processing… this
          page updates every second and opens the quote review when done.
        </p>
      )}
      {data.status === "failed" && (
        <p className="rounded-md border border-[#FECACA] bg-[#FEE2E2] p-3 text-sm text-[#991B1B]">
          The pipeline failed{data.error ? `: ${data.error}` : "."} Fix the
          input and run it again.
        </p>
      )}
      {!data.in_memory_run && data.terminal && data.status !== "failed" && (
        <p className="text-sm text-[#334155]">
          This case has been processed. Its stage log isn&apos;t available after
          an API restart, but the results are in the workbench tabs.
        </p>
      )}
      {!data.in_memory_run && data.status === "processing" && (
        <p className="text-sm text-[#9A3412]">
          The API restarted during processing; start the run again.
        </p>
      )}

      {data.can_start && !running && (
        <div className="flex items-center gap-3">
          {canStart ? (
            <Button
              disabled={launcher.pending}
              onClick={() => launcher.launch()}
            >
              {launcher.pending
                ? "Inspecting files…"
                : data.status === "draft" || data.status === "uploaded"
                  ? "Start processing"
                  : "Run again"}
            </Button>
          ) : (
            <p className="text-sm text-[#64748B]">
              A Sales RM, Underwriter or Admin starts processing.
            </p>
          )}
          {data.terminal && data.status !== "failed" && (
            <Button
              variant="outline"
              onClick={() => router.push(`/cases/${caseId}/quote`)}
            >
              Open quote review
            </Button>
          )}
        </div>
      )}
      {launcher.modal}
    </div>
  );
}
