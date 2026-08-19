from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentAdmin
from app.core.database import SessionFactory, get_session
from app.models.auth import AppUserAuditEvent
from app.schemas.batches import (
    OperationalBatchDetail,
    OperationalBatchList,
    OperationalBatchPromotionResponse,
)
from app.services.operational.batches import (
    OperationalBatchNotFoundError,
    OperationalBatchReviewService,
)
from app.services.operational.promotion import (
    OperationalPromotionError,
    OperationalPromotionService,
    SourceBatchNotFoundError,
    SourceBatchNotSucceededError,
)
from app.services.operational.store import SqlAlchemyOperationalPromotionRepository

router = APIRouter(prefix="/api/operational/batches", tags=["operational-batches"])


def get_batch_review_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationalBatchReviewService:
    return OperationalBatchReviewService(session, SessionFactory)


ReviewService = Annotated[OperationalBatchReviewService, Depends(get_batch_review_service)]


def get_operational_promotion_service() -> OperationalPromotionService:
    return OperationalPromotionService(SqlAlchemyOperationalPromotionRepository(SessionFactory))


PromotionService = Annotated[
    OperationalPromotionService, Depends(get_operational_promotion_service)
]


@router.get("", response_model=OperationalBatchList)
async def list_batches(
    _: CurrentAdmin,
    service: ReviewService,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> OperationalBatchList:
    return await service.list_batches(limit=limit)


@router.get("/{batch_id}", response_model=OperationalBatchDetail)
async def get_batch(
    batch_id: int,
    _: CurrentAdmin,
    service: ReviewService,
) -> OperationalBatchDetail:
    try:
        return await service.get_batch(batch_id)
    except OperationalBatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{batch_id}/promote", response_model=OperationalBatchPromotionResponse)
async def promote_batch(
    batch_id: int,
    admin: CurrentAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    review: ReviewService,
    service: PromotionService,
) -> OperationalBatchPromotionResponse:
    try:
        detail = await review.get_batch(batch_id)
        if not detail.promotion_eligible:
            raise HTTPException(
                status_code=409,
                detail=detail.promotion_eligibility_reason,
            )
        report = await service.promote(batch_id)
        if report.status == "identity_review_required":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Promoção bloqueada: existem correspondências de identidade "
                    "críticas em REVIEW_REQUIRED."
                ),
            )
    except OperationalBatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SourceBatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SourceBatchNotSucceededError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OperationalPromotionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    session.add(
        AppUserAuditEvent(
            actor_user_id=admin.id,
            action="OPERATIONAL_BATCH_PROMOTED",
            details={
                "source_batch_id": report.source_batch_id,
                "promotion_id": report.promotion_id,
                "status": report.status,
                "idempotent": report.idempotent,
            },
        )
    )
    await session.commit()
    return OperationalBatchPromotionResponse(
        promotion_id=report.promotion_id,
        source_batch_id=report.source_batch_id,
        status=report.status,
        idempotent=report.idempotent,
        summary=report.summary,
    )
