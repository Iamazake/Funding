from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funding import (
    FundingAuditEvent,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingSource,
)
from app.models.operational import utc_now
from app.schemas.funding import (
    ContributionCreate,
    ContributionResponse,
    ContributionUpdate,
    InvestorCreate,
    InvestorResponse,
    InvestorUpdate,
)


class FundingNotFoundError(LookupError):
    pass


class FundingConflictError(RuntimeError):
    pass


class FundingRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID | None = None,
        actor_label: str = "FUNDING_API",
    ) -> None:
        self._session = session
        self._actor_user_id = actor_user_id
        self._actor_label = actor_label

    async def list_investors(self) -> list[InvestorResponse]:
        rows = await self._session.scalars(
            select(FundingInvestor).order_by(FundingInvestor.name, FundingInvestor.id)
        )
        return [InvestorResponse.model_validate(row) for row in rows]

    async def get_investor(self, investor_id: UUID) -> InvestorResponse:
        row = await self._session.get(FundingInvestor, investor_id)
        if row is None:
            raise FundingNotFoundError("Investidor não encontrado.")
        return InvestorResponse.model_validate(row)

    async def create_investor(self, data: InvestorCreate) -> InvestorResponse:
        entity_id = uuid4()
        row = FundingInvestor(
            id=entity_id,
            code=f"INV-{entity_id.hex[:10].upper()}",
            **data.model_dump(),
        )
        self._session.add(row)
        self._audit("INVESTOR", entity_id, "CREATED", data.model_dump(mode="json"))
        await self._commit_and_refresh(row)
        return InvestorResponse.model_validate(row)

    async def update_investor(self, investor_id: UUID, data: InvestorUpdate) -> InvestorResponse:
        row = await self._locked(FundingInvestor, investor_id, "Investidor não encontrado.")
        changes = self._apply(row, data.model_dump(exclude_unset=True))
        row.updated_at = utc_now()
        self._audit("INVESTOR", investor_id, "UPDATED", changes)
        await self._commit_and_refresh(row)
        return InvestorResponse.model_validate(row)

    async def list_contributions(
        self, investor_id: UUID | None = None
    ) -> list[ContributionResponse]:
        statement = select(FundingContribution)
        if investor_id is not None:
            if await self._session.get(FundingInvestor, investor_id) is None:
                raise FundingNotFoundError("Investidor não encontrado.")
            statement = statement.where(FundingContribution.investor_id == investor_id)
        rows = await self._session.scalars(
            statement.order_by(FundingContribution.contribution_date.desc(), FundingContribution.id)
        )
        return [self._contribution_response(row) for row in rows]

    async def get_contribution(self, contribution_id: UUID) -> ContributionResponse:
        row = await self._session.get(FundingContribution, contribution_id)
        if row is None:
            raise FundingNotFoundError("Aporte não encontrado.")
        return self._contribution_response(row)

    async def create_contribution(self, data: ContributionCreate) -> ContributionResponse:
        await self._require_investor(data.investor_id)
        entity_id = uuid4()
        locked_at = utc_now()
        row = FundingContribution(
            id=entity_id,
            code=f"APT-{entity_id.hex[:10].upper()}",
            original_amount_locked_at=locked_at,
            **data.model_dump(),
        )
        self._session.add(row)
        await self._flush_or_rollback()

        source = FundingSource(
            id=uuid4(),
            source_type="INVESTOR_CONTRIBUTION",
            contribution_id=entity_id,
            status="ACTIVE",
        )
        self._session.add(source)
        await self._flush_or_rollback()

        entry = FundingLedgerEntry(
            source_id=source.id,
            entry_type="CONTRIBUTION",
            amount=data.original_amount,
            direction=1,
            effective_date=data.contribution_date,
            origin_type="CONTRIBUTION",
            contribution_id=entity_id,
            actor=self._actor_label,
            notes="Entrada inicial do aporte.",
        )
        self._session.add(entry)
        self._audit("CONTRIBUTION", entity_id, "CREATED", data.model_dump(mode="json"))
        self._audit(
            "SOURCE",
            source.id,
            "CREATED",
            {
                "source_type": "INVESTOR_CONTRIBUTION",
                "contribution_id": str(entity_id),
            },
        )
        await self._commit_and_refresh(row)
        return self._contribution_response(row)

    async def update_contribution(
        self, contribution_id: UUID, data: ContributionUpdate
    ) -> ContributionResponse:
        row = await self._locked(FundingContribution, contribution_id, "Aporte não encontrado.")
        values = data.model_dump(exclude_unset=True)
        investor_id = values.get("investor_id")
        if investor_id is not None:
            await self._require_investor(investor_id)
        new_amount = values.get("original_amount")
        if (
            new_amount is not None
            and Decimal(new_amount) != row.original_amount
            and row.original_amount_locked_at is not None
        ):
            raise FundingConflictError(
                "O valor original não pode ser sobrescrito após movimentação financeira."
            )
        changes = self._apply(row, values)
        row.updated_at = utc_now()
        self._audit("CONTRIBUTION", contribution_id, "UPDATED", changes)
        await self._commit_and_refresh(row)
        return self._contribution_response(row)

    async def _require_investor(self, investor_id: UUID) -> None:
        if await self._session.get(FundingInvestor, investor_id) is None:
            raise FundingNotFoundError("Investidor não encontrado.")

    async def _locked(self, model, entity_id: UUID, message: str):
        row = await self._session.scalar(
            select(model).where(model.id == entity_id).with_for_update()
        )
        if row is None:
            raise FundingNotFoundError(message)
        return row

    @staticmethod
    def _apply(row, values: dict[str, Any]) -> dict[str, dict[str, Any]]:
        changes: dict[str, dict[str, Any]] = {}
        for field, value in values.items():
            previous = getattr(row, field)
            if previous != value:
                changes[field] = {
                    "from": FundingRepository._json_value(previous),
                    "to": FundingRepository._json_value(value),
                }
                setattr(row, field, value)
        return changes

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value

    def _audit(
        self, entity_type: str, entity_id: UUID, action: str, changes: dict[str, Any]
    ) -> None:
        self._session.add(
            FundingAuditEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changes=changes,
                actor_user_id=self._actor_user_id,
            )
        )

    async def _commit_and_refresh(self, row) -> None:
        try:
            await self._session.commit()
            await self._session.refresh(row)
        except Exception:
            await self._session.rollback()
            raise

    async def _flush_or_rollback(self) -> None:
        try:
            await self._session.flush()
        except Exception:
            await self._session.rollback()
            raise

    @staticmethod
    def _contribution_response(row: FundingContribution) -> ContributionResponse:
        return ContributionResponse.model_validate(
            {
                **row.__dict__,
                "original_amount_editable": row.original_amount_locked_at is None,
            }
        )
