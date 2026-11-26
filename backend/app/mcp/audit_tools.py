from mcp.server import MCPServer

from app.core.managers.audit import AuditManager
from app.core.services.mcp_auth import MCPAuthorizationError
from app.mcp.auth import MCPDatabaseSessions, require_mcp_principal
from app.mcp.tools import READ_ONLY, structured_mcp_errors
from app.schemas.audit import AuditEventListInput, AuditEventPage, AuditEventRead


def register_audit_tools(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    audit: AuditManager,
) -> None:
    @server.tool(
        description=(
            "List compact, tenant-scoped audit events. Requires the audit:read scope. "
            "Results never include credentials or document contents."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_audit_events(input: AuditEventListInput) -> AuditEventPage:
        async with structured_mcp_errors():
            principal = require_mcp_principal()
            async with sessions.session() as session:
                if "audit:read" not in principal.scopes:
                    await audit.record_denied_for_principal(
                        session,
                        principal,
                        action="audit.query",
                        required_permission="audit:read",
                    )
                    raise MCPAuthorizationError("Insufficient MCP scope")
                items, total = await audit.list_for_principal(
                    session,
                    principal,
                    interface=input.interface,
                    action=input.action,
                    outcome=input.outcome,
                    target_type=input.target_type,
                    actor_user_id=input.actor_user_id,
                    occurred_from=input.occurred_from,
                    occurred_to=input.occurred_to,
                    limit=input.limit,
                    offset=input.offset,
                )
        return AuditEventPage(
            items=[AuditEventRead.model_validate(item) for item in items],
            total=total,
            limit=input.limit,
            offset=input.offset,
        )
