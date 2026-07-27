from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
DatabaseSession = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def health(session: DatabaseSession) -> HealthResponse | JSONResponse:
    try:
        result = await session.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise RuntimeError("Unexpected database health-check result")
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "api": "ok", "database": "unavailable"},
        )

    return HealthResponse(status="ok", api="ok", database="connected")
