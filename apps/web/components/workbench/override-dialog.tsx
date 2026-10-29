"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  JustificationField,
  justificationOk,
} from "@/components/workbench/justification-field";
import { useOverrideField } from "@/lib/api/queries";
import type { QuoteRow } from "@/lib/api/types";

/** Manual override of a quote field (PATCH /extractions/{field_name}). */
export function OverrideDialog({
  caseId,
  row,
  onClose,
}: {
  caseId: string;
  row: QuoteRow | undefined;
  onClose: () => void;
}) {
  return (
    <Dialog open={!!row} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        {row && (
          <OverrideForm
            key={row.quote_field}
            caseId={caseId}
            row={row}
            onDone={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function OverrideForm({
  caseId,
  row,
  onDone,
}: {
  caseId: string;
  row: QuoteRow;
  onDone: () => void;
}) {
  const [coverage, setCoverage] = useState(row.coverage_details ?? "");
  const [proposed, setProposed] = useState(row.proposed_details ?? "");
  const [justification, setJustification] = useState("");
  const mutation = useOverrideField(caseId);

  const changes = {
    ...(coverage !== (row.coverage_details ?? "") && {
      coverage_details: coverage || null,
    }),
    ...(proposed !== (row.proposed_details ?? "") && {
      proposed_details: proposed || null,
    }),
  };
  const canSave =
    Object.keys(changes).length > 0 && justificationOk(justification);

  return (
    <>
      <DialogHeader>
        <DialogTitle>Override “{row.quote_field}”</DialogTitle>
        <DialogDescription>
          The field becomes Manual / High confidence and is never overwritten by
          a re-extraction.
        </DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="override-coverage">Coverage Details (current)</Label>
        <Textarea
          id="override-coverage"
          value={coverage}
          onChange={(e) => setCoverage(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="override-proposed">Proposed Details (requested)</Label>
        <Textarea
          id="override-proposed"
          value={proposed}
          onChange={(e) => setProposed(e.target.value)}
        />
      </div>
      <JustificationField
        id="override-justification"
        value={justification}
        onChange={setJustification}
      />
      <DialogFooter>
        <Button variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button
          disabled={!canSave || mutation.isPending}
          onClick={() =>
            mutation.mutate(
              {
                fieldName: row.quote_field,
                justification: justification.trim(),
                ...changes,
              },
              {
                onSuccess: () => {
                  toast.success(`${row.quote_field} overridden and logged`);
                  onDone();
                },
                onError: (e) => toast.error(e.message),
              },
            )
          }
        >
          Apply Override & Log
        </Button>
      </DialogFooter>
    </>
  );
}
