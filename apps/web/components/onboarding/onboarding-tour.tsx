"use client";

import { cn } from "cn";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UploadCloudIcon,
  UsersIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useCan, useSessionUser } from "@/components/providers/session-user";
import { markOnboardingDone } from "@/lib/onboarding";

const STEPS = [
  {
    icon: UploadCloudIcon,
    title: "Smart Case Intake",
    lead: "Start a case from the RFQ pack and the member census in one go.",
    points: [
      "Drag and drop RFQ documents (PDF, DOCX, TXT, MD) and census sheets (XLSX, XLS, CSV); each file is tagged automatically.",
      "Password-protected files open a decryption prompt. The password is used in memory only, never saved to disk, the database or logs.",
      "Intake details such as the policy start date, incumbent insurer, brokerage and PIN code are captured up front.",
    ],
  },
  {
    icon: UsersIcon,
    title: "Vectorized Demography Engine",
    lead: "Messy rosters become a clean, strictly ordered 7-column census.",
    points: [
      "Columns are always Age · Date of Birth · Sum Insured · Relationship · Name · EmpCode · Gender.",
      "Ages are ⌊(basis date − DOB) / 365.25⌋; switch the basis between today and the policy start date and recalculate instantly.",
      "Under-18 employees, orphan dependants, duplicates and age/DOB mismatches land in an exceptions queue for triage.",
    ],
  },
  {
    icon: SparklesIcon,
    title: "Two-Pass AI Quote Review",
    lead: "The RFQ is read once by the extractor and checked again by a verifier.",
    points: [
      "Every quote field shows Coverage (current) vs Proposed details, a source status and a confidence, with the verbatim evidence one click away.",
      "Values whose evidence isn't found in the document are demoted to Review Required.",
      "The 19 procedure sub-limits are matched to Options 1–4 by exact deterministic rules, never by the AI.",
    ],
  },
  {
    icon: ShieldCheckIcon,
    title: "Underwriter Governance & Audit",
    lead: "Every change is justified, attributed and permanent.",
    points: [
      "Overrides, sub-limit approvals and exception resolutions need a written justification and are appended to an immutable audit trail.",
      "Row-level security enforces role boundaries: Sales RMs see their assigned cases; Underwriters and Admins see all cases; Ops Analysts see all cases for demography work.",
      "Only Underwriters and Admins can approve unmatched sub-limits; exports are logged too.",
    ],
  },
] as const;

export function OnboardingTour() {
  const router = useRouter();
  const user = useSessionUser();
  const canCreate = useCan("editQuote");
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const Icon = current.icon;
  const last = step === STEPS.length - 1;

  const finish = (href: string) => {
    markOnboardingDone();
    router.push(href);
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-6 pt-12">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[#64748B]">
          Welcome to QuotePulse GMC, {user.fullName.split(" ")[0]}
        </p>
        <button
          type="button"
          onClick={() => finish("/dashboard")}
          className="text-sm text-[#64748B] hover:text-[#0F172A]"
        >
          Skip tour
        </button>
      </div>

      <article
        key={step}
        className="flex flex-col gap-5 rounded-md border border-[#E2E8F0] bg-white p-8 shadow-xs animate-in fade-in-0 duration-150"
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-[#EFF6FF] text-[#0052CC]">
            <Icon className="size-5" />
          </span>
          <div>
            <p className="font-mono text-xs text-[#64748B]">
              Step {step + 1} of {STEPS.length}
            </p>
            <h1 className="font-heading text-xl font-semibold tracking-[-0.01em]">
              {current.title}
            </h1>
          </div>
        </div>
        <p className="text-[15px] text-[#334155]">{current.lead}</p>
        <ul className="flex flex-col gap-2.5 text-sm text-[#334155]">
          {current.points.map((p) => (
            <li key={p} className="flex gap-2">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-[#0066FF]" />
              {p}
            </li>
          ))}
        </ul>
      </article>

      <div className="flex items-center justify-between">
        <div className="flex gap-1.5" role="tablist" aria-label="Tour steps">
          {STEPS.map((s, i) => (
            <button
              key={s.title}
              type="button"
              role="tab"
              aria-selected={i === step}
              aria-label={s.title}
              onClick={() => setStep(i)}
              className={cn(
                "h-2 rounded-full transition-all duration-150",
                i === step ? "w-6 bg-[#0066FF]" : "w-2 bg-[#CBD5E1]",
              )}
            />
          ))}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={step === 0}
            onClick={() => setStep((s) => s - 1)}
          >
            <ArrowLeftIcon /> Back
          </Button>
          {last ? (
            <>
              {canCreate && (
                <Button variant="outline" onClick={() => finish("/cases/new")}>
                  Create first case
                </Button>
              )}
              <Button onClick={() => finish("/dashboard")}>
                Launch Workbench
              </Button>
            </>
          ) : (
            <Button onClick={() => setStep((s) => s + 1)}>
              Next <ArrowRightIcon />
            </Button>
          )}
        </div>
      </div>
    </main>
  );
}
