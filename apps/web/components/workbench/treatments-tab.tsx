"use client";

import { ArrowUpRightIcon, PencilIcon } from "lucide-react";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCan } from "@/components/providers/session-user";
import { EvidenceDrawer } from "@/components/workbench/evidence-drawer";
import { OverrideDialog } from "@/components/workbench/override-dialog";
import { StatusPill } from "@/components/workbench/status-pill";
import { useExtractions } from "@/lib/api/queries";
import type { QuoteRow } from "@/lib/api/types";

/**
 * BRD §7.1 modern treatments, in registry order (mirrors `modern_treatments` in
 * services/backend/app/services/field_registry.py). `irdai` marks the 12 methods in
 * IRDAI's standardised modern-treatment list; BRD items 6 and 7 (intravitreal
 * injections) are one IRDAI item. The docs give no IRDAI codes, so the reference shown
 * is the BRD §7.1 item number.
 */
const TREATMENTS: { name: string; irdai: boolean }[] = [
  { name: "Uterine Artery Embolization and HIFU", irdai: true },
  { name: "Balloon Sinuplasty", irdai: true },
  { name: "Deep Brain Stimulation", irdai: true },
  { name: "Oral Chemotherapy", irdai: true },
  {
    name: "Immunotherapy including Monoclonal Antibody Injection",
    irdai: true,
  },
  { name: "Intravitreal Injections except Lucentis", irdai: true },
  { name: "Intravitreal Injections", irdai: true },
  { name: "Robotic Surgeries", irdai: true },
  {
    name: "Vaporisation of the Prostate (Green Laser / Holmium Laser)",
    irdai: true,
  },
  { name: "Bronchial Thermoplasty", irdai: true },
  { name: "Stereotactic Radiosurgery", irdai: true },
  { name: "Intraoperative Neuro Monitoring (IONM)", irdai: true },
  { name: "Stem Cell Therapy / Treatment", irdai: true },
  { name: "Gamma Knife / CyberKnife Surgery", irdai: false },
  { name: "Remicade / Avastin Injection", irdai: false },
  { name: "Biodegradable Stent", irdai: false },
  { name: "Cochlear Implant Treatment", irdai: false },
  { name: "Lucentis Injection", irdai: false },
  { name: "Functional Endoscopic Sinus Surgery (FESS)", irdai: false },
  {
    name: "Ayurvedic Treatment (Inpatient Modern Administration)",
    irdai: false,
  },
];

// Display-only fallback when the RFQ states nothing for a treatment; never stored.
const DEFAULT_COVER = "Covered up to Base SI";

function placeholderRow(name: string): QuoteRow {
  return {
    id: `treatment-${name}`,
    section: "modern_treatments",
    quote_field: name,
    coverage_details: null,
    proposed_details: null,
    source_status: "Not Found",
    confidence: "Low",
    confidence_score: 0,
    is_manual_override: false,
    evidence: { file: null, page: null, excerpt: null, verification: null },
  };
}

export function TreatmentsWorkbench({ caseId }: { caseId: string }) {
  const grid = useExtractions(caseId);
  const canEdit = useCan("editQuote");
  const [irdaiOnly, setIrdaiOnly] = useQueryState(
    "irdai",
    parseAsBoolean.withDefault(false),
  );
  const [evidenceField, setEvidenceField] = useQueryState(
    "evidence",
    parseAsString,
  );
  const [overrideField, setOverrideField] = useState<string | null>(null);

  if (grid.isError)
    return <p className="text-sm text-[#991B1B]">{grid.error.message}</p>;
  if (grid.isPending)
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 10 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );

  const byName = new Map(grid.data.rows.map((r) => [r.quote_field, r]));
  const rows = TREATMENTS.map((t, i) => ({
    ...t,
    ref: `BRD 7.1-${String(i + 1).padStart(2, "0")}`,
    row: byName.get(t.name) ?? placeholderRow(t.name),
  })).filter((t) => !irdaiOnly || t.irdai);
  const stated = rows.filter(
    (t) => t.row.proposed_details || t.row.coverage_details,
  ).length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <h2 className="font-heading text-xl font-semibold tracking-[-0.01em]">
          Modern Treatments
        </h2>
        <span className="text-xs text-[#64748B]">
          {stated} of {rows.length} stated in the RFQ
        </span>
        <label className="ml-auto flex items-center gap-2 text-xs text-[#334155]">
          <input
            type="checkbox"
            checked={irdaiOnly}
            onChange={(e) => setIrdaiOnly(e.target.checked || null)}
          />
          IRDAI standardised list only
        </label>
      </div>

      <div className="overflow-x-auto rounded-md border border-[#E2E8F0] bg-white">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-left text-xs text-[#64748B]">
            <tr>
              <th className="h-9 w-[38%] px-3 font-medium">
                Treatment &amp; Reference
              </th>
              <th className="w-[38%] px-3 font-medium">
                Extracted Sub-limit / Coverage Condition
              </th>
              <th className="px-3 font-medium">Evidence &amp; Override</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ name, irdai, ref, row }) => {
              const value = row.proposed_details ?? row.coverage_details;
              return (
                <tr
                  key={name}
                  className="border-b border-[#E2E8F0] align-top last:border-0"
                >
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{name}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px] text-[#64748B]">
                      {ref}
                      {irdai && (
                        <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-1.5 font-semibold text-[#1E40AF]">
                          IRDAI
                        </span>
                      )}
                    </p>
                  </td>
                  <td className="px-3 py-2.5">
                    {value ? (
                      <>
                        <p className="font-semibold">{value}</p>
                        {row.coverage_details && row.proposed_details && (
                          <p className="text-xs text-[#64748B]">
                            Current: {row.coverage_details}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="text-[#334155]">
                        {DEFAULT_COVER}
                        <span className="ml-2 text-xs text-[#64748B]">
                          (default · not stated in RFQ)
                        </span>
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill
                        label={value ? row.source_status : "Default Data"}
                      />
                      {row.evidence.excerpt || row.evidence.verification ? (
                        <button
                          type="button"
                          onClick={() => setEvidenceField(name)}
                          className="flex items-center gap-1 text-xs text-[#0052CC] hover:underline"
                        >
                          {row.evidence.page
                            ? `Page ${row.evidence.page}`
                            : "Evidence"}
                          <ArrowUpRightIcon className="size-3" />
                        </button>
                      ) : null}
                      {canEdit && (
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          title="Override with justification"
                          onClick={() => setOverrideField(name)}
                        >
                          <PencilIcon />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <EvidenceDrawer
        row={evidenceField ? byName.get(evidenceField) : undefined}
        onClose={() => setEvidenceField(null)}
      />
      <OverrideDialog
        caseId={caseId}
        row={
          overrideField
            ? (byName.get(overrideField) ?? placeholderRow(overrideField))
            : undefined
        }
        onClose={() => setOverrideField(null)}
      />
    </div>
  );
}
