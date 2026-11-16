export type ProjectStatus = "Active" | "Planning" | "At risk" | "Completed";
export type ProjectFilter = "All" | ProjectStatus;

export type ProjectItem = Readonly<{
  id: number;
  name: string;
  description: string | null;
  business_id: number;
  status: ProjectStatus;
}>;

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
      project.description?.toLowerCase().includes(normalizedQuery) === true;
    return matchesFilter && matchesQuery;
  });
}
