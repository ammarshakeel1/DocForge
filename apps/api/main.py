from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import documents
from schemas import HealthOut

settings = get_settings()

app = FastAPI(
    title="DocForge AI",
    description="Invoice document extraction demo — upload → extract → review → export",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    detail = {
        "supabase_configured": bool(settings.supabase_url and settings.supabase_service_role_key),
        "openai_configured": bool(settings.openai_api_key),
        "storage_bucket": settings.supabase_storage_bucket,
        "model": settings.openai_model,
    }
    status = "ok" if detail["supabase_configured"] else "missing_config"
    return HealthOut(status=status, detail=detail)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "DocForge AI",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
