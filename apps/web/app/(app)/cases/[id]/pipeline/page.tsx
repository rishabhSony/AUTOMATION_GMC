import { PipelineScreen } from "@/components/workbench/pipeline-tab";

export default async function PipelinePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PipelineScreen caseId={id} />;
}
