from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.routers.auth import ACCESS_COOKIE
from app.core.managers.auth import AuthenticationError
from app.core.managers.projects import BusinessRequiredError
from app.deps import AuditManagerDep, SessionDep
from app.models import ActionOrigin
from app.schemas.audit import AuditEventPage, AuditEventRead

router = APIRouter()


@router.get("", response_model=AuditEventPage)
async def list_audit_events(
    request: Request,
    session: SessionDep,
    manager: AuditManagerDep,
    interface: ActionOrigin | None = None,
    action: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    outcome: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    actor_user_id: Annotated[int | None, Query(gt=0)] = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditEventPage:
    try:
        items, total = await manager.list_for_rest(
            session,
            request.cookies.get(ACCESS_COOKIE),
            interface=interface,
            action=action,
            outcome=outcome,
            target_type=target_type,
            actor_user_id=actor_user_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
    except AuthenticationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error
    except BusinessRequiredError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    return AuditEventPage(
        items=[AuditEventRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
