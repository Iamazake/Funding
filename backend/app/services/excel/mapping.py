from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.services.excel.contract import AUTHORIZED_SHEETS, PARTIAL_PAYMENT_NOTE
from app.services.excel.parsers import (
    ParseIssue,
    mask_sensitive_value,
    normalize_code,
    normalize_name,
    parse_cpf,
    parse_date,
    parse_integer,
    parse_money,
    parse_rate,
    serialize_raw,
)
from app.services.excel.reader import OperationalWorkbookReader, SheetRow


@dataclass(slots=True)
class MirrorRow:
    source_sheet: str
    source_row_number: int
    source_row_hash: str
    source_key: str | None
    validation_status: str
    validation_errors: list[dict[str, str | None]]
    raw_data: dict[str, Any]
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Inconsistency:
    source_sheet: str
    source_row_number: int
    inconsistency_type: str
    field_name: str | None
    message: str
    masked_value: str | None
    severity: str


@dataclass(slots=True)
class WorkbookImport:
    rows: dict[str, list[MirrorRow]] = field(
        default_factory=lambda: {sheet: [] for sheet in AUTHORIZED_SHEETS}
    )
    inconsistencies: list[Inconsistency] = field(default_factory=list)

    def counters(self) -> dict[str, Any]:
        sheets: dict[str, dict[str, int]] = {}
        total_rows = 0
        for sheet, rows in self.rows.items():
            status = Counter(row.validation_status for row in rows)
            sheets[sheet] = {
                "read": len(rows),
                "valid": status["valid"],
                "warning": status["warning"],
                "divergent": status["divergent"],
                "invalid": status["invalid"],
            }
            total_rows += len(rows)
        return {
            "total_rows": total_rows,
            "total_inconsistencies": len(self.inconsistencies),
            "sheets": sheets,
        }


