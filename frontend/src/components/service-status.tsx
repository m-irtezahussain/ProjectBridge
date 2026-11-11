import { formatStatusLabel } from "@/services/api";
import type { DisplayStatus } from "@/types/status";

type ServiceStatusProps = Readonly<{
  status: DisplayStatus;
}>;

export function ServiceStatus({ status }: ServiceStatusProps) {
  return (
    <section className="status-card" aria-label="Service status">
      <span className={`status-dot status-dot--${status.status}`} aria-hidden="true" />
      <div>
        <strong>{formatStatusLabel(status.status)}</strong>
        <p>API version {status.version}</p>
      </div>
    </section>
  );
}

