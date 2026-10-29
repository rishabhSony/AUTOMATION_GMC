"use client";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** Mandatory justification, 5–2000 characters (enforced again by the API). */
export const MIN_JUSTIFICATION = 5;

export function JustificationField({
  id,
  value,
  onChange,
  label = "Justification (mandatory)",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        value={value}
        maxLength={2000}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Why is this change correct? This is stored in the audit trail."
      />
    </div>
  );
}

export const justificationOk = (value: string) =>
  value.trim().length >= MIN_JUSTIFICATION;
