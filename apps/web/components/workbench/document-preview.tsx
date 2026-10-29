"use client";

import { useQuery } from "@tanstack/react-query";
import { FileWarningIcon } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, useApi } from "@/lib/api/client";

const TEXT_TYPES = new Set(["md", "txt"]);

/**
 * Inline source-document preview for the evidence drawer.
 * - PDF: the browser's viewer in an iframe, opened at `#page=N`.
 * - TXT/MD: the document text with the verbatim excerpt highlighted and scrolled to.
 * - DOCX, other types, or password-protected uploads (423): the verbatim excerpt only.
 * The file comes from GET /cases/{id}/files/{file_id}/view with the session's auth
 * headers, so it's fetched as a blob rather than pointing the iframe at the API.
 */
export function DocumentPreview({
  caseId,
  fileId,
  extension,
  filename,
  page,
  excerpt,
}: {
  caseId: string;
  fileId: string | null | undefined;
  extension: string | null | undefined;
  filename: string | null;
  page: string | null;
  excerpt: string | null;
}) {
  const api = useApi();
  const ext = (extension ?? filename?.split(".").pop() ?? "").toLowerCase();
  const previewable = !!fileId && (ext === "pdf" || TEXT_TYPES.has(ext));

  const file = useQuery({
    queryKey: ["case", caseId, "file", fileId],
    queryFn: () => api.blob(`/cases/${caseId}/files/${fileId}/view`),
    enabled: previewable,
    staleTime: Infinity,
    retry: false,
  });

  if (!previewable)
    return (
      <Fallback
        excerpt={excerpt}
        reason={
          fileId
            ? `In-browser preview isn't available for .${ext || "?"} files.`
            : "This value has no linked source document."
        }
      />
    );
  if (file.isPending) return <Skeleton className="h-full min-h-96 w-full" />;
  if (file.isError) {
    const locked = file.error instanceof ApiError && file.error.status === 423;
    return (
      <Fallback
        excerpt={excerpt}
        reason={
          locked
            ? "This document is password-protected. Passwords are never stored, so it can't be previewed."
            : `Could not load the document: ${file.error.message}`
        }
      />
    );
  }
  return ext === "pdf" ? (
    <PdfFrame blob={file.data} page={page} filename={filename} />
  ) : (
    <TextDocument blob={file.data} excerpt={excerpt} />
  );
}

function PdfFrame({
  blob,
  page,
  filename,
}: {
  blob: Blob;
  page: string | null;
  filename: string | null;
}) {
  const url = useMemo(() => URL.createObjectURL(blob), [blob]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  const pageNumber = page && /^\d+$/.test(page) ? page : "1";
  return (
    <iframe
      // Re-mount on page change: viewers ignore fragment-only src updates.
      key={pageNumber}
      title={`${filename ?? "Source document"}, page ${pageNumber}`}
      src={`${url}#page=${pageNumber}`}
      className="h-full min-h-[70vh] w-full rounded border border-[#E2E8F0] bg-white"
    />
  );
}

function TextDocument({
  blob,
  excerpt,
}: {
  blob: Blob;
  excerpt: string | null;
}) {
  const { data: text } = useQuery({
    queryKey: ["blob-text", blob.size, excerpt],
    queryFn: () => blob.text(),
    staleTime: Infinity,
  });
  const mark = useRef<HTMLElement>(null);
  useEffect(() => {
    // Block body: newer browsers return a Promise from scrollIntoView, and an effect
    // may only return a cleanup function.
    void mark.current?.scrollIntoView({ block: "center" });
  }, [text]);

  if (text === undefined) return <Skeleton className="h-96 w-full" />;
  const at = excerpt ? text.indexOf(excerpt) : -1;
  return (
    <pre className="h-full min-h-[70vh] overflow-auto rounded border border-[#E2E8F0] bg-white p-4 font-mono text-xs leading-5 whitespace-pre-wrap">
      {at === -1 ? (
        text
      ) : (
        <>
          {text.slice(0, at)}
          <mark ref={mark} className="rounded bg-[#FEF08A] px-0.5">
            {excerpt}
          </mark>
          {text.slice(at + (excerpt?.length ?? 0))}
        </>
      )}
    </pre>
  );
}

function Fallback({
  excerpt,
  reason,
}: {
  excerpt: string | null;
  reason: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-start gap-2 rounded border border-[#FDE68A] bg-[#FEF3C7] p-3 text-xs text-[#92400E]">
        <FileWarningIcon className="mt-0.5 size-4 shrink-0" />
        {reason} Showing the verbatim excerpt extracted from the document
        instead.
      </p>
      <blockquote className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-4 font-mono text-xs leading-5 whitespace-pre-wrap">
        {excerpt ?? "No verbatim excerpt was recorded for this field."}
      </blockquote>
    </div>
  );
}
