import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { DocumentDetail } from "@/components/documents/document-detail";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Document source — ProjectBridge",
  description: "Review immutable document metadata and validation status.",
};

export default async function DocumentDetailPage({
  params,
}: Readonly<{ params: Promise<{ documentId: string }> }>) {
  const session = await getSessionStatus();
  if (!session.authenticated) redirect("/login");
  if (!session.has_business) redirect("/business/register");

  const { documentId } = await params;
  const numericDocumentId = Number(documentId);
  if (!Number.isInteger(numericDocumentId) || numericDocumentId < 1) notFound();

  return (
    <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
      <DocumentDetail documentId={numericDocumentId} />
    </DashboardFrame>
  );
}
