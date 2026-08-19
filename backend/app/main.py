from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import install_sensitive_access_log_filter

install_sensitive_access_log_filter()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Remo Funding API",
    version="0.1.0",
    description="API operacional e financeira do Funding REMO.",
    lifespan=lifespan,
    docs_url="/docs" if settings.resolved_enable_api_docs else None,
    redoc_url="/redoc" if settings.resolved_enable_api_docs else None,
    openapi_url="/openapi.json" if settings.resolved_enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Accept", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.resolved_trusted_hosts)

app.include_router(api_router)
