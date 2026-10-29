import { SublimitsWorkbench } from "@/components/workbench/sublimits-tab";

export default async function SublimitsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SublimitsWorkbench caseId={id} />;
}
