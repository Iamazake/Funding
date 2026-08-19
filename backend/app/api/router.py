from fastapi import APIRouter, Depends

from app.api.admin import router as admin_router
from app.api.auth import get_current_user
from app.api.auth import router as auth_router
from app.api.batches import router as batches_router
from app.api.debt_continuity import router as debt_continuity_router
from app.api.funding import router as funding_router
from app.api.health import router as health_router
from app.api.integrations import router as integrations_router
from app.api.operational import router as operational_router
from app.api.treasury import router as treasury_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(integrations_router)
api_router.include_router(batches_router)
api_router.include_router(debt_continuity_router)

protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router.include_router(operational_router)
protected_router.include_router(treasury_router)
protected_router.include_router(funding_router)
api_router.include_router(protected_router)
