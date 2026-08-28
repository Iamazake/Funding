from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    String,
    Uuid,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    null,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtContinuityPredecessor,
)
from app.models.funding import FundingAllocation, FundingContribution, FundingInvestor
from app.models.identity import OperationalRevenueSnapshot, OperationalSaleSnapshot
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPromotion,
)
from app.models.operational import MONEY, utc_now
from app.models.treasury import TreasuryBankValidation
from app.schemas.treasury import (
    TreasuryMovementResponse,
    TreasuryMovementsResponse,
    TreasuryPageMeta,
    TreasurySummaryResponse,
    TreasuryValidationCreate,
    TreasuryValidationHistory,
    TreasuryValidationResponse,
    TreasuryValidationState,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class TreasuryQuery:
    page: int = 1
    page_size: int = 50
    period_from: date | None = None
    period_to: date | None = None
    movement_type: str | None = None
    search: str | None = None
    installment: str | None = None
    investor_id: UUID | None = None
    validation_status: str | None = None
    eligible_for_validation: bool = False


class TreasuryNotFoundError(LookupError):
    pass


class TreasuryConflictError(ValueError):
    pass


class TreasuryRepository:
    """Read-only cash projection over canonical funding and operational records."""

    def __init__(self, session: AsyncSession, actor_user_id: UUID | None = None) -> None:
        self._session = session
        self._actor_user_id = actor_user_id

    async def summary(self, query: TreasuryQuery) -> TreasurySummaryResponse:
        statement = self._filtered_movement_statement(query).subquery("filtered_treasury")
        row = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (statement.c.movement_type == "CONTRIBUTION", statement.c.amount),
                                else_=ZERO,
                            )
                        ),
                        ZERO,
                    ).label("contributions"),
                    func.coalesce(
                        func.sum(
                            case(
                                (statement.c.movement_type == "REVENUE", statement.c.amount),
                                else_=ZERO,
                            )
                        ),
                        ZERO,
                    ).label("revenues"),
                    func.coalesce(
                        func.sum(
                            case(
                                (statement.c.movement_type == "SALE", statement.c.amount),
                                else_=ZERO,
                            )
                        ),
                        ZERO,
                    ).label("sales"),
                    func.count()
                    .filter(statement.c.movement_type == "CONTRIBUTION")
                    .label("contribution_count"),
                    func.count()
                    .filter(statement.c.movement_type == "REVENUE")
                    .label("revenue_count"),
                    func.count().filter(statement.c.movement_type == "SALE").label("sale_count"),
                    func.count().filter(statement.c.movement_date.is_(None)).label("undated_count"),
                    func.count().filter(statement.c.amount.is_(None)).label("unknown_amount_count"),
                    func.count().filter(statement.c.validation_id.is_(None)).label("pending_count"),
                    func.count()
                    .filter(statement.c.validation_status == "VALIDATED")
                    .label("validated_count"),
                    func.count()
                    .filter(statement.c.validation_status == "DIVERGENT")
                    .label("divergent_count"),
                    func.coalesce(func.sum(statement.c.difference_amount), ZERO).label(
                        "net_difference"
                    ),
                )
            )
        ).one()
        contributions = Decimal(row.contributions)
        revenues = Decimal(row.revenues)
        sales = Decimal(row.sales)
        inflows = contributions + revenues
        return TreasurySummaryResponse(
            period_from=query.period_from,
            period_to=query.period_to,
            total_inflows=inflows,
            total_outflows=sales,
            known_net_flow=inflows - sales,
            contributions=contributions,
            revenues=revenues,
            sales=sales,
            contribution_count=int(row.contribution_count),
            revenue_count=int(row.revenue_count),
            sale_count=int(row.sale_count),
            undated_movement_count=int(row.undated_count),
            unknown_amount_count=int(row.unknown_amount_count),
            pending_validation_count=int(row.pending_count),
            validated_count=int(row.validated_count),
            divergent_count=int(row.divergent_count),
            net_difference_amount=Decimal(row.net_difference),
        )

    async def movements(self, query: TreasuryQuery) -> TreasuryMovementsResponse:
        statement = self._filtered_movement_statement(query)
        total = int(
            await self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        rows = (
            await self._session.execute(
                statement.order_by(
                    statement.selected_columns.movement_date.desc().nulls_last(),
                    statement.selected_columns.id.desc(),
                )
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size)
            )
        ).mappings()
        return TreasuryMovementsResponse(
            items=[self._movement_response(row) for row in rows],
            pagination=TreasuryPageMeta(
                page=query.page,
                page_size=query.page_size,
                total=total,
                pages=(total + query.page_size - 1) // query.page_size if total else 0,
            ),
        )

    async def get_movement(self, movement_id: str) -> TreasuryMovementResponse:
        movement_id = await self._canonical_movement_key(movement_id)
        statement = self._movement_statement()
        statement = statement.where(statement.selected_columns.id == movement_id)
        row = (await self._session.execute(statement)).mappings().one_or_none()
        if row is None:
            raise TreasuryNotFoundError("Movimento de Tesouraria não encontrado.")
        return self._movement_response(row)

    async def get_validation(self, movement_key: str) -> TreasuryValidationState:
        movement_key = await self._canonical_movement_key(movement_key)
        await self._require_movement(movement_key)
        current = await self._current_validation(movement_key)
        return TreasuryValidationState(
            movement_key=movement_key,
            status=current.status if current is not None else "PENDING",
            current=self._validation_response(current) if current is not None else None,
        )

    async def validation_history(self, movement_key: str) -> TreasuryValidationHistory:
        movement_key = await self._canonical_movement_key(movement_key)
        await self._require_movement(movement_key)
        rows = list(
            await self._session.scalars(
                select(TreasuryBankValidation)
                .where(TreasuryBankValidation.movement_key == movement_key)
                .order_by(TreasuryBankValidation.version.desc())
            )
        )
        return TreasuryValidationHistory(
            movement_key=movement_key,
            items=[self._validation_response(item) for item in rows],
        )

    async def validate_movement(
        self,
        movement_key: str,
        data: TreasuryValidationCreate,
    ) -> TreasuryValidationResponse:
        try:
            movement_key = await self._canonical_movement_key(movement_key)
            movement = await self._require_movement(movement_key)
            if movement.amount is None or movement.amount <= ZERO:
                raise TreasuryConflictError(
                    "Movimento sem valor positivo não pode ser validado no banco."
                )
            await self._session.execute(
                select(func.pg_advisory_xact_lock(func.hashtextextended(movement_key, literal(0))))
            )
            current = await self._session.scalar(
                select(TreasuryBankValidation)
                .where(
                    TreasuryBankValidation.movement_key == movement_key,
                    TreasuryBankValidation.is_current.is_(True),
                )
                .with_for_update()
            )
            expected, observed, difference, status = validation_outcome(
                movement.amount,
                data.observed_amount,
                data.justification,
            )
            if current is not None:
                current.is_current = False
            validation = TreasuryBankValidation(
                id=uuid4(),
                movement_key=movement_key,
                version=current.version + 1 if current is not None else 1,
                is_current=True,
                supersedes_validation_id=current.id if current is not None else None,
                movement_type=movement.movement_type,
                sale_identity_id=(
                    UUID(movement_key.split(":", 1)[1])
                    if movement.movement_type == "SALE"
                    else None
                ),
                revenue_identity_id=(
                    UUID(movement_key.split(":", 1)[1])
                    if movement.movement_type == "REVENUE"
                    else None
                ),
                direction=movement.direction,
                system_amount_snapshot=expected,
                system_date_snapshot=movement.movement_date,
                observed_amount=observed,
                observed_date=data.observed_date,
                difference_amount=difference,
                status=status,
                bank_reference=data.bank_reference,
                bank_code=data.bank_code,
                justification=data.justification,
                validated_at=utc_now(),
                validated_by=self._actor_user_id,
            )
            self._session.add(validation)
            await self._session.flush()
            await self._session.commit()
            await self._session.refresh(validation)
            return self._validation_response(validation)
        except Exception:
            await self._session.rollback()
            raise

    async def _require_movement(self, movement_key: str) -> TreasuryMovementResponse:
        try:
            return await self.get_movement(movement_key)
        except TreasuryNotFoundError:
            raise

    async def _current_validation(self, movement_key: str) -> TreasuryBankValidation | None:
        return await self._session.scalar(
            select(TreasuryBankValidation).where(
                TreasuryBankValidation.movement_key == movement_key,
                TreasuryBankValidation.is_current.is_(True),
            )
        )

    async def _canonical_movement_key(self, movement_key: str) -> str:
        legacy_match = await self._session.scalar(
            select(TreasuryBankValidation.movement_key).where(
                TreasuryBankValidation.legacy_movement_key == movement_key
            )
        )
        if legacy_match is not None:
            return legacy_match
        if movement_key.startswith("sale:contract:"):
            try:
                snapshot_id = int(movement_key.rsplit(":", 1)[1])
            except ValueError:
                return movement_key
            identity_id = await self._session.scalar(
                select(OperationalSaleSnapshot.sale_identity_id).where(
                    OperationalSaleSnapshot.contract_id == snapshot_id
                )
            )
            return f"sale:{identity_id}" if identity_id else movement_key
        if movement_key.startswith("sale:loan:"):
            try:
                snapshot_id = int(movement_key.rsplit(":", 1)[1])
            except ValueError:
                return movement_key
            identity_id = await self._session.scalar(
                select(OperationalSaleSnapshot.sale_identity_id).where(
                    OperationalSaleSnapshot.loan_id == snapshot_id
                )
            )
            return f"sale:{identity_id}" if identity_id else movement_key
        if movement_key.startswith("revenue:"):
            raw_id = movement_key.split(":", 1)[1]
            try:
                UUID(raw_id)
                return movement_key
            except ValueError:
                try:
                    snapshot_id = int(raw_id)
                except ValueError:
                    return movement_key
            identity_id = await self._session.scalar(
                select(OperationalRevenueSnapshot.revenue_identity_id).where(
                    OperationalRevenueSnapshot.installment_id == snapshot_id
                )
            )
            return f"revenue:{identity_id}" if identity_id else movement_key
        return movement_key

    def _movement_statement(self):
        movements = self._movement_union().subquery("derived_treasury_movements")
        validation = TreasuryBankValidation
        return select(
            *[movements.c[column] for column in movements.c.keys()],
            validation.id.label("validation_id"),
            validation.status.label("validation_status"),
            validation.observed_amount,
            validation.observed_date,
            validation.difference_amount,
            validation.bank_reference,
            validation.bank_code,
            validation.validated_at,
            validation.validated_by,
            validation.justification.label("validation_justification"),
        ).outerjoin(
            validation,
            and_(
                validation.movement_key == movements.c.id,
                validation.is_current.is_(True),
            ),
        )

    def _filtered_movement_statement(self, query: TreasuryQuery):
        statement = self._movement_statement()
        columns = statement.selected_columns
        conditions = []
        if query.period_from is not None:
            conditions.append(columns.movement_date >= query.period_from)
        if query.period_to is not None:
            conditions.append(columns.movement_date <= query.period_to)
        if query.movement_type is not None:
            conditions.append(columns.movement_type == query.movement_type)
        if query.investor_id is not None:
            conditions.append(columns.investor_id == query.investor_id)
        if query.search and query.search.strip():
            pattern = f"%{query.search.strip().casefold()}%"
            conditions.append(
                func.lower(
                    func.concat_ws(
                        " ",
                        columns.reference,
                        columns.description,
                        columns.contract_code,
                        columns.client_name,
                        columns.investor_name,
                    )
                ).like(pattern)
            )
        if query.installment and query.installment.strip():
            conditions.append(
                func.lower(columns.installment_code).like(
                    f"%{query.installment.strip().casefold()}%"
                )
            )
        if query.validation_status == "PENDING":
            conditions.append(columns.validation_id.is_(None))
        elif query.validation_status in {"VALIDATED", "DIVERGENT"}:
            conditions.append(columns.validation_status == query.validation_status)
        if query.eligible_for_validation:
            conditions.extend((columns.amount.is_not(None), columns.amount > ZERO))
        return statement.where(*conditions)

    def _movement_union(self):
        promotion_id = (
            select(OperationalPromotion.id)
            .where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
            .scalar_subquery()
        )
        zero = literal(ZERO, type_=MONEY)
        null_uuid = cast(null(), Uuid(as_uuid=True))
        null_text = cast(null(), String)
        null_bigint = cast(null(), BigInteger)
        null_money = cast(null(), MONEY)

        def continuity_state(sale_identity_id):
            confirmed_statuses = ("REFIN_CONFIRMED", "RENEGOTIATION_CONFIRMED")
            is_predecessor = exists(
                select(OperationalDebtContinuityPredecessor.id).where(
                    OperationalDebtContinuityPredecessor.continuity_id
                    == OperationalDebtContinuity.id,
                    OperationalDebtContinuityPredecessor.sale_identity_id
                    == sale_identity_id,
                    OperationalDebtContinuityPredecessor.is_current.is_(True),
                )
            )
            continuity_filter = (
                or_(
                    OperationalDebtContinuity.successor_sale_identity_id == sale_identity_id,
                    is_predecessor,
                ),
                OperationalDebtContinuity.status.in_(confirmed_statuses),
            )
            latest_type = (
                select(OperationalDebtContinuity.continuity_type)
                .where(*continuity_filter)
                .order_by(
                    OperationalDebtContinuity.updated_at.desc(),
                    OperationalDebtContinuity.id.desc(),
                )
                .limit(1)
                .correlate_except(OperationalDebtContinuity)
                .scalar_subquery()
            )
            latest_role = (
                select(
                    case(
                        (
                            OperationalDebtContinuity.successor_sale_identity_id
                            == sale_identity_id,
                            "SUCCESSOR",
                        ),
                        else_="PREDECESSOR",
                    )
                )
                .where(*continuity_filter)
                .order_by(
                    OperationalDebtContinuity.updated_at.desc(),
                    OperationalDebtContinuity.id.desc(),
                )
                .limit(1)
                .correlate_except(OperationalDebtContinuity)
                .scalar_subquery()
            )
            return latest_type, latest_role

        allocation_totals = (
            select(
                FundingAllocation.sale_id.label("sale_id"),
                func.sum(FundingAllocation.amount).label("identified_amount"),
                func.count(FundingAllocation.id).label("allocation_count"),
            )
            .where(FundingAllocation.status == "ACTIVE")
            .group_by(FundingAllocation.sale_id)
            .subquery("active_funding_allocation_totals")
        )

        def funding_status_for(base_amount):
            return case(
                (allocation_totals.c.allocation_count.is_(None), "NOT_INFORMED"),
                (base_amount.is_(None), "BASE_AMOUNT_UNAVAILABLE"),
                (allocation_totals.c.identified_amount < base_amount, "INCOMPLETE"),
                (allocation_totals.c.identified_amount > base_amount, "OVERFUNDED"),
                else_="COMPLETE",
            )

        contribution_id = cast(FundingContribution.id, String)
        contribution = (
            select(
                (literal("contribution:") + contribution_id).label("id"),
                literal("CONTRIBUTION").label("movement_type"),
                literal("INFLOW").label("direction"),
                FundingContribution.contribution_date.label("movement_date"),
                FundingContribution.code.label("reference"),
                func.concat("Aporte recebido de ", FundingInvestor.name).label("description"),
                null_text.label("contract_code"),
                null_text.label("client_name"),
                null_text.label("installment_code"),
                null_text.label("data_quality_status"),
                null_text.label("funding_status"),
                FundingInvestor.id.label("investor_id"),
                FundingInvestor.name.label("investor_name"),
                FundingContribution.original_amount.label("inflow"),
                zero.label("outflow"),
                FundingContribution.original_amount.label("amount"),
                null_text.label("sale_id"),
                null_money.label("released_amount"),
                null_text.label("continuity_type"),
                null_text.label("continuity_role"),
                literal("funding_contributions").label("origin"),
                contribution_id.label("source_record_id"),
                null_bigint.label("source_batch_id"),
                (literal("/cadastro/aportes/") + contribution_id).label("detail_path"),
                FundingContribution.status.label("source_status"),
            )
            .select_from(FundingContribution)
            .join(FundingInvestor, FundingInvestor.id == FundingContribution.investor_id)
        )

        contract_sale_id = literal("sale:") + cast(OperationalSaleSnapshot.sale_identity_id, String)
        contract_continuity_type, contract_continuity_role = continuity_state(
            OperationalSaleSnapshot.sale_identity_id
        )
        contract_is_rollover = exists(
            select(OperationalDebtContinuity.id).where(
                OperationalDebtContinuity.successor_sale_identity_id
                == OperationalSaleSnapshot.sale_identity_id,
                OperationalDebtContinuity.predecessor_sale_identity_id
                != OperationalDebtContinuity.successor_sale_identity_id,
                OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED",
                OperationalDebtContinuity.has_new_disbursement.is_(False),
            )
        )
        contract = (
            select(
                contract_sale_id.label("id"),
                literal("SALE").label("movement_type"),
                literal("OUTFLOW").label("direction"),
                OperationalContract.operation_date.label("movement_date"),
                contract_sale_id.label("reference"),
                func.concat(
                    "Liberação da Venda ",
                    func.coalesce(OperationalContract.contract_code, contract_sale_id),
                    case(
                        (
                            OperationalClient.name.is_not(None),
                            func.concat(" para ", OperationalClient.name),
                        ),
                        else_="",
                    ),
                ).label("description"),
                OperationalContract.contract_code.label("contract_code"),
                OperationalClient.name.label("client_name"),
                null_text.label("installment_code"),
                OperationalContract.data_quality_status.label("data_quality_status"),
                funding_status_for(OperationalContract.released_amount).label("funding_status"),
                null_uuid.label("investor_id"),
                null_text.label("investor_name"),
                zero.label("inflow"),
                OperationalContract.released_amount.label("outflow"),
                OperationalContract.released_amount.label("amount"),
                contract_sale_id.label("sale_id"),
                OperationalContract.released_amount.label("released_amount"),
                contract_continuity_type.label("continuity_type"),
                contract_continuity_role.label("continuity_role"),
                literal("operational_contracts").label("origin"),
                contract_sale_id.label("source_record_id"),
                OperationalContract.current_source_batch_id.label("source_batch_id"),
                (literal("/vendas/") + contract_sale_id).label("detail_path"),
                func.coalesce(
                    OperationalContract.operational_status,
                    OperationalContract.data_quality_status,
                ).label("source_status"),
            )
            .select_from(OperationalContract)
            .join(
                OperationalSaleSnapshot,
                OperationalSaleSnapshot.contract_id == OperationalContract.id,
            )
            .outerjoin(
                OperationalClient,
                OperationalClient.id == OperationalContract.client_id,
            )
            .outerjoin(
                allocation_totals,
                allocation_totals.c.sale_id == contract_sale_id,
            )
            .where(
                OperationalContract.promotion_id == promotion_id,
                ~contract_is_rollover,
            )
        )

        loan_sale_id = literal("sale:") + cast(OperationalSaleSnapshot.sale_identity_id, String)
        loan_continuity_type, loan_continuity_role = continuity_state(
            OperationalSaleSnapshot.sale_identity_id
        )
        loan_is_rollover = exists(
            select(OperationalDebtContinuity.id).where(
                OperationalDebtContinuity.successor_sale_identity_id
                == OperationalSaleSnapshot.sale_identity_id,
                OperationalDebtContinuity.predecessor_sale_identity_id
                != OperationalDebtContinuity.successor_sale_identity_id,
                OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED",
                OperationalDebtContinuity.has_new_disbursement.is_(False),
            )
        )
        loan = (
            select(
                loan_sale_id.label("id"),
                literal("SALE").label("movement_type"),
                literal("OUTFLOW").label("direction"),
                OperationalLoan.operation_date.label("movement_date"),
                loan_sale_id.label("reference"),
                func.concat(
                    "Liberação da Venda ",
                    func.coalesce(OperationalLoan.contract_code, loan_sale_id),
                    case(
                        (
                            OperationalClient.name.is_not(None),
                            func.concat(" para ", OperationalClient.name),
                        ),
                        else_="",
                    ),
                ).label("description"),
                OperationalLoan.contract_code.label("contract_code"),
                OperationalClient.name.label("client_name"),
                null_text.label("installment_code"),
                OperationalLoan.data_quality_status.label("data_quality_status"),
                funding_status_for(OperationalLoan.released_amount).label("funding_status"),
                null_uuid.label("investor_id"),
                null_text.label("investor_name"),
                zero.label("inflow"),
                OperationalLoan.released_amount.label("outflow"),
                OperationalLoan.released_amount.label("amount"),
                loan_sale_id.label("sale_id"),
                OperationalLoan.released_amount.label("released_amount"),
                loan_continuity_type.label("continuity_type"),
                loan_continuity_role.label("continuity_role"),
                literal("operational_loans").label("origin"),
                loan_sale_id.label("source_record_id"),
                OperationalLoan.current_source_batch_id.label("source_batch_id"),
                (literal("/vendas/") + loan_sale_id).label("detail_path"),
                func.coalesce(
                    OperationalLoan.operational_status,
                    OperationalLoan.data_quality_status,
                ).label("source_status"),
            )
            .select_from(OperationalLoan)
            .join(
                OperationalSaleSnapshot,
                OperationalSaleSnapshot.loan_id == OperationalLoan.id,
            )
            .outerjoin(
                OperationalClient,
                OperationalClient.id == OperationalLoan.client_id,
            )
            .outerjoin(
                allocation_totals,
                allocation_totals.c.sale_id == loan_sale_id,
            )
            .where(
                OperationalLoan.promotion_id == promotion_id,
                OperationalLoan.contract_id.is_(None),
                ~loan_is_rollover,
            )
        )

        revenue_id = cast(OperationalRevenueSnapshot.revenue_identity_id, String)
        revenue_sale_id = literal("sale:") + cast(
            OperationalSaleSnapshot.sale_identity_id, String
        )
        revenue_continuity_type, revenue_continuity_role = continuity_state(
            OperationalSaleSnapshot.sale_identity_id
        )
        revenue_reference = func.coalesce(
            OperationalInstallment.source_key,
            literal("Receita #") + revenue_id,
        )
        revenue = (
            select(
                (literal("revenue:") + revenue_id).label("id"),
                literal("REVENUE").label("movement_type"),
                literal("INFLOW").label("direction"),
                OperationalInstallment.payment_date.label("movement_date"),
                revenue_reference.label("reference"),
                func.concat(
                    "Recebimento de Receita ",
                    revenue_reference,
                    case(
                        (
                            OperationalClient.name.is_not(None),
                            func.concat(" de ", OperationalClient.name),
                        ),
                        else_="",
                    ),
                ).label("description"),
                func.coalesce(
                    OperationalInstallment.contract_code,
                    OperationalContract.contract_code,
                ).label("contract_code"),
                OperationalClient.name.label("client_name"),
                OperationalInstallment.installment_code.label("installment_code"),
                OperationalInstallment.data_quality_status.label("data_quality_status"),
                null_text.label("funding_status"),
                null_uuid.label("investor_id"),
                null_text.label("investor_name"),
                OperationalInstallment.paid_amount.label("inflow"),
                zero.label("outflow"),
                OperationalInstallment.paid_amount.label("amount"),
                revenue_sale_id.label("sale_id"),
                OperationalContract.released_amount.label("released_amount"),
                revenue_continuity_type.label("continuity_type"),
                revenue_continuity_role.label("continuity_role"),
                literal("operational_installments").label("origin"),
                revenue_id.label("source_record_id"),
                OperationalInstallment.current_source_batch_id.label("source_batch_id"),
                (literal("/receita/") + cast(OperationalInstallment.id, String)).label(
                    "detail_path"
                ),
                func.coalesce(
                    OperationalInstallment.installment_status,
                    OperationalInstallment.data_quality_status,
                ).label("source_status"),
            )
            .select_from(OperationalInstallment)
            .join(
                OperationalRevenueSnapshot,
                OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
            )
            .outerjoin(
                OperationalContract,
                OperationalContract.id == OperationalInstallment.contract_id,
            )
            .outerjoin(
                OperationalSaleSnapshot,
                and_(
                    OperationalSaleSnapshot.promotion_id
                    == OperationalInstallment.promotion_id,
                    OperationalSaleSnapshot.contract_id == OperationalInstallment.contract_id,
                ),
            )
            .outerjoin(
                OperationalClient,
                OperationalClient.id == OperationalContract.client_id,
            )
            .where(
                OperationalInstallment.promotion_id == promotion_id,
                OperationalInstallment.payment_date.is_not(None),
                OperationalInstallment.paid_amount.is_not(None),
                OperationalInstallment.paid_amount > ZERO,
            )
        )
        return union_all(contribution, contract, loan, revenue)

    @staticmethod
    def _movement_response(row) -> TreasuryMovementResponse:
        return TreasuryMovementResponse(
            id=row["id"],
            movement_type=row["movement_type"],
            direction=row["direction"],
            movement_date=row["movement_date"],
            reference=row["reference"],
            description=row["description"],
            contract_code=row["contract_code"],
            client_name=row["client_name"],
            installment_code=row["installment_code"],
            data_quality_status=row["data_quality_status"],
            funding_status=row["funding_status"],
            investor_id=row["investor_id"],
            investor_name=row["investor_name"],
            inflow=row["inflow"],
            outflow=row["outflow"],
            amount=row["amount"],
            sale_id=row["sale_id"],
            released_amount=row["released_amount"],
            continuity_type=row["continuity_type"],
            continuity_role=row["continuity_role"],
            origin=row["origin"],
            source_record_id=row["source_record_id"],
            source_batch_id=row["source_batch_id"],
            detail_path=row["detail_path"],
            status=row["source_status"],
            validation_status=row["validation_status"] or "PENDING",
            validation_id=row["validation_id"],
            observed_amount=row["observed_amount"],
            observed_date=row["observed_date"],
            difference_amount=row["difference_amount"],
            bank_reference=row["bank_reference"],
            bank_code=row["bank_code"],
            validated_at=row["validated_at"],
            validated_by=row["validated_by"],
            validation_justification=row["validation_justification"],
        )

    @staticmethod
    def _validation_response(
        validation: TreasuryBankValidation,
    ) -> TreasuryValidationResponse:
        return TreasuryValidationResponse.model_validate(validation)

    async def _load_movements(self) -> list[TreasuryMovementResponse]:
        contribution_rows = (
            await self._session.execute(
                select(FundingContribution, FundingInvestor).join(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
            )
        ).all()
        promotion_id = await self._session.scalar(
            select(OperationalPromotion.id).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
        )
        if promotion_id is None:
            raise RuntimeError("Nenhuma promoção operacional atual está disponível.")
        contract_rows = (
            await self._session.execute(
                select(OperationalContract, OperationalClient, OperationalSaleSnapshot)
                .join(
                    OperationalSaleSnapshot,
                    OperationalSaleSnapshot.contract_id == OperationalContract.id,
                )
                .outerjoin(
                    OperationalClient,
                    OperationalClient.id == OperationalContract.client_id,
                )
                .where(OperationalContract.promotion_id == promotion_id)
                .where(
                    ~exists(
                        select(OperationalDebtContinuity.id).where(
                            OperationalDebtContinuity.successor_sale_identity_id
                            == OperationalSaleSnapshot.sale_identity_id,
                            OperationalDebtContinuity.predecessor_sale_identity_id
                            != OperationalDebtContinuity.successor_sale_identity_id,
                            OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED",
                            OperationalDebtContinuity.has_new_disbursement.is_(False),
                        )
                    )
                )
            )
        ).all()
        orphan_rows = (
            await self._session.execute(
                select(OperationalLoan, OperationalClient, OperationalSaleSnapshot)
                .join(
                    OperationalSaleSnapshot,
                    OperationalSaleSnapshot.loan_id == OperationalLoan.id,
                )
                .outerjoin(
                    OperationalClient,
                    OperationalClient.id == OperationalLoan.client_id,
                )
                .where(
                    OperationalLoan.promotion_id == promotion_id,
                    OperationalLoan.contract_id.is_(None),
                    ~exists(
                        select(OperationalDebtContinuity.id).where(
                            OperationalDebtContinuity.successor_sale_identity_id
                            == OperationalSaleSnapshot.sale_identity_id,
                            OperationalDebtContinuity.predecessor_sale_identity_id
                            != OperationalDebtContinuity.successor_sale_identity_id,
                            OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED",
                            OperationalDebtContinuity.has_new_disbursement.is_(False),
                        )
                    ),
                )
            )
        ).all()
        revenue_rows = (
            await self._session.execute(
                select(
                    OperationalInstallment,
                    OperationalContract,
                    OperationalClient,
                    OperationalRevenueSnapshot,
                )
                .join(
                    OperationalRevenueSnapshot,
                    OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
                )
                .outerjoin(
                    OperationalContract,
                    OperationalContract.id == OperationalInstallment.contract_id,
                )
                .outerjoin(
                    OperationalClient,
                    OperationalClient.id == OperationalContract.client_id,
                )
                .where(
                    OperationalInstallment.promotion_id == promotion_id,
                    OperationalInstallment.payment_date.is_not(None),
                    OperationalInstallment.paid_amount.is_not(None),
                    OperationalInstallment.paid_amount > ZERO,
                )
            )
        ).all()
        return [
            *[
                contribution_movement(contribution, investor)
                for contribution, investor in contribution_rows
            ],
            *[
                sale_movement(
                    contract,
                    client,
                    orphan=False,
                    canonical_identity_id=snapshot.sale_identity_id,
                )
                for contract, client, snapshot in contract_rows
            ],
            *[
                sale_movement(
                    loan,
                    client,
                    orphan=True,
                    canonical_identity_id=snapshot.sale_identity_id,
                )
                for loan, client, snapshot in orphan_rows
            ],
            *[
                revenue_movement(
                    installment,
                    contract,
                    client,
                    canonical_identity_id=snapshot.revenue_identity_id,
                )
                for installment, contract, client, snapshot in revenue_rows
            ],
        ]


def contribution_movement(
    contribution: FundingContribution,
    investor: FundingInvestor,
) -> TreasuryMovementResponse:
    return TreasuryMovementResponse(
        id=f"contribution:{contribution.id}",
        movement_type="CONTRIBUTION",
        direction="INFLOW",
        movement_date=contribution.contribution_date,
        reference=contribution.code,
        description=f"Aporte recebido de {investor.name}",
        contract_code=None,
        investor_id=investor.id,
        investor_name=investor.name,
        inflow=contribution.original_amount,
        outflow=ZERO,
        amount=contribution.original_amount,
        origin="funding_contributions",
        source_record_id=str(contribution.id),
        source_batch_id=None,
        detail_path=f"/cadastro/aportes/{contribution.id}",
        status=contribution.status,
    )


def validation_outcome(
    system_amount: Decimal,
    observed_amount: Decimal,
    justification: str | None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    expected = system_amount.quantize(CENT, rounding=ROUND_HALF_UP)
    observed = observed_amount.quantize(CENT, rounding=ROUND_HALF_UP)
    difference = observed - expected
    status = "VALIDATED" if difference == ZERO else "DIVERGENT"
    if status == "DIVERGENT" and not justification:
        raise TreasuryConflictError("Justificativa é obrigatória para uma validação divergente.")
    return expected, observed, difference, status


def sale_movement(
    sale: OperationalContract | OperationalLoan,
    client: OperationalClient | None,
    *,
    orphan: bool,
    canonical_identity_id: UUID | None = None,
) -> TreasuryMovementResponse:
    legacy_sale_id = f"{'loan' if orphan else 'contract'}:{sale.id}"
    sale_id = f"sale:{canonical_identity_id}" if canonical_identity_id else legacy_sale_id
    amount = sale.released_amount
    identity = sale.contract_code or sale_id
    description = f"Liberação da Venda {identity}" + (
        f" para {client.name}" if client and client.name else ""
    )
    return TreasuryMovementResponse(
        id=sale_id if canonical_identity_id else f"sale:{sale_id}",
        movement_type="SALE",
        direction="OUTFLOW",
        movement_date=sale.operation_date,
        reference=sale_id,
        description=description,
        contract_code=sale.contract_code,
        investor_id=None,
        investor_name=None,
        inflow=ZERO,
        outflow=amount,
        amount=amount,
        sale_id=sale_id if canonical_identity_id else None,
        released_amount=amount,
        origin="operational_loans" if orphan else "operational_contracts",
        source_record_id=sale_id,
        source_batch_id=sale.current_source_batch_id,
        detail_path=f"/vendas/{sale_id}",
        status=sale.operational_status or sale.data_quality_status,
    )


def revenue_movement(
    installment: OperationalInstallment,
    contract: OperationalContract | None,
    client: OperationalClient | None,
    *,
    canonical_identity_id: UUID | None = None,
) -> TreasuryMovementResponse:
    amount = installment.paid_amount
    assert installment.payment_date is not None
    assert amount is not None and amount > ZERO
    contract_code = installment.contract_code or (
        contract.contract_code if contract is not None else None
    )
    reference = installment.source_key or f"Receita #{installment.id}"
    description = f"Recebimento de Receita {reference}"
    if client and client.name:
        description += f" de {client.name}"
    return TreasuryMovementResponse(
        id=f"revenue:{canonical_identity_id or installment.id}",
        movement_type="REVENUE",
        direction="INFLOW",
        movement_date=installment.payment_date,
        reference=reference,
        description=description,
        contract_code=contract_code,
        investor_id=None,
        investor_name=None,
        inflow=amount,
        outflow=ZERO,
        amount=amount,
        released_amount=contract.released_amount if contract is not None else None,
        origin="operational_installments",
        source_record_id=str(canonical_identity_id or installment.id),
        source_batch_id=installment.current_source_batch_id,
        detail_path=f"/receita/{installment.id}",
        status=installment.installment_status or installment.data_quality_status,
    )


def filter_treasury_movements(
    movements: list[TreasuryMovementResponse],
    query: TreasuryQuery,
) -> list[TreasuryMovementResponse]:
    search = (query.search or "").strip().casefold()
    return [
        movement
        for movement in movements
        if (query.movement_type is None or movement.movement_type == query.movement_type)
        and (query.investor_id is None or movement.investor_id == query.investor_id)
        and (
            query.period_from is None
            or (movement.movement_date is not None and movement.movement_date >= query.period_from)
        )
        and (
            query.period_to is None
            or (movement.movement_date is not None and movement.movement_date <= query.period_to)
        )
        and (
            not search
            or search
            in " ".join(
                filter(
                    None,
                    (
                        movement.reference,
                        movement.description,
                        movement.contract_code,
                        movement.investor_name,
                    ),
                )
            ).casefold()
        )
        and (
            query.validation_status is None or movement.validation_status == query.validation_status
        )
    ]


def summarize_treasury_movements(
    movements: list[TreasuryMovementResponse],
    period_from: date | None = None,
    period_to: date | None = None,
) -> TreasurySummaryResponse:
    contributions = _sum_type(movements, "CONTRIBUTION")
    revenues = _sum_type(movements, "REVENUE")
    sales = _sum_type(movements, "SALE")
    inflows = contributions + revenues
    return TreasurySummaryResponse(
        period_from=period_from,
        period_to=period_to,
        total_inflows=inflows,
        total_outflows=sales,
        known_net_flow=inflows - sales,
        contributions=contributions,
        revenues=revenues,
        sales=sales,
        contribution_count=sum(item.movement_type == "CONTRIBUTION" for item in movements),
        revenue_count=sum(item.movement_type == "REVENUE" for item in movements),
        sale_count=sum(item.movement_type == "SALE" for item in movements),
        undated_movement_count=sum(item.movement_date is None for item in movements),
        unknown_amount_count=sum(item.amount is None for item in movements),
        pending_validation_count=sum(item.validation_status == "PENDING" for item in movements),
        validated_count=sum(item.validation_status == "VALIDATED" for item in movements),
        divergent_count=sum(item.validation_status == "DIVERGENT" for item in movements),
        net_difference_amount=sum(
            (item.difference_amount for item in movements if item.difference_amount is not None),
            start=ZERO,
        ),
    )


def _sum_type(movements: list[TreasuryMovementResponse], movement_type: str) -> Decimal:
    return sum(
        (
            movement.amount
            for movement in movements
            if movement.movement_type == movement_type and movement.amount is not None
        ),
        start=ZERO,
    )
