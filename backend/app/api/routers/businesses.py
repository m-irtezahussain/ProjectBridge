from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.routers.auth import (
    ACCESS_COOKIE,
    ONBOARDING_COOKIE,
    _clear_cookies,
)
from app.core.managers.auth import (
    AuthenticationError,
    BusinessAlreadyRegisteredError,
)
from app.core.services.rate_limits import RateLimitExceededError
from app.deps import AuthManagerDep, AuthRateLimiterDep, SessionDep
from app.schemas.auth import NavigationResponse
from app.schemas.business import BusinessCreate

router = APIRouter()


@router.post(
    "/register",
    response_model=NavigationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_business(
    data: BusinessCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    manager: AuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> NavigationResponse:
    try:
        client = request.client.host if request.client else "unknown"
        await limiter.consume(
            session, bucket="business-registration-ip", identity=client, limit=20
        )
        await manager.register_business(
            session,
            data,
            request.cookies.get(ACCESS_COOKIE),
            request.cookies.get(ONBOARDING_COOKIE),
        )
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except BusinessAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _clear_cookies(response)
    return NavigationResponse(message="Business registered", next="/login")
