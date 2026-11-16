import type { CSSProperties } from "react";

import { Icon } from "@/components/ui/icon";
import { upcomingDeadlines } from "@/data/dashboard";

export function DeadlineList() {
  return (
    <section className="dashboard-card deadline-list dashboard-enter" style={{ "--i": 8 } as CSSProperties}>
      <header className="dashboard-card__header"><div><span>Schedule</span><h2>Upcoming deadlines</h2></div><button type="button" title="Calendar view is coming soon">•••</button></header>
      <div>
        {upcomingDeadlines.map((deadline) => (
          <article key={deadline.title}>
            <time><strong>{deadline.day}</strong><small>{deadline.month}</small></time>
            <p><strong>{deadline.title}</strong><span>{deadline.project}</span></p>
            <em>{deadline.tag}</em><Icon name="chevron" />
          </article>
        ))}
      </div>
      <aside className="mcp-status" id="integrations"><span><Icon name="command" /></span><p><strong>MCP server connected</strong><small>3 assistants authorized · All systems operational</small></p><i /></aside>
    </section>
  );
}
