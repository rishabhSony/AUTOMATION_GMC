"use client";

import { cn } from "cn";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  JustificationField,
  justificationOk,
} from "@/components/workbench/justification-field";
import { useApproveSublimit } from "@/lib/api/queries";
import type { SublimitOption, SublimitRow } from "@/lib/api/types";
import { formatInr } from "@/lib/format";

const TIERS = ["Option 1", "Option 2", "Option 3", "Option 4"] as const;

/**
 * Underwriter resolution of a sub-limit (PATCH /sublimits/{proc_name}): map it to an
 * Option tier, or retain the exact RFQ amount. Used by the sub-limit tab and triage cards.
 */
export function ApproveSublimitForm({
  caseId,
  row,
  onDone,
}: {
  caseId: string;
  row: SublimitRow;
  onDone?: () => void;
}) {
  const [option, setOption] = useState<SublimitOption | null>(null);
  const [justification, setJustification] = useState("");
  const mutation = useApproveSublimit(caseId);
  const choices: { value: SublimitOption; label: string }[] = [
    ...(row.extracted_amount_raw
      ? [
          {
            value: "unmatched" as const,
            label: `Retain ${row.extracted_amount_raw} (exact RFQ amount)`,
          },
        ]
      : []),
    ...TIERS.map((t, i) => ({
      value: `option_${i + 1}` as SublimitOption,
      label: `Map to ${t} (${formatInr(row.options[t])})`,
    })),
  ];

  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1 text-sm font-medium">Resolution</legend>
        {choices.map((c) => (
          <label
            key={c.value}
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded border px-2.5 py-1.5 text-sm",
              option === c.value
                ? "border-[#0066FF] bg-[#EFF6FF]"
                : "border-[#E2E8F0]",
            )}
          >
            <input
              type="radio"
              name={`resolution-${row.procedure_name}`}
              checked={option === c.value}
              onChange={() => setOption(c.value)}
            />
            {c.label}
          </label>
        ))}
      </fieldset>
      <JustificationField
        id={`sublimit-justification-${row.procedure_name}`}
        label="Underwriting Justification (mandatory)"
        value={justification}
        onChange={setJustification}
      />
      <div className="flex justify-end gap-2">
        {onDone && (
          <Button variant="outline" onClick={onDone}>
            Cancel
          </Button>
        )}
        <Button
          disabled={
            !option || !justificationOk(justification) || mutation.isPending
          }
          onClick={() =>
            option &&
            mutation.mutate(
              {
                procedureName: row.procedure_name,
                matched_option: option,
                justification: justification.trim(),
              },
              {
                onSuccess: () => {
                  toast.success(`${row.procedure_name} approved and logged`);
                  onDone?.();
                },
                onError: (e) => toast.error(e.message),
              },
            )
          }
        >
          Apply Override & Log
        </Button>
      </div>
    </div>
  );
}
