import { AuditTrail } from "@/components/workbench/audit-tab";

export default async function AuditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AuditTrail caseId={id} />;
}
