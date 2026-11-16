import type { CSSProperties } from "react";

import { recentActivity } from "@/data/dashboard";

export function ActivityFeed() {
  return (
    <section className="dashboard-card activity-feed dashboard-enter" style={{ "--i": 7 } as CSSProperties}>
      <header className="dashboard-card__header"><div><span>Workspace</span><h2>Recent activity</h2></div><i className="live-indicator">Live</i></header>
      <div className="activity-list">
        {recentActivity.map((activity) => (
          <article key={`${activity.actor}-${activity.time}`}>
            <b className={`activity-avatar activity-avatar--${activity.tone}`}>{activity.initials}</b>
            <p><strong>{activity.actor}</strong><span>{activity.action} <em>{activity.target}</em></span></p>
            <time>{activity.time}</time>
          </article>
        ))}
      </div>
    </section>
  );
}
