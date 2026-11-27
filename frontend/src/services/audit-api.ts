import { apiRequest, type OffsetPage, type PageOptions, queryString } from "./api-client";
import type { ActionOrigin } from "./documents-api";

export type AuditEvent = Readonly<{
  id: number;
  business_id: number;
  actor_user_id: number | null;
  interface: ActionOrigin;
  action: string;
  target_type: string;
  target_id: number | null;
  outcome: string;
  details: Readonly<Record<string, unknown>> | null;
  occurred_at: string;
}>;

export type AuditEventListOptions = PageOptions & Readonly<{
  interface?: ActionOrigin;
  action?: string;
  outcome?: string;
  target_type?: string;
  actor_user_id?: number;
  occurred_from?: Date | string;
  occurred_to?: Date | string;
}>;

type AuditEventPageResponse = Omit<OffsetPage<AuditEvent>, "has_more">;

export async function listAuditEvents(options: AuditEventListOptions = {}): Promise<OffsetPage<AuditEvent>> {
  const page = await apiRequest<AuditEventPageResponse>(`/api/v1/audit-events${queryString(options)}`);
  return { ...page, has_more: page.offset + page.items.length < page.total };
}
