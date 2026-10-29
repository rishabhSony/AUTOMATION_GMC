"use client";

import { useState } from "react";
import { toast } from "sonner";

import { PasswordModal } from "@/components/intake/password-modal";
import { ApiError } from "@/lib/api/client";
import { useStartPipeline } from "@/lib/api/queries";
import type { LockedFile } from "@/lib/api/types";

type Detail = { code?: string; files?: LockedFile[]; file_id?: string };

/**
 * Starts POST /cases/{id}/process. A 423 opens the password modal for the locked files;
 * a 422 `invalid_password` shakes the field and counts the attempt. Shared by /cases/new
 * and the pipeline screen.
 */
export function usePipelineLauncher(
  caseId: string | null,
  {
    onStarted,
    onCancel,
  }: { onStarted: (caseId: string) => void; onCancel?: () => void },
) {
  const start = useStartPipeline();
  const [activeCaseId, setActiveCaseId] = useState<string | null>(caseId);
  const [locked, setLocked] = useState<LockedFile[]>([]);
  const [invalidFileId, setInvalidFileId] = useState<string | null>(null);
  const [attempts, setAttempts] = useState<Record<string, number>>({});

  /** `id` overrides the hook's case (e.g. a case created a moment ago on /cases/new). */
  const launch = (
    passwords: Record<string, string> = {},
    id = activeCaseId ?? caseId,
  ) => {
    if (!id) return;
    setActiveCaseId(id);
    start.mutate(
      { caseId: id, passwords },
      {
        onSuccess: () => {
          setLocked([]);
          setInvalidFileId(null);
          onStarted(id);
        },
        onError: (error) => {
          const detail = (
            error instanceof ApiError ? error.detail : null
          ) as Detail | null;
          if (
            error instanceof ApiError &&
            error.status === 423 &&
            detail?.files
          ) {
            setLocked(detail.files);
            setInvalidFileId(null);
          } else if (detail?.code === "invalid_password" && detail.file_id) {
            const fileId = detail.file_id;
            setInvalidFileId(fileId);
            setAttempts((a) => ({ ...a, [fileId]: (a[fileId] ?? 0) + 1 }));
          } else {
            toast.error(`Could not start processing: ${error.message}`);
          }
        },
      },
    );
  };

  const modal = (
    <PasswordModal
      files={locked}
      invalidFileId={invalidFileId}
      attempts={attempts}
      submitting={start.isPending}
      onSubmit={(passwords) => launch(passwords)}
      onCancel={() => {
        setLocked([]);
        setInvalidFileId(null);
        onCancel?.();
      }}
    />
  );

  return { launch, pending: start.isPending, modal };
}
