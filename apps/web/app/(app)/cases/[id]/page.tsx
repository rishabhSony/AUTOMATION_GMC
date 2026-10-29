import { redirect } from "next/navigation";

// The pipeline hub (App Flow route 7) needs the SSE status stream, which isn't built yet.
export default async function CasePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/cases/${id}/quote`);
}
