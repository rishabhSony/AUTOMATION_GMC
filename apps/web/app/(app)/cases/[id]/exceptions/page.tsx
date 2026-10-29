import { ExceptionsQueue } from "@/components/workbench/exceptions-tab";

export default async function ExceptionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExceptionsQueue caseId={id} />;
}
