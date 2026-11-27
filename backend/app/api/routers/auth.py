from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.auth_cookies import (
    ACCESS_COOKIE,
    ONBOARDING_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
)
from app.config import get_settings
from app.core.managers.auth import AuthenticationError
from app.core.services.rate_limits import RateLimitExceededError
from app.deps import AuthManagerDep, AuthRateLimiterDep, SessionDep
from app.schemas.auth import LoginRequest, NavigationResponse, SessionResponse
from app.schemas.user import UserCreate

router = APIRouter()


def _set_cookie(response: Response, name: str, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        name,
        token,
        max_age=settings.jwt_access_minutes * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_sliding_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", samesite="lax")
    response.delete_cookie(ONBOARDING_COOKIE, path="/", samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite="strict"
    )


@router.post("/signup", response_model=NavigationResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    data: UserCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    manager: AuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> NavigationResponse:
    try:
        client = request.client.host if request.client else "unknown"
        await limiter.consume(session, bucket="signup-ip", identity=client, limit=20)
        await limiter.consume(session, bucket="signup-email", identity=data.email, limit=5)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    result = await manager.signup(session, data)
    _clear_cookies(response)
    if result.token is not None:
        _set_cookie(response, ONBOARDING_COOKIE, result.token)
    return NavigationResponse(
        message="Registration request accepted",
        next=result.next,
    )


@router.post("/login", response_model=NavigationResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    manager: AuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> NavigationResponse:
    try:
        client = request.client.host if request.client else "unknown"
        await limiter.consume(session, bucket="login-ip", identity=client, limit=50)
        await limiter.consume(session, bucket="login-email", identity=data.email, limit=10)
        result = await manager.login(session, data.email, data.password)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _clear_cookies(response)
    if result.token is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    _set_cookie(response, ACCESS_COOKIE, result.token)
    if result.refresh_token is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    _set_refresh_cookie(response, result.refresh_token)
    return NavigationResponse(message="Signed in", next=result.next)


@router.post("/refresh", response_model=NavigationResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    manager: AuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> NavigationResponse:
    try:
        client = request.client.host if request.client else "unknown"
        await limiter.consume(session, bucket="refresh-ip", identity=client, limit=60)
        result = await manager.refresh(session, request.cookies.get(REFRESH_COOKIE))
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthenticationError:
        _clear_cookies(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return NavigationResponse(message="Invalid or expired session", next="/login")
    if result.token is None or result.refresh_token is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    _set_cookie(response, ACCESS_COOKIE, result.token)
    _set_refresh_cookie(response, result.refresh_token)
    return NavigationResponse(message="Session refreshed", next=result.next)


@router.get("/session", response_model=SessionResponse)
async def session_status(
    request: Request,
    session: SessionDep,
    manager: AuthManagerDep,
) -> SessionResponse:
    return await manager.session_status(
        session,
        request.cookies.get(ACCESS_COOKIE),
        request.cookies.get(ONBOARDING_COOKIE),
    )


@router.post("/logout", response_model=NavigationResponse)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    manager: AuthManagerDep,
) -> NavigationResponse:
    await manager.logout(
        session,
        request.cookies.get(ACCESS_COOKIE),
        request.cookies.get(ONBOARDING_COOKIE),
        request.cookies.get(REFRESH_COOKIE),
    )
    _clear_cookies(response)
    return NavigationResponse(message="Signed out", next="/login")
