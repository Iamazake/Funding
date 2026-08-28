from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import OperationalDebtContinuity
from app.models.identity import OperationalSaleSnapshot
from app.models.normalized import OperationalContract, OperationalLoan, OperationalPromotion
from app.services.funding.repository import FundingNotFoundError


@dataclass(frozen=True, slots=True)
class FundingSale:
    sale_id: str
    operation_date: date
    released_amount: Decimal | None
    sale_identity_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    has_new_disbursement: bool = True
    funding_origin_sale_identity_id: UUID | None = None


async def resolve_funding_sale(session: AsyncSession, sale_id: str) -> FundingSale:
    promotion_id = await session.scalar(
        select(OperationalPromotion.id).where(
            OperationalPromotion.is_current.is_(True),
            OperationalPromotion.status == "succeeded",
        )
    )
    if promotion_id is None:
        raise FundingNotFoundError("Nenhuma promoção operacional atual está disponível.")

    identity_id = await resolve_sale_identity_id(session, sale_id)
    if isinstance(identity_id, (OperationalContract, OperationalLoan)):
        entity = identity_id
        if entity.operation_date is None:
            raise FundingNotFoundError("Venda sem data operacional válida para composição.")
        return FundingSale(
            sale_id=sale_id,
            operation_date=entity.operation_date,
            released_amount=entity.released_amount,
        )
    snapshot = await session.scalar(
        select(OperationalSaleSnapshot).where(
            OperationalSaleSnapshot.sale_identity_id == identity_id,
            OperationalSaleSnapshot.promotion_id == promotion_id,
        )
    )
    if snapshot is None:
        entity = None
    elif snapshot.contract_id is not None:
        entity = await session.get(OperationalContract, snapshot.contract_id)
    elif snapshot.loan_id is not None:
        entity = await session.get(OperationalLoan, snapshot.loan_id)
    else:
        entity = None
    if entity is None:
        raise FundingNotFoundError("Venda operacional não encontrada.")
    if entity.operation_date is None:
        raise FundingNotFoundError("Venda sem data operacional válida para composição.")
    continuity = await session.scalar(
        select(OperationalDebtContinuity).where(
            OperationalDebtContinuity.successor_sale_identity_id == identity_id,
            OperationalDebtContinuity.predecessor_sale_identity_id != identity_id,
            OperationalDebtContinuity.status.in_(
                ("RENEGOTIATION_CONFIRMED", "REFIN_CONFIRMED")
            ),
        )
    )
    is_refinancing = continuity is not None and continuity.status == "REFIN_CONFIRMED"
    operational_release = entity.released_amount
    return FundingSale(
        sale_id=f"sale:{identity_id}",
        sale_identity_id=identity_id,
        operation_date=entity.operation_date,
        released_amount=(
            operational_release
            if is_refinancing or continuity is None
            else continuity.principal_rolled
        ),
        has_new_disbursement=(
            operational_release is not None and operational_release > Decimal("0.00")
            if is_refinancing
            else continuity is None
        ),
        funding_origin_sale_identity_id=(
            continuity.predecessor_sale_identity_id if continuity is not None else None
        ),
    )


async def resolve_sale_identity_id(session: AsyncSession, sale_id: str) -> UUID:
    """Resolve canonical IDs and the temporary contract:/loan: compatibility aliases."""

    try:
        kind, raw_id = sale_id.split(":", 1)
        if kind == "sale":
            return UUID(raw_id)
        snapshot_id = int(raw_id)
    except (AttributeError, TypeError, ValueError) as error:
        raise FundingNotFoundError("Venda operacional não encontrada.") from error
    if kind == "contract":
        identity_id = await session.scalar(
            select(OperationalSaleSnapshot.sale_identity_id).where(
                OperationalSaleSnapshot.contract_id == snapshot_id
            )
        )
    elif kind == "loan":
        identity_id = await session.scalar(
            select(OperationalSaleSnapshot.sale_identity_id).where(
                OperationalSaleSnapshot.loan_id == snapshot_id
            )
        )
    else:
        identity_id = None
    if identity_id is None:
        raise FundingNotFoundError("Venda operacional não encontrada.")
    return identity_id