class WorkbookMapper:
    def map(self, reader: OperationalWorkbookReader) -> WorkbookImport:
        imported = WorkbookImport()
        for sheet_name in AUTHORIZED_SHEETS:
            for sheet_row in reader.iter_sheet(sheet_name):
                row, inconsistencies = self._map_row(sheet_name, sheet_row, reader.epoch)
                imported.rows[sheet_name].append(row)
                imported.inconsistencies.extend(inconsistencies)
        self._validate_unique_contract_codes(imported)
        self._validate_relationships(imported)
        return imported

    def _map_row(
        self, sheet_name: str, sheet_row: SheetRow, epoch: datetime
    ) -> tuple[MirrorRow, list[Inconsistency]]:
        raw_data = {key: serialize_raw(value) for key, value in sheet_row.values.items()}
        errors: list[dict[str, str | None]] = []
        inconsistencies: list[Inconsistency] = []

        def capture(field_name: str, parsed, raw_value: Any, *, severity: str):
            if parsed.issue is not None:
                error = _issue_payload(field_name, parsed.issue, severity)
                errors.append(error)
                inconsistencies.append(
                    Inconsistency(
                        source_sheet=sheet_name,
                        source_row_number=sheet_row.number,
                        inconsistency_type=parsed.issue.kind,
                        field_name=field_name,
                        message=parsed.issue.message,
                        masked_value=mask_sensitive_value(field_name, raw_value),
                        severity=severity,
                    )
                )
            return parsed.value

        def require_identifier(field_name: str, value: str | None, raw_value: Any) -> None:
            if value is None:
                issue = ParseIssue(
                    "missing_required_identifier",
                    "Identificador operacional obrigatório ausente.",
                )
                error = _issue_payload(field_name, issue, "invalid")
                errors.append(error)
                inconsistencies.append(
                    Inconsistency(
                        source_sheet=sheet_name,
                        source_row_number=sheet_row.number,
                        inconsistency_type=issue.kind,
                        field_name=field_name,
                        message=issue.message,
                        masked_value=mask_sensitive_value(field_name, raw_value),
                        severity="invalid",
                    )
                )

        values = sheet_row.values
        if sheet_name == "BCLI_CADASTRO":
            cod_cliente = normalize_code(values["COD_CLIENTE"])
            cpf = capture(
                "CPF_CLIENTE",
                parse_cpf(values["CPF_CLIENTE"]),
                values["CPF_CLIENTE"],
                severity="warning",
            )
            data = {
                "cod_cliente_original": _text(values["COD_CLIENTE"]),
                "cod_cliente": cod_cliente,
                "cpf_original": _text(values["CPF_CLIENTE"]),
                "cpf_normalized": cpf,
                "nome_cliente_original": _text(values["NOME_CLIENTE"]),
                "nome_cliente": normalize_name(values["NOME_CLIENTE"]),
                "dt_nasc_original": _text(values["DT_NASC"]),
                "dt_nasc": capture(
                    "DT_NASC",
                    parse_date(values["DT_NASC"], epoch=epoch),
                    values["DT_NASC"],
                    severity="warning",
                ),
            }
            source_key = cod_cliente or cpf
            if source_key is None and values["CPF_CLIENTE"] in (None, ""):
                require_identifier("COD_CLIENTE/CPF_CLIENTE", None, None)
        elif sheet_name == "DFEN_CONTRATO":
            data = {
                "cod_cliente": normalize_code(values["COD_CLIENTE"]),
                "cod_contrato": normalize_code(values["COD_CONTRATO"]),
                "cpf_original": _text(values["NUM_CPF"]),
                "cpf_normalized": capture(
                    "NUM_CPF",
                    parse_cpf(values["NUM_CPF"]),
                    values["NUM_CPF"],
                    severity="warning",
                ),
                "dt_operacao": capture(
                    "DT_OPERACAO",
                    parse_date(values["DT_OPERACAO"], epoch=epoch),
                    values["DT_OPERACAO"],
                    severity="warning",
                ),
                "vcto_prim_parc": capture(
                    "VCTO_PRIM_PARC",
                    parse_date(values["VCTO_PRIM_PARC"], epoch=epoch),
                    values["VCTO_PRIM_PARC"],
                    severity="warning",
                ),
                "prazo": capture(
                    "PRAZO",
                    parse_integer(values["PRAZO"]),
                    values["PRAZO"],
                    severity="warning",
                ),
                "principal": capture(
                    "PRINCIPAL",
                    parse_money(values["PRINCIPAL"]),
                    values["PRINCIPAL"],
                    severity="invalid",
                ),
                "iof": capture(
                    "IOF",
                    parse_money(values["IOF"]),
                    values["IOF"],
                    severity="warning",
                ),
                "vl_financiado": capture(
                    "VL_FINANCIADO",
                    parse_money(values["VL_FINANCIADO"]),
                    values["VL_FINANCIADO"],
                    severity="warning",
                ),
                "pmt": capture(
                    "PMT",
                    parse_money(values["PMT"]),
                    values["PMT"],
                    severity="warning",
                ),
                "vl_liberado": capture(
                    "VL_LIBERADO",
                    parse_money(values["VL_LIBERADO"]),
                    values["VL_LIBERADO"],
                    severity="warning",
                ),
                "data_liberacao": capture(
                    "DATA_LIBERACAO",
                    parse_date(values["DATA_LIBERACAO"], epoch=epoch),
                    values["DATA_LIBERACAO"],
                    severity="warning",
                ),
            }
            source_key = data["cod_contrato"]
            require_identifier("COD_CONTRATO", source_key, values["COD_CONTRATO"])
        elif sheet_name == "ECON_EMPRESTIMOS":
            data = {
                "cod_contrato": normalize_code(values["COD_CONTRATO"]),
                "cod_cliente": normalize_code(values["COD_CLIENTE"]),
                "cpf_original": _text(values["NUM_CPF"]),
                "cpf_normalized": capture(
                    "NUM_CPF",
                    parse_cpf(values["NUM_CPF"]),
                    values["NUM_CPF"],
                    severity="warning",
                ),
                "dt_operacao": capture(
                    "DT_OPERACAO",
                    parse_date(values["DT_OPERACAO"], epoch=epoch),
                    values["DT_OPERACAO"],
                    severity="warning",
                ),
                "vencimento1": capture(
                    "VENCIMENTO1",
                    parse_date(values["VENCIMENTO1"], epoch=epoch),
                    values["VENCIMENTO1"],
                    severity="warning",
                ),
                "vl_principal": capture(
                    "VL_PRINCIPAL",
                    parse_money(values["VL_PRINCIPAL"]),
                    values["VL_PRINCIPAL"],
                    severity="invalid",
                ),
                "prazo_pgto": capture(
                    "PRAZO_PGTO",
                    parse_integer(values["PRAZO_PGTO"]),
                    values["PRAZO_PGTO"],
                    severity="warning",
                ),
                "iof": capture(
                    "IOF",
                    parse_money(values["IOF"]),
                    values["IOF"],
                    severity="warning",
                ),
                "vl_finaciado": capture(
                    "VL_FINACIADO",
                    parse_money(values["VL_FINACIADO"]),
                    values["VL_FINACIADO"],
                    severity="warning",
                ),
                "pmt": capture(
                    "PMT",
                    parse_money(values["PMT"]),
                    values["PMT"],
                    severity="warning",
                ),
                "vl_liberado": capture(
                    "VL_LIBERADO",
                    parse_money(values["VL_LIBERADO"]),
                    values["VL_LIBERADO"],
                    severity="warning",
                ),
                "taxa_juros": capture(
                    "TAXA_JUROS",
                    parse_rate(values["TAXA_JUROS"]),
                    values["TAXA_JUROS"],
                    severity="warning",
                ),
                "taxa_tir": capture(
                    "TAXA_TIR",
                    parse_rate(values["TAXA_TIR"]),
                    values["TAXA_TIR"],
                    severity="warning",
                ),
                "taxa_cet_am": capture(
                    "TAXA_CET_AM",
                    parse_rate(values["TAXA_CET_AM"]),
                    values["TAXA_CET_AM"],
                    severity="warning",
                ),
                "status": _text(values["STATUS"]),
            }
            source_key = data["cod_contrato"]
            require_identifier("COD_CONTRATO", source_key, values["COD_CONTRATO"])
        else:
            data = {
                "cod_cliente": normalize_code(values["COD_CLIENTE"]),
                "cpf_original": _text(values["NUM_CPF"]),
                "cpf_normalized": capture(
                    "NUM_CPF",
                    parse_cpf(values["NUM_CPF"]),
                    values["NUM_CPF"],
                    severity="warning",
                ),
                "cod_contrato": normalize_code(values["COD_CONTRATO"]),
                "cod_parcela": normalize_code(values["COD_PARCELA"]),
                "vencimento": capture(
                    "VENCIMENTO",
                    parse_date(values["VENCIMENTO"], epoch=epoch),
                    values["VENCIMENTO"],
                    severity="warning",
                ),
                "val_amtz_jur": capture(
                    "VAL_AMTZ_JUR",
                    parse_money(values["VAL_AMTZ_JUR"]),
                    values["VAL_AMTZ_JUR"],
                    severity="warning",
                ),
                "val_amtz_princ": capture(
                    "VAL_AMTZ_PRINC",
                    parse_money(values["VAL_AMTZ_PRINC"]),
                    values["VAL_AMTZ_PRINC"],
                    severity="warning",
                ),
                "val_parcela": capture(
                    "VAL_PARCELA",
                    parse_money(values["VAL_PARCELA"]),
                    values["VAL_PARCELA"],
                    severity="invalid",
                ),
                "baixa_total_original": _text(values["BAIXA _TOTAL"]),
                "dt_baixatotal": capture(
                    "DT_BAIXATOTAL",
                    parse_date(values["DT_BAIXATOTAL"], epoch=epoch),
                    values["DT_BAIXATOTAL"],
                    severity="warning",
                ),
                "val_pgto": capture(
                    "VAL_PGTO",
                    parse_money(values["VAL_PGTO"]),
                    values["VAL_PGTO"],
                    severity="warning",
                ),
                "desconto_conc": capture(
                    "DESCONTO_CONC",
                    parse_money(values["DESCONTO_CONC"]),
                    values["DESCONTO_CONC"],
                    severity="warning",
                ),
                "status_parc": _text(values["STATUS_PARC"]),
                "situacao": _text(values["SITUACAO"]),
                "chave_referencia": _text(values.get("CHAVE")),
                "bol_antecip": _text(values["BOL_ANTECIP"]),
                "produto_financeiro": _text(values["PRODUTO_FINANCEIRO"]),
            }
            source_key = _joined_key(data["cod_contrato"], data["cod_parcela"])
            require_identifier("COD_CONTRATO", data["cod_contrato"], values["COD_CONTRATO"])
            require_identifier("COD_PARCELA", data["cod_parcela"], values["COD_PARCELA"])

        return (
            MirrorRow(
                source_sheet=sheet_name,
                source_row_number=sheet_row.number,
                source_row_hash=_row_hash(raw_data),
                source_key=source_key,
                validation_status=_validation_status(errors),
                validation_errors=errors,
                raw_data=raw_data,
                data=data,
            ),
            inconsistencies,
        )

    def _validate_unique_contract_codes(self, imported: WorkbookImport) -> None:
        expected_unique = (
            ("DFEN_CONTRATO", "duplicate_dfen_contract_code"),
            ("ECON_EMPRESTIMOS", "duplicate_loan_contract_code"),
        )
        for sheet_name, issue_type in expected_unique:
            seen: set[str] = set()
            for row in imported.rows[sheet_name]:
                contract = row.data["cod_contrato"]
                if contract and contract in seen:
                    self._relationship_issue(
                        imported,
                        row,
                        issue_type,
                        "COD_CONTRATO",
                        "Código de contrato duplicado em base com unicidade esperada.",
                        severity="divergent",
                    )
                if contract:
                    seen.add(contract)

    def _validate_relationships(self, imported: WorkbookImport) -> None:
        clients = imported.rows["BCLI_CADASTRO"]
        client_codes = {row.data["cod_cliente"] for row in clients if row.data["cod_cliente"]}
        client_cpfs = {row.data["cpf_normalized"] for row in clients if row.data["cpf_normalized"]}
        contracts = imported.rows["DFEN_CONTRATO"]
        contract_codes = {row.data["cod_contrato"] for row in contracts if row.data["cod_contrato"]}
        loans = imported.rows["ECON_EMPRESTIMOS"]
        loan_codes = {row.data["cod_contrato"] for row in loans if row.data["cod_contrato"]}

        for row in contracts:
            if (
                row.data["cod_cliente"] not in client_codes
                and row.data["cpf_normalized"] not in client_cpfs
            ):
                self._relationship_issue(
                    imported,
                    row,
                    "orphan_contract",
                    "COD_CLIENTE",
                    "Contrato sem cliente no espelho.",
                    severity="divergent",
                )

        for row in loans:
            if row.data["cod_contrato"] not in contract_codes:
                self._relationship_issue(
                    imported,
                    row,
                    "orphan_loan",
                    "COD_CONTRATO",
                    "Empréstimo sem DFEN_CONTRATO correspondente.",
                    severity="divergent",
                )

        seen_installments: set[tuple[str, str]] = set()
        for row in imported.rows["ECON_AMORTIZACOES"]:
            contract = row.data["cod_contrato"]
            installment = row.data["cod_parcela"]
            if contract not in contract_codes:
                self._relationship_issue(
                    imported,
                    row,
                    "orphan_amortization_contract",
                    "COD_CONTRATO",
                    "Amortização sem DFEN_CONTRATO correspondente.",
                    severity="divergent",
                )
            if contract not in loan_codes:
                self._relationship_issue(
                    imported,
                    row,
                    "orphan_amortization_loan",
                    "COD_CONTRATO",
                    "Amortização sem ECON_EMPRESTIMOS correspondente.",
                    severity="divergent",
                )
            if contract and installment:
                natural_key = (contract, installment)
                if natural_key in seen_installments:
                    self._relationship_issue(
                        imported,
                        row,
                        "multiple_payment_movements",
                        "COD_CONTRATO+COD_PARCELA",
                        f"Múltiplos movimentos observados. {PARTIAL_PAYMENT_NOTE}",
                        severity="info",
                    )
                seen_installments.add(natural_key)

    @staticmethod
    def _relationship_issue(
        imported: WorkbookImport,
        row: MirrorRow,
        issue_type: str,
        field_name: str,
        message: str,
        *,
        severity: str,
    ) -> None:
        payload = {
            "type": issue_type,
            "field": field_name,
            "message": message,
            "severity": severity,
        }
        row.validation_errors.append(payload)
        row.validation_status = _highest_status(row.validation_status, severity)
        imported.inconsistencies.append(
            Inconsistency(
                source_sheet=row.source_sheet,
                source_row_number=row.source_row_number,
                inconsistency_type=issue_type,
                field_name=field_name,
                message=message,
                masked_value=mask_sensitive_value(field_name, row.source_key),
                severity=severity,
            )
        )


def _issue_payload(
    field_name: str, issue: ParseIssue, severity: str
) -> dict[str, str | None]:
    return {
        "type": issue.kind,
        "field": field_name,
        "message": issue.message,
        "severity": severity,
    }


def _validation_status(errors: list[dict[str, str | None]]) -> str:
    status = "valid"
    for error in errors:
        status = _highest_status(status, error.get("severity") or "warning")
    return status


def _highest_status(current: str, candidate: str) -> str:
    rank = {"info": 0, "valid": 0, "warning": 1, "divergent": 2, "invalid": 3}
    return candidate if rank[candidate] > rank[current] else current


def _row_hash(raw_data: dict[str, Any]) -> str:
    payload = json.dumps(raw_data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _joined_key(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    return f"{left or ''}:{right or ''}"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(serialize_raw(value))
