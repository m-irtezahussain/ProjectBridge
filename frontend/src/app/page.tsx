import { ServiceStatus } from "@/components/service-status";
import { getServiceStatus } from "@/services/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const status = await getServiceStatus();

  return (
    <main>
      <div className="eyebrow">Container-first project operations</div>
      <h1>One workspace.<br />Two interfaces.</h1>
      <p className="lede">
        ProjectBridge will expose the same secure, tenant-scoped project core through
        the web and Model Context Protocol.
      </p>
      <ServiceStatus status={status} />
      <div className="interface-grid">
        <article>
          <span>01</span>
          <h2>Web application</h2>
          <p>A typed Next.js interface for teams, projects, tasks, and source documents.</p>
        </article>
        <article>
          <span>02</span>
          <h2>MCP server</h2>
          <p>Compact tools backed by the same managers, permissions, and audit trail.</p>
        </article>
      </div>
    </main>
  );
}

