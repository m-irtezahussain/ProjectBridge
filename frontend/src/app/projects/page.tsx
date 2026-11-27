import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { ProjectsView } from "@/components/projects/projects-view";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Projects — ProjectBridge",
  description: "Plan, review, and manage every ProjectBridge workspace project.",
};

export default async function ProjectsPage() {
  const session = await getSessionStatus();
  if (!session.authenticated) redirect("/login");
  if (!session.has_business) redirect("/business/register");

  return (
    <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
      <Suspense fallback={<section className="projects-grid projects-grid--loading" aria-label="Loading projects"><i /><i /><i /><i /></section>}>
        <ProjectsView />
      </Suspense>
    </DashboardFrame>
  );
}
