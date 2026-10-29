import { DemographyWorkbench } from "@/components/workbench/demography-tab";

export default async function DemographyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <DemographyWorkbench caseId={id} />;
}
