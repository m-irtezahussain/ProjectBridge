from enum import StrEnum


class ActionOrigin(StrEnum):
    """Trusted application boundary that performed an action."""

    REST = "rest"
    MCP = "mcp"
    WORKER = "worker"
