import { cn } from "cn";

// Semantic provenance palette from the UI/UX brief §1.1 (background / text / border).
const PILL_STYLES: Record<string, string> = {
  "RFQ Data": "bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]",
  "Default Data": "bg-[#EFF6FF] text-[#1E40AF] border-[#BFDBFE]",
  "AI Derived": "bg-[#F0FDFA] text-[#115E59] border-[#99F6E4]",
  "Demography Derived": "bg-[#FAF5FF] text-[#6B21A8] border-[#E9D5FF]",
  Manual: "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]",
  Fixed: "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]",
  "Not Found": "bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]",
  Ambiguous: "bg-[#FDF4FF] text-[#86198F] border-[#F5D0FE]",
  Conflict: "bg-[#FDF4FF] text-[#86198F] border-[#F5D0FE]",
  "Review Required": "bg-[#FFF7ED] text-[#9A3412] border-[#FFEDD5]",
};

// Case statuses and sub-limit match results reuse the same palette.
const ALIASES: Record<string, string> = {
  Matched: "RFQ Data",
  "Unmatched / Review Required": "Review Required",
  "Needs Review": "Review Required",
  "Ready for Quote": "RFQ Data",
  Completed: "Demography Derived",
  Uploaded: "Default Data",
  Processing: "AI Derived",
  Draft: "Fixed",
  Failed: "Not Found",
  Approved: "Manual",
};

export function StatusPill({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  const style =
    PILL_STYLES[label] ?? PILL_STYLES[ALIASES[label]] ?? PILL_STYLES.Fixed;
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-full border px-2 font-mono text-[11px] font-semibold tracking-[0.02em] whitespace-nowrap",
        style,
        className,
      )}
    >
      {label}
    </span>
  );
}
