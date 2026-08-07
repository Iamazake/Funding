from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.operational import RevenueDetail, RevenuePage, SaleDetail, SalesPage
from app.services.operational.read import (
    OperationalReadRepository,
    RevenueQuery,
    SalesQuery,
)

router = APIRouter(prefix="/api/operational", tags=["operational"])
QualityFilter = Literal["VALID", "WARNING", "DIVERGENT", "INVALID"]
SortOrder = Literal["asc", "desc"]


def get_operational_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationalReadRepository:
    return OperationalReadRepository(session)


@router.get("/sales", response_model=SalesPage)
async def list_sales(
    repository: Annotated[OperationalReadRepository, Depends(get_operational_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: str | None = None,
    contract: str | None = None,
    client: str | None = None,
    status: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
    quality: QualityFilter | None = None,
    sort_by: str = "operation_date",
    sort_order: SortOrder = "desc",
) -> SalesPage:
    return await repository.list_sales(
        SalesQuery(
            page=page,
            page_size=page_size,
            search=search,
            contract=contract,
            client=client,
            status=status,
            period_from=period_from,
            period_to=period_to,
            quality=quality,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


@router.get("/sales/{sale_id}", response_model=SaleDetail)
async def get_sale(
    sale_id: str,
    repository: Annotated[OperationalReadRepository, Depends(get_operational_repository)],
) -> SaleDetail:
    result = await repository.get_sale(sale_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Venda operacional não encontrada.")
    return result


@router.get("/revenue", response_model=RevenuePage)
async def list_revenue(
    repository: Annotated[OperationalReadRepository, Depends(get_operational_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: str | None = None,
    contract: str | None = None,
    client: str | None = None,
    status: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    payment_from: date | None = None,
    payment_to: date | None = None,
    quality: QualityFilter | None = None,
    sort_by: str = "due_date",
    sort_order: SortOrder = "desc",
) -> RevenuePage:
    return await repository.list_revenue(
        RevenueQuery(
            page=page,
            page_size=page_size,
            search=search,
            contract=contract,
            client=client,
            status=status,
            due_from=due_from,
            due_to=due_to,
            payment_from=payment_from,
            payment_to=payment_to,
            quality=quality,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


@router.get("/revenue/{revenue_id}", response_model=RevenueDetail)
async def get_revenue(
    revenue_id: int,
    repository: Annotated[OperationalReadRepository, Depends(get_operational_repository)],
) -> RevenueDetail:
    result = await repository.get_revenue(revenue_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Registro de Receita não encontrado.")
    return result
