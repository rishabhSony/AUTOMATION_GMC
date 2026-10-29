"use client";

import { cn } from "cn";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { useUpdateManualInputs } from "@/lib/api/queries";
import type { ManualInputs } from "@/lib/api/types";

export type ManualField = keyof ManualInputs;

// Quote Review Grid field → `cases` column it edits (PATCH /cases/{id}/manual-inputs).
export const MANUAL_FIELDS: Record<string, ManualField> = {
  "Rater Type": "rater_type",
  "Brokerage %": "brokerage_pct",
  "PIN Code": "pincode",
  State: "state",
  District: "district",
};

const PINCODE_RE = /^[1-9][0-9]{5}$/;

function validate(field: ManualField, value: string): string | null {
  if (field === "pincode" && value && !PINCODE_RE.test(value))
    return "6 digits, not starting with 0";
  if (field === "brokerage_pct" && value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0 || n > 15) return "Between 0 and 15";
  }
  return null;
}

/** "5" → "5.00" on blur (UI brief §3.2); the % sign is shown beside the input. */
const normalize = (field: ManualField, value: string) =>
  field === "brokerage_pct" && value && Number.isFinite(Number(value))
    ? Number(value).toFixed(2)
    : value.trim();

/**
 * Inline editor for the five manual inputs. Commits on Enter or blur; a PIN or
 * District change re-derives Zone server-side, and the parent pulses the Zone row.
 */
export function ManualInputCell({
  caseId,
  field,
  value,
  disabled,
  onZoneChange,
}: {
  caseId: string;
  field: ManualField;
  value: string | null;
  disabled: boolean;
  onZoneChange: (zone: string) => void;
}) {
  const [draft, setDraft] = useState(value ?? "");
  const [flash, setFlash] = useState(false);
  const mutation = useUpdateManualInputs(caseId);
  const error = validate(field, draft);

  useEffect(() => setDraft(value ?? ""), [value]);

  const commit = () => {
    const next = normalize(field, draft);
    setDraft(next);
    if (error || next === (value ?? "")) return;
    if (field === "pincode" && !next) {
      setDraft(value ?? "");
      return; // the API can't clear a PIN back to empty
    }
    mutation.mutate(
      { [field]: next || null },
      {
        onSuccess: (res) => {
          setFlash(true);
          setTimeout(() => setFlash(false), 400);
          if (
            res.changed.length &&
            (field === "pincode" || field === "district" || field === "state")
          ) {
            onZoneChange(res.zone);
            toast.success(
              res.zone_matched_by === "none"
                ? `Zone needs review: no mapping for ${field === "pincode" ? `PIN ${next}` : next}`
                : `Zone updated to ${res.zone} (${res.zone_matched_by === "pincode" ? `PIN ${res.pincode}` : res.district})`,
            );
          }
        },
        onError: (e) => {
          toast.error(e.message);
          setDraft(value ?? "");
        },
      },
    );
  };

  if (disabled)
    return <span className="font-mono text-[13px]">{value ?? "—"}</span>;

  return (
    <div className="flex items-center gap-1.5">
      <Input
        value={draft}
        aria-invalid={!!error}
        title={error ?? undefined}
        inputMode={
          field === "pincode" || field === "brokerage_pct" ? "decimal" : "text"
        }
        maxLength={field === "pincode" ? 6 : 100}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") setDraft(value ?? "");
        }}
        className={cn(
          "h-8 max-w-56 bg-white font-mono text-xs transition-colors duration-150",
          flash && "bg-[#F0FDF4]",
          mutation.isPending && "opacity-60",
        )}
      />
      {field === "brokerage_pct" && (
        <span className="text-xs text-[#64748B]">%</span>
      )}
      {error && <span className="text-[11px] text-[#EF4444]">{error}</span>}
    </div>
  );
}
