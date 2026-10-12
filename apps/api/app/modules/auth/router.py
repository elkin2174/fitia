from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.mailer import Mailer, get_mailer
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.modules.auth.cookies import set_session_cookie
from app.modules.auth.schemas import (
    ProgramOut,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    VerifiedUserOut,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(tags=["Autenticación"])


def get_auth_service(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
    mailer: Mailer = Depends(get_mailer),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> AuthService:
    return AuthService(session, settings, clock, mailer, limiter, background)


def _client_ip(request: Request) -> str:
    # Detrás de Render/Vercel, uvicorn debe correr con --proxy-headers para obtener la IP real.
    return request.client.host if request.client else "unknown"


@router.get("/programs", response_model=list[ProgramOut])
async def list_programs(service: AuthService = Depends(get_auth_service)) -> list[ProgramOut]:
    return [ProgramOut.model_validate(p) for p in await service.list_programs()]


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(
    payload: RegisterRequest, request: Request, service: AuthService = Depends(get_auth_service)
) -> RegisterResponse:
    await service.register(payload, _client_ip(request))
    return RegisterResponse()


@router.post("/auth/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> VerifyEmailResponse:
    result = await service.verify_email(payload.token)
    set_session_cookie(response, result.session.token, result.session.expires_at, settings)
    response.headers["Cache-Control"] = "no-store"
    return VerifyEmailResponse(
        user=VerifiedUserOut(
            id=result.user.id,
            nickname=result.user.nickname,
            program=ProgramOut.model_validate(result.program),
        )
    )


@router.post(
    "/auth/resend-verification", status_code=status.HTTP_202_ACCEPTED, response_model=ResendVerificationResponse
)
async def resend_verification(
    payload: ResendVerificationRequest, request: Request, service: AuthService = Depends(get_auth_service)
) -> ResendVerificationResponse:
    await service.resend_verification(payload.email, _client_ip(request))
    return ResendVerificationResponse()
