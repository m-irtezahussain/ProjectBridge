import { formatStatusLabel } from "@/services/api";
import type { DisplayStatus } from "@/types/status";

type ServiceStatusProps = Readonly<{
  status: DisplayStatus;
  compact?: boolean;
}>;

export function ServiceStatus({ status, compact = false }: ServiceStatusProps) {
  return (
    <section className={`status-card${compact ? " status-card--compact" : ""}`} aria-label="Service status">
      <span className={`status-dot status-dot--${status.status}`} aria-hidden="true" />
      <div>
        <strong>{formatStatusLabel(status.status)}</strong>
        {!compact && <p>API version {status.version}</p>}
      </div>
    </section>
  );
}

