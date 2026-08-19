from app.services.operational.read import _display_client_name


def test_loan_name_is_display_fallback_without_changing_client_identity() -> None:
    assert _display_client_name(None, ("Cliente do Empréstimo", False)) == (
        "Cliente do Empréstimo",
        "ECON_EMPRESTIMOS",
        False,
    )


def test_canonical_name_wins_and_source_divergence_is_explicit() -> None:
    assert _display_client_name(
        "Cliente Canônico",
        ("Nome Diferente no Empréstimo", False),
    ) == ("Cliente Canônico", "CLIENT_CANONICAL", True)


def test_ambiguous_loan_names_are_not_used_as_fallback() -> None:
    assert _display_client_name(None, (None, True)) == (None, None, True)
