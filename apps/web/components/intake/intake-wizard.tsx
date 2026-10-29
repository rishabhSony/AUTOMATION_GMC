"use client";

import { cn } from "cn";
import {
  CheckIcon,
  ChevronRightIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  UploadCloudIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePipelineLauncher } from "@/components/intake/use-pipeline-launcher";
import { useCan } from "@/components/providers/session-user";
import { StatusPill } from "@/components/workbench/status-pill";
import {
  useCreateCase,
  useUploadFiles,
  useZoneLookup,
} from "@/lib/api/queries";
import type { CaseIntake } from "@/lib/api/types";
import { isoToDdMmYyyy } from "@/lib/format";

const STEPS = ["Case Details", "Documents", "Review & Submit"] as const;
const RFQ_EXT = ["pdf", "docx", "txt", "md"];
const CENSUS_EXT = ["xlsx", "xls", "csv"];
const ACCEPT = [...RFQ_EXT, ...CENSUS_EXT].map((e) => `.${e}`).join(",");
const MAX_BYTES = 50 * 1024 * 1024; // API MAX_UPLOAD_BYTES
const PINCODE_RE = /^[1-9][0-9]{5}$/;

const ext = (name: string) => name.split(".").pop()?.toLowerCase() ?? "";
const isCensus = (f: File) => CENSUS_EXT.includes(ext(f.name));

type Form = {
  company_name: string;
  proposal_start_date: string;
  policy_tenure: string;
  incumbent_insurer: string;
  brokerage_pct: string;
  rater_type: string;
  pincode: string;
};

const EMPTY: Form = {
  company_name: "",
  proposal_start_date: "",
  policy_tenure: "1 Year",
  incumbent_insurer: "",
  brokerage_pct: "",
  rater_type: "-",
  pincode: "",
};

function formErrors(f: Form): Partial<Record<keyof Form, string>> {
  const errors: Partial<Record<keyof Form, string>> = {};
  if (!f.company_name.trim()) errors.company_name = "Required";
  if (f.pincode && !PINCODE_RE.test(f.pincode))
    errors.pincode = "6 digits, not starting with 0";
  if (f.brokerage_pct) {
    const n = Number(f.brokerage_pct);
    if (!Number.isFinite(n) || n < 0 || n > 15)
      errors.brokerage_pct = "Between 0 and 15";
  }
  return errors;
}

