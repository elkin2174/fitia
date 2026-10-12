from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.csrf import require_csrf_header
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.modules.auth.router import router as auth_router

configure_logging()

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
app.include_router(api_v1)
