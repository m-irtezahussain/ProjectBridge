from app.schemas.status import ServiceStatus


class StatusService:
    """Return public service metadata without interface-specific concerns."""

    def get_status(self) -> ServiceStatus:
        return ServiceStatus()


status_service = StatusService()

