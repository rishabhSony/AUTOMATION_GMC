import { CaseHeader } from "@/components/workbench/case-header";

export default async function CaseLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex flex-col">
      <CaseHeader caseId={id} />
      <main className="mx-auto w-full max-w-[1400px] p-6">{children}</main>
    </div>
  );
}
