from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/health", tags=["Salud"])
async def health_check():
    return {"status": "ok", "app": "FITIA API", "version": "1.0.0"}

@app.get("/api/v1/health", tags=["Salud"])
async def api_health():
    return {"status": "ok", "api_version": "v1"}
