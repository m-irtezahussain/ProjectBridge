import type { CSSProperties } from "react";

import { Icon } from "@/components/ui/icon";
import type { DashboardMetric } from "@/data/dashboard";

export function MetricCard({ metric, index }: Readonly<{ metric: DashboardMetric; index: number }>) {
  return (
    <article className={`dashboard-metric dashboard-enter dashboard-metric--${metric.tone}`} style={{ "--i": index } as CSSProperties}>
      <div className="dashboard-metric__icon"><Icon name={metric.icon} /></div>
      <span>{metric.label}</span>
      <div><strong>{metric.value}</strong><b>{metric.trend}</b></div>
      <small>{metric.detail}</small>
    </article>
  );
}
