import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { KnowledgeView } from "@/components/knowledge/knowledge-view";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Knowledge search — ProjectBridge",
  description: "Search tenant-isolated project knowledge with traceable source excerpts.",
};

export default async function KnowledgePage() {
  const session = await getSessionStatus();
  if (!session.authenticated) redirect("/login");
  if (!session.has_business) redirect("/business/register");

  return (
    <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
      <KnowledgeView />
    </DashboardFrame>
  );
}
