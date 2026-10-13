from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.registry import get_prompt_registry
from app.core.cache_control import NoStoreMiddleware
from app.core.config import get_settings
from app.core.csrf import require_csrf_header
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.modules.auth.router import router as auth_router
from app.modules.onboarding.router import router as onboarding_router
from app.modules.plan.router import router as plan_router
from app.modules.profile.router import ranking_router
from app.modules.profile.router import router as profile_router

configure_logging()
# Falla al arrancar si el prompt activo no existe o está incompleto.
get_prompt_registry().load("weekly_plan", get_settings().PROMPT_VERSION_WEEKLY_PLAN)

app = FastAPI(
    title="FITIA API",
    description="API del MVP FITIA - Universidad del Valle 2026",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# En producción, Vercel reenvía /api/* al mismo origen.
# En desarrollo local se habilita CORS para el frontend Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NFR-11: nada bajo /api/v1 se guarda en caché (incluidas las respuestas de error),
# salvo los GET públicos que sí pueden cachearse.
app.add_middleware(
    NoStoreMiddleware,
    prefix="/api/v1",
    cacheable_get_paths=frozenset({"/api/v1/programs", "/api/v1/health"}),
)

register_error_handlers(app)

@app.get("/health", tags=["Salud"])
async def health_check():
    return {"status": "ok", "app": "FITIA API", "version": "1.0.0"}

@app.get("/api/v1/health", tags=["Salud"])
async def api_health():
    return {"status": "ok", "api_version": "v1"}

# Todas las mutaciones bajo /api/v1 exigen el encabezado anti-CSRF.
api_v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(require_csrf_header)])
api_v1.include_router(auth_router)
api_v1.include_router(onboarding_router)
api_v1.include_router(plan_router)
api_v1.include_router(profile_router)
api_v1.include_router(ranking_router)
app.include_router(api_v1)
