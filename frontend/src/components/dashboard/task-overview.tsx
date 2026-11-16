import type { CSSProperties } from "react";

import { taskBreakdown } from "@/data/dashboard";

export function TaskOverview() {
  return (
    <section className="dashboard-card task-overview dashboard-enter" id="tasks" style={{ "--i": 6 } as CSSProperties}>
      <header className="dashboard-card__header"><div><span>Workload</span><h2>Task overview</h2></div><small>This week</small></header>
      <div className="task-chart">
        <div className="task-donut"><span><strong>42</strong><small>Total tasks</small></span></div>
        <ul>{taskBreakdown.map((item) => <li key={item.label}><i className={`task-color task-color--${item.color}`} /><span>{item.label}</span><strong>{item.value}</strong></li>)}</ul>
      </div>
      <div className="task-throughput"><span><b>68%</b> weekly completion</span><small>8% above last week</small></div>
    </section>
  );
}