export function IntakeWizard() {
  const router = useRouter();
  const canCreate = useCan("editQuote");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Form>(EMPTY);
  const [files, setFiles] = useState<File[]>([]);
  const [caseId, setCaseId] = useState<string | null>(null);
  const create = useCreateCase();
  const upload = useUploadFiles();
  const launcher = usePipelineLauncher(caseId, {
    onStarted: (id) => router.push(`/cases/${id}/pipeline`),
    // The case exists; processing can be retried from its pipeline screen.
    onCancel: () => caseId && router.push(`/cases/${caseId}/pipeline`),
  });

  const errors = formErrors(form);
  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const busy = create.isPending || upload.isPending || launcher.pending;

  if (!canCreate)
    return (
      <main className="mx-auto max-w-3xl p-6 text-sm text-[#64748B]">
        Your role can&apos;t create quotation cases (Doc 05 §8: Sales RM,
        Underwriter, Admin).
      </main>
    );

  const submit = async () => {
    try {
      let id = caseId;
      if (!id) {
        const body: CaseIntake = {
          company_name: form.company_name.trim(),
          proposal_start_date: form.proposal_start_date || null,
          policy_tenure: form.policy_tenure.trim() || null,
          brokerage_pct: form.brokerage_pct
            ? Number(form.brokerage_pct).toFixed(2)
            : null,
          rater_type: form.rater_type.trim() || null,
          pincode: form.pincode || null,
          ...(form.incumbent_insurer.trim() && {
            incumbent_insurer: form.incumbent_insurer.trim(),
          }),
        };
        id = (await create.mutateAsync(body)).id;
        setCaseId(id);
        const uploaded = await upload.mutateAsync({ caseId: id, files });
        const locked = uploaded.files.filter((f) => f.is_encrypted).length;
        toast.success(
          `Case created · ${uploaded.files.length} file(s) uploaded` +
            (locked ? ` · ${locked} password-protected` : ""),
        );
      }
      launcher.launch({}, id); // 423 → password modal
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <nav className="flex items-center gap-1 text-xs text-[#64748B]">
          <Link href="/dashboard" className="hover:text-[#0F172A]">
            Dashboard
          </Link>
          <ChevronRightIcon className="size-3" />
          <span>New Quote Case</span>
        </nav>
        <h1 className="font-heading text-[28px] leading-9 font-bold tracking-[-0.02em]">
          New Quote Case
        </h1>
      </div>

      <ol className="flex items-center gap-2 text-sm">
        {STEPS.map((label, i) => (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border font-mono text-xs",
                i < step && "border-[#16A34A] bg-[#16A34A] text-white",
                i === step && "border-[#0066FF] bg-[#0066FF] text-white",
                i > step && "border-[#E2E8F0] text-[#64748B]",
              )}
            >
              {i < step ? <CheckIcon className="size-3.5" /> : i + 1}
            </span>
            <span className={i === step ? "font-medium" : "text-[#64748B]"}>
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span className="mx-1 h-px w-8 bg-[#E2E8F0]" />
            )}
          </li>
        ))}
      </ol>

      <section className="rounded-md border border-[#E2E8F0] bg-white p-5">
        {step === 0 && <DetailsStep form={form} errors={errors} set={set} />}
        {step === 1 && <FilesStep files={files} setFiles={setFiles} />}
        {step === 2 && <ReviewStep form={form} files={files} />}
      </section>

      <div className="flex justify-between">
        <Button
          variant="outline"
          disabled={step === 0 || busy || !!caseId}
          onClick={() => setStep((s) => s - 1)}
        >
          Back
        </Button>
        {step < 2 ? (
          <Button
            disabled={
              (step === 0 && Object.keys(errors).length > 0) ||
              (step === 1 && files.length === 0)
            }
            onClick={() => setStep((s) => s + 1)}
          >
            Continue
          </Button>
        ) : (
          <Button disabled={busy} onClick={submit}>
            {create.isPending
              ? "Creating case…"
              : upload.isPending
                ? "Uploading…"
                : launcher.pending
                  ? "Inspecting files…"
                  : caseId
                    ? "Retry processing"
                    : "Create case & start processing"}
          </Button>
        )}
      </div>
      {launcher.modal}
    </main>
  );
}

function Field({
  label,
  id,
  error,
  hint,
  children,
}: {
  label: string;
  id: string;
  error?: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p className="text-xs text-[#EF4444]">{error}</p>
      ) : (
        hint && <div className="text-xs text-[#64748B]">{hint}</div>
      )}
    </div>
  );
}

