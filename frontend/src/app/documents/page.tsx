import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { DocumentsView } from "@/components/documents/documents-view";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Documents — ProjectBridge",
  description: "Preserve, validate, and trace source documents in ProjectBridge.",
};

export default async function DocumentsPage() {
  const session = await getSessionStatus();
  if (!session.authenticated) redirect("/login");
  if (!session.has_business) redirect("/business/register");

  return (
    <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
      <DocumentsView />
    </DashboardFrame>
  );
}
