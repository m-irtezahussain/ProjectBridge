from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.config import get_settings
from app.core.services.status import status_service
from app.schemas.status import ServiceStatus

settings = get_settings()
mcp_server = MCPServer("ProjectBridge")


@mcp_server.tool()
def get_service_status() -> ServiceStatus:
    """Return compact public status information for the ProjectBridge service."""

    return status_service.get_status()


mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        allowed_hosts=settings.mcp_allowed_hosts,
        allowed_origins=settings.mcp_allowed_origins,
    ),
)

