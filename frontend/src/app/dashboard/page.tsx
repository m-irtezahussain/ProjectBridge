import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { redirect } from "next/navigation";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { DeadlineList } from "@/components/dashboard/deadline-list";
import { MetricCard } from "@/components/dashboard/metric-card";
import { ProjectHealth } from "@/components/dashboard/project-health";
import { TaskOverview } from "@/components/dashboard/task-overview";
import { dashboardMetrics } from "@/data/dashboard";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Workspace overview — ProjectBridge",
  description: "ProjectBridge workspace health, projects, tasks, and recent activity.",
};

export default async function DashboardPage() {
  const session = await getSessionStatus();
  if (!session.authenticated) {
    redirect("/login");
  }
  if (!session.has_business) {
    redirect("/business/register");
  }

  const firstName = session.full_name?.split(" ")[0] ?? "there";

  return <DashboardFrame userName={session.full_name ?? "ProjectBridge user"} userEmail={session.email ?? ""}>
    <main className="dashboard-content" id="main-content">
      <section className="dashboard-intro dashboard-enter" style={{ "--i": 0 } as CSSProperties}>
        <div><span className="eyebrow">Monday, November 16</span><h1>Good morning, {firstName}.</h1><p>Here&apos;s what is moving across your workspace today.</p></div>
        <div className="dashboard-intro__status"><i /><span><strong>Workspace healthy</strong><small>Last synced just now</small></span></div>
      </section>
      <section className="dashboard-metrics" aria-label="Workspace metrics">
        {dashboardMetrics.map((metric, index) => <MetricCard metric={metric} index={index + 1} key={metric.label} />)}
      </section>
      <div className="dashboard-grid dashboard-grid--primary"><ProjectHealth /><TaskOverview /></div>
      <div className="dashboard-grid dashboard-grid--secondary"><ActivityFeed /><DeadlineList /></div>
    </main>
  </DashboardFrame>;
}
