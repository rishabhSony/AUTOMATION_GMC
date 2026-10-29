"use client";

import { cn } from "cn";
import { EyeIcon, EyeOffIcon, LockIcon, ShieldCheckIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { LockedFile } from "@/lib/api/types";

export const MAX_ATTEMPTS = 3;

/**
 * Zero-persistence decryption challenge (UI brief §4.2). Passwords live in this
 * component's state only until they're sent with POST /process, then are cleared.
 */
export function PasswordModal({
  files,
  invalidFileId,
  attempts,
  submitting,
  onSubmit,
  onCancel,
}: {
  files: LockedFile[];
  invalidFileId: string | null;
  attempts: Record<string, number>;
  submitting: boolean;
  onSubmit: (passwords: Record<string, string>) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState(false);
  const [shakeKey, setShakeKey] = useState(0);
  const exhausted = files.some(
    (f) => (attempts[f.file_id] ?? 0) >= MAX_ATTEMPTS,
  );
  const ready = files.every((f) => values[f.file_id]);

  const submit = () => {
    onSubmit(values);
    setValues({}); // never kept after the request
    setShakeKey((k) => k + 1);
  };

  return (
    <Dialog
      open={files.length > 0}
      onOpenChange={(open) => !open && onCancel()}
    >
      <DialogContent
        className="sm:max-w-md"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LockIcon className="size-4" /> Protected File Detected
          </DialogTitle>
          <DialogDescription>
            {files.length === 1
              ? `'${files[0].filename}' is encrypted.`
              : `${files.length} files are encrypted.`}{" "}
            Enter the decryption password to proceed with intake.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready && !submitting && !exhausted) submit();
          }}
        >
          {files.map((f) => {
            const wrong = invalidFileId === f.file_id;
            const tries = attempts[f.file_id] ?? 0;
            return (
              <div
                key={wrong ? `${f.file_id}-${shakeKey}` : f.file_id}
                className={cn(
                  "flex flex-col gap-1.5",
                  wrong && "animate-qp-shake",
                )}
              >
                <Label htmlFor={`pw-${f.file_id}`}>
                  Password{files.length > 1 && ` · ${f.filename}`}
                </Label>
                <div className="flex gap-1.5">
                  <Input
                    id={`pw-${f.file_id}`}
                    type={visible ? "text" : "password"}
                    autoComplete="off"
                    value={values[f.file_id] ?? ""}
                    aria-invalid={wrong}
                    className={cn(wrong && "border-[#EF4444]")}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [f.file_id]: e.target.value }))
                    }
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={visible ? "Hide password" : "Show password"}
                    onClick={() => setVisible((v) => !v)}
                  >
                    {visible ? <EyeOffIcon /> : <EyeIcon />}
                  </Button>
                </div>
                {wrong && (
                  <p className="text-xs text-[#EF4444]">
                    Incorrect password (Attempt {tries} of {MAX_ATTEMPTS})
                  </p>
                )}
              </div>
            );
          })}

          <p className="flex gap-2 rounded-md border border-[#BBF7D0] bg-[#F0FDF4] p-2.5 text-xs text-[#166534]">
            <ShieldCheckIcon className="size-4 shrink-0" />
            <span>
              <strong>Zero-Persistence Security Notice:</strong> passwords are
              used to decrypt in ephemeral RAM only and are never saved to disk,
              database, or logs.
            </span>
          </p>
          {exhausted && (
            <p className="text-xs text-[#991B1B]">
              Too many incorrect attempts. Check the password with the client
              and try again from the pipeline screen.
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={!ready || submitting || exhausted}>
              {submitting ? "Decrypting…" : "Decrypt & Continue"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
