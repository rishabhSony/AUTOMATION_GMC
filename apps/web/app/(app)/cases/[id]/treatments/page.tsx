import { TreatmentsWorkbench } from "@/components/workbench/treatments-tab";

export default async function TreatmentsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TreatmentsWorkbench caseId={id} />;
}
