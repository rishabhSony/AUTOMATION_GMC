"use client";

import { cn } from "cn";
import { CopyIcon, FileSearchIcon, PanelRightCloseIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { DocumentPreview } from "@/components/workbench/document-preview";
import { SECTION_LABELS } from "@/components/workbench/sections";
import { StatusPill } from "@/components/workbench/status-pill";
import type { QuoteRow } from "@/lib/api/types";

/** Source Evidence Inspector (UI brief §4.1): citation, verbatim snippet, Pass 2 note. */
export function EvidenceDrawer({
  caseId,
  row,
  onClose,
}: {
  caseId: string;
  row: QuoteRow | undefined;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState(false);
  const canPreview = !!row && !!(row.evidence.file_id || row.evidence.excerpt);
  const showPreview = preview && canPreview;
  return (
    <Sheet
      open={!!row}
      onOpenChange={(open) => {
        if (!open) {
          setPreview(false);
          onClose();
        }
      }}
    >
      <SheetContent
        className={cn(
          showPreview &&
            "sm:max-w-[min(1280px,96vw)] lg:grid lg:grid-cols-[440px_1fr] lg:gap-6",
        )}
      >
        {row && (
          <div className="flex flex-col gap-4">
            <SheetHeader>
              <SheetTitle>Source Evidence Inspector</SheetTitle>
              <SheetDescription>
                {SECTION_LABELS[row.section] ?? row.section} › {row.quote_field}
              </SheetDescription>
            </SheetHeader>

            <Block title="Extracted Value">
              <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 text-sm">
                <dt className="text-[#64748B]">Current</dt>
                <dd className="text-[#334155]">
                  {row.coverage_details ?? "—"}
                </dd>
                <dt className="text-[#64748B]">Proposed</dt>
                <dd className="font-semibold">{row.proposed_details ?? "—"}</dd>
                <dt className="text-[#64748B]">Provenance</dt>
                <dd className="flex items-center gap-2">
                  <StatusPill label={row.source_status} />
                  <span className="text-xs text-[#64748B]">
                    {row.confidence} · {Math.round(row.confidence_score * 100)}%
                  </span>
                </dd>
              </dl>
            </Block>

            <Block title="Document Citation">
              {row.evidence.file ? (
                <p className="text-sm">
                  <span className="font-mono text-xs">{row.evidence.file}</span>
                  {row.evidence.page && (
                    <span className="text-[#64748B]">
                      {" "}
                      · Page {row.evidence.page}
                    </span>
                  )}
                </p>
              ) : (
                <p className="text-sm text-[#64748B]">
                  {row.is_manual_override
                    ? "Entered manually; no document citation."
                    : "No source document cited for this value."}
                </p>
              )}
            </Block>

            {row.evidence.excerpt && (
              <Block title="Verbatim Snippet">
                <blockquote className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-3 font-mono text-xs leading-5 whitespace-pre-wrap">
                  {row.evidence.excerpt}
                </blockquote>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 w-fit"
                  onClick={() =>
                    navigator.clipboard
                      .writeText(row.evidence.excerpt ?? "")
                      .then(() => toast.success("Verbatim text copied"))
                  }
                >
                  <CopyIcon /> Copy Verbatim Text
                </Button>
              </Block>
            )}

            {row.evidence.verification && (
              <Block title="Verification Note">
                <p className="text-sm text-[#334155]">
                  {row.evidence.verification}
                </p>
              </Block>
            )}
            {canPreview && (
              <Button
                variant={showPreview ? "outline" : "default"}
                className="w-fit"
                onClick={() => setPreview((p) => !p)}
              >
                {showPreview ? <PanelRightCloseIcon /> : <FileSearchIcon />}
                {showPreview ? "Hide document" : "View Evidence in Document"}
              </Button>
            )}
          </div>
        )}
        {row && showPreview && (
          <section className="mt-4 flex min-h-0 flex-col gap-2 lg:mt-0">
            <p className="pr-8 text-xs text-[#64748B]">
              {row.evidence.file ?? "Source document"}
              {row.evidence.page && ` · page ${row.evidence.page}`}
            </p>
            <DocumentPreview
              caseId={caseId}
              fileId={row.evidence.file_id}
              extension={row.evidence.file_extension}
              filename={row.evidence.file}
              page={row.evidence.page}
              excerpt={row.evidence.excerpt}
            />
          </section>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Block({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2 border-t border-[#E2E8F0] pt-3">
      <h3 className="text-[11px] font-semibold tracking-wider text-[#64748B] uppercase">
        {title}
      </h3>
      {children}
    </section>
  );
}