function DetailsStep({
  form,
  errors,
  set,
}: {
  form: Form;
  errors: Partial<Record<keyof Form, string>>;
  set: (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const validPin = PINCODE_RE.test(form.pincode) ? form.pincode : null;
  const zone = useZoneLookup(validPin);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field label="Company Name *" id="company" error={errors.company_name}>
          <Input
            id="company"
            value={form.company_name}
            onChange={set("company_name")}
          />
        </Field>
      </div>
      <Field
        label="Policy Start Date"
        id="start"
        hint="Sets the age basis to Policy Proposal Start Date"
      >
        <Input
          id="start"
          type="date"
          value={form.proposal_start_date}
          onChange={set("proposal_start_date")}
          className="font-mono"
        />
      </Field>
      <Field label="Policy Tenure" id="tenure">
        <Input
          id="tenure"
          value={form.policy_tenure}
          onChange={set("policy_tenure")}
        />
      </Field>
      <div className="sm:col-span-2">
        <Field
          label="Incumbent Insurer"
          id="insurer"
          hint="Leave blank for New Business. Any insurer → Roll Over; Bajaj → Own Renewal (BRD §6.1)."
        >
          <Input
            id="insurer"
            value={form.incumbent_insurer}
            onChange={set("incumbent_insurer")}
          />
        </Field>
      </div>
      <Field label="Brokerage %" id="brokerage" error={errors.brokerage_pct}>
        <Input
          id="brokerage"
          inputMode="decimal"
          value={form.brokerage_pct}
          onChange={set("brokerage_pct")}
          className="font-mono"
          placeholder="0.00"
        />
      </Field>
      <Field label="Rater Type" id="rater">
        <Input
          id="rater"
          value={form.rater_type}
          onChange={set("rater_type")}
          className="font-mono"
        />
      </Field>
      <Field
        label="PIN Code"
        id="pincode"
        error={errors.pincode}
        hint={
          validPin && (
            <span className="flex items-center gap-1.5">
              Zone:
              {zone.data ? (
                <StatusPill
                  label={
                    zone.data.matched_by === "none"
                      ? "Review Required"
                      : zone.data.zone
                  }
                />
              ) : (
                "…"
              )}
              {zone.data?.matched_by === "none" && "no zone_master mapping yet"}
            </span>
          )
        }
      >
        <Input
          id="pincode"
          inputMode="numeric"
          maxLength={6}
          value={form.pincode}
          onChange={set("pincode")}
          className="font-mono"
        />
      </Field>
    </div>
  );
}

function FilesStep({
  files,
  setFiles,
}: {
  files: File[];
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const add = (list: FileList | null) => {
    if (!list) return;
    const accepted: File[] = [];
    for (const f of Array.from(list)) {
      if (![...RFQ_EXT, ...CENSUS_EXT].includes(ext(f.name)))
        toast.error(`${f.name}: .${ext(f.name)} is not supported`);
      else if (f.size > MAX_BYTES)
        toast.error(`${f.name} is larger than 50 MB`);
      else accepted.push(f);
    }
    setFiles((current) => [
      ...current.filter((c) => !accepted.some((a) => a.name === c.name)),
      ...accepted,
    ]);
  };

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-md border-2 border-dashed px-6 py-10 text-center transition-colors duration-150",
          dragging
            ? "border-[#0066FF] bg-[#EFF6FF]"
            : "border-[#CBD5E1] hover:bg-[#F8FAFC]",
        )}
      >
        <UploadCloudIcon className="size-8 text-[#64748B]" />
        <span className="text-sm font-medium">
          Drop RFQ and census files here, or browse
        </span>
        <span className="text-xs text-[#64748B]">
          RFQ: PDF, DOCX, TXT, MD · Census: XLSX, XLS, CSV · up to 50 MB each.
          Password-protected files are fine.
        </span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        data-testid="file-input"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      {files.length > 0 && (
        <ul className="divide-y divide-[#E2E8F0] rounded-md border border-[#E2E8F0]">
          {files.map((f) => (
            <li
              key={f.name}
              className="flex items-center gap-3 px-3 py-2 text-sm"
            >
              {isCensus(f) ? (
                <FileSpreadsheetIcon className="size-4 text-[#166534]" />
              ) : (
                <FileTextIcon className="size-4 text-[#1E40AF]" />
              )}
              <span className="truncate">{f.name}</span>
              <span className="text-xs text-[#64748B]">
                {isCensus(f) ? "Demography census" : "RFQ document"} ·{" "}
                {(f.size / 1024).toFixed(0)} KB
              </span>
              <Button
                variant="ghost"
                size="icon-xs"
                className="ml-auto"
                aria-label={`Remove ${f.name}`}
                onClick={() => setFiles((fs) => fs.filter((x) => x !== f))}
              >
                <XIcon />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ReviewStep({ form, files }: { form: Form; files: File[] }) {
  const rows: [string, string][] = [
    ["Company", form.company_name],
    [
      "Policy Start Date",
      form.proposal_start_date ? isoToDdMmYyyy(form.proposal_start_date) : "—",
    ],
    ["Policy Tenure", form.policy_tenure || "—"],
    ["Incumbent Insurer", form.incumbent_insurer || "— (New Business)"],
    [
      "Brokerage %",
      form.brokerage_pct ? `${Number(form.brokerage_pct).toFixed(2)}%` : "—",
    ],
    ["Rater Type", form.rater_type || "—"],
    ["PIN Code", form.pincode || "—"],
  ];
  return (
    <div className="flex flex-col gap-4 text-sm">
      <dl className="grid grid-cols-[160px_1fr] gap-y-1.5">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-[#64748B]">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <div>
        <p className="mb-1 text-[#64748B]">Documents</p>
        <ul className="list-inside list-disc">
          {files.map((f) => (
            <li key={f.name}>
              {f.name}{" "}
              <span className="text-xs text-[#64748B]">
                ({isCensus(f) ? "census" : "RFQ"})
              </span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-[#64748B]">
        Submitting creates the case, uploads the files and starts the 4-stage
        pipeline. If a file is password-protected you&apos;ll be asked for its
        password; it is used in memory only.
      </p>
    </div>
  );
}
