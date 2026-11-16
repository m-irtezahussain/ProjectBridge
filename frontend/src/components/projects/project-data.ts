export type ProjectStatus = "Active" | "Planning" | "At risk" | "Completed";
export type ProjectFilter = "All" | ProjectStatus;

export type ProjectItem = Readonly<{
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  progress: number;
  dueDate: string;
  dueLabel: string;
  tasksDone: number;
  tasksTotal: number;
  documents: number;
  members: readonly string[];
  updated: string;
  accent: "lime" | "violet" | "amber" | "blue";
}>;

export const initialProjects: readonly ProjectItem[] = [
  { id: "projectbridge-launch", name: "ProjectBridge Launch", description: "Ship the secure multi-tenant workspace and MCP integration to the first pilot teams.", status: "Active", progress: 74, dueDate: "2026-11-28", dueLabel: "Nov 28", tasksDone: 28, tasksTotal: 38, documents: 24, members: ["MH", "AR", "SK"], updated: "12 min ago", accent: "lime" },
  { id: "northstar-rebrand", name: "Northstar Rebrand", description: "Unify product positioning, visual language, and launch collateral across channels.", status: "At risk", progress: 48, dueDate: "2026-12-05", dueLabel: "Dec 05", tasksDone: 14, tasksTotal: 29, documents: 18, members: ["LC", "MH"], updated: "34 min ago", accent: "violet" },
  { id: "atlas-research", name: "Atlas Research Hub", description: "Turn customer interviews and market documents into a searchable research library.", status: "Active", progress: 86, dueDate: "2026-11-21", dueLabel: "Nov 21", tasksDone: 31, tasksTotal: 36, documents: 42, members: ["AR", "JT", "LC"], updated: "1 hr ago", accent: "amber" },
  { id: "mobile-onboarding", name: "Mobile Onboarding", description: "Reduce first-session friction with a redesigned guided setup and contextual help.", status: "Planning", progress: 18, dueDate: "2026-12-18", dueLabel: "Dec 18", tasksDone: 4, tasksTotal: 22, documents: 9, members: ["SK", "JT"], updated: "2 hrs ago", accent: "blue" },
  { id: "ops-automation", name: "Ops Automation", description: "Automate weekly reporting, handoffs, and project-risk notifications for operations.", status: "Active", progress: 63, dueDate: "2026-12-02", dueLabel: "Dec 02", tasksDone: 17, tasksTotal: 27, documents: 16, members: ["MH", "LC", "AR"], updated: "Yesterday", accent: "lime" },
  { id: "client-portal", name: "Client Portal v2", description: "Create a permission-aware client view for milestones, approvals, and source files.", status: "Planning", progress: 27, dueDate: "2027-01-12", dueLabel: "Jan 12", tasksDone: 6, tasksTotal: 22, documents: 7, members: ["JT", "SK"], updated: "Yesterday", accent: "violet" },
  { id: "security-review", name: "Security Review", description: "Close authentication, tenant-isolation, document ingestion, and audit-trail findings.", status: "At risk", progress: 57, dueDate: "2026-11-25", dueLabel: "Nov 25", tasksDone: 12, tasksTotal: 21, documents: 8, members: ["AR", "MH"], updated: "2 days ago", accent: "amber" },
  { id: "q3-insights", name: "Q3 Insights Archive", description: "Consolidate completed quarterly research and retain traceable source documents.", status: "Completed", progress: 100, dueDate: "2026-10-31", dueLabel: "Oct 31", tasksDone: 34, tasksTotal: 34, documents: 31, members: ["LC", "SK"], updated: "Oct 31", accent: "blue" },
] as const;

export function filterProjects(
  projects: readonly ProjectItem[],
  query: string,
  filter: ProjectFilter,
): ProjectItem[] {
  const normalizedQuery = query.trim().toLowerCase();
  return projects.filter((project) => {
    const matchesFilter = filter === "All" || project.status === filter;
    const matchesQuery =
      normalizedQuery.length === 0 ||
      project.name.toLowerCase().includes(normalizedQuery) ||
      project.description.toLowerCase().includes(normalizedQuery);
    return matchesFilter && matchesQuery;
  });
}
