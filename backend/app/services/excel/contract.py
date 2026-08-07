from __future__ import annotations

PARTIAL_PAYMENT_NOTE = "Pagamento parcial previsto para etapa futura."

AUTHORIZED_SHEETS = (
    "BCLI_CADASTRO",
    "DFEN_CONTRATO",
    "ECON_EMPRESTIMOS",
    "ECON_AMORTIZACOES",
)

SENSITIVE_SHEETS = frozenset(
    {
        "CAD_USUARIOS",
        "Planilha1",
        "BCLI_DADOS_BANCARIOS",
    }
)

APPROVED_COLUMNS: dict[str, tuple[str, ...]] = {
    "BCLI_CADASTRO": (
        "COD_CLIENTE",
        "CPF_CLIENTE",
        "NOME_CLIENTE",
        "DT_NASC",
    ),
    "DFEN_CONTRATO": (
        "COD_CLIENTE",
        "COD_CONTRATO",
        "NUM_CPF",
        "DT_OPERACAO",
        "VCTO_PRIM_PARC",
        "PRAZO",
        "PRINCIPAL",
        "IOF",
        "VL_FINANCIADO",
        "PMT",
        "VL_LIBERADO",
        "DATA_LIBERACAO",
    ),
    "ECON_EMPRESTIMOS": (
        "COD_CONTRATO",
        "COD_CLIENTE",
        "NUM_CPF",
        "DT_OPERACAO",
        "VENCIMENTO1",
        "VL_PRINCIPAL",
        "PRAZO_PGTO",
        "IOF",
        "VL_FINACIADO",
        "PMT",
        "VL_LIBERADO",
        "TAXA_JUROS",
        "TAXA_TIR",
        "TAXA_CET_AM",
        "STATUS",
    ),
    "ECON_AMORTIZACOES": (
        "COD_CLIENTE",
        "NUM_CPF",
        "COD_CONTRATO",
        "COD_PARCELA",
        "VENCIMENTO",
        "VAL_AMTZ_JUR",
        "VAL_AMTZ_PRINC",
        "VAL_PARCELA",
        "BAIXA _TOTAL",
        "DT_BAIXATOTAL",
        "VAL_PGTO",
        "DESCONTO_CONC",
        "STATUS_PARC",
        "SITUACAO",
        "BOL_ANTECIP",
        "PRODUTO_FINANCEIRO",
    ),
}

OPTIONAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "ECON_AMORTIZACOES": ("CHAVE",),
}
