import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { ProjectWorkspace } from "@/components/project-workspace/project-workspace";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Project workspace — ProjectBridge",
  description: "Plan and manage project tasks across Kanban, list, and calendar views.",
};

export default async function ProjectWorkspacePage({
  params,
}: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const session = await getSessionStatus();
  if (!session.authenticated) redirect("/login");
  if (!session.has_business) redirect("/business/register");

  const { projectId } = await params;
  const numericProjectId = Number(projectId);
  if (!Number.isInteger(numericProjectId) || numericProjectId < 1) notFound();

  return (
    <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
      <ProjectWorkspace projectId={numericProjectId} />
    </DashboardFrame>
  );
}
