from app.core.services.status import StatusService


def test_status_service_is_interface_agnostic() -> None:
    result = StatusService().get_status()

    assert result.service == "projectbridge"
    assert result.status == "ok"

