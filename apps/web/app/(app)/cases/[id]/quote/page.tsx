import { QuoteWorkbench } from "@/components/workbench/quote-tab";

export default async function QuotePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuoteWorkbench caseId={id} />;
}
