import { redirect } from "next/navigation";

// The workbench opens on the quote review; the pipeline hub (App Flow route 7) is /pipeline.
export default async function CasePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/cases/${id}/quote`);
}
