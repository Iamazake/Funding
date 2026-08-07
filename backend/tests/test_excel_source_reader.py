from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.excel.errors import (
    MissingRequiredColumnError,
    MissingRequiredSheetError,
    SensitiveSheetAccessError,
    UnauthorizedSheetError,
)
from app.services.excel.reader import OperationalWorkbookReader
from app.services.excel.source import LocalFileSource
from tests.excel_helpers import create_workbook


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reader_opens_only_unique_temporary_copy_and_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = create_workbook(tmp_path / "Cadastro de Clientes.xlsm")
    original_hash = file_hash(original)
    opened_paths: list[Path] = []

    from app.services.excel import reader as reader_module

    real_loader = reader_module.load_workbook

    def recording_loader(*args, **kwargs):
        opened_paths.append(Path(kwargs["filename"]))
        return real_loader(*args, **kwargs)

    monkeypatch.setattr(reader_module, "load_workbook", recording_loader)
    with LocalFileSource(original).stage() as staged:
        copy_path = staged.copy_path
        assert copy_path != original
        assert copy_path.exists()
        with OperationalWorkbookReader(staged) as reader:
            reader.validate_layout()

    assert opened_paths == [copy_path]
    assert original not in opened_paths
    assert file_hash(original) == original_hash
    assert not copy_path.exists()


def test_temporary_copy_is_removed_even_when_reader_fails(tmp_path: Path) -> None:
    original = create_workbook(
        tmp_path / "Cadastro de Clientes.xlsm", missing_sheet="DFEN_CONTRATO"
    )
    copy_path: Path | None = None
    with pytest.raises(MissingRequiredSheetError):
        with LocalFileSource(original).stage() as staged:
            copy_path = staged.copy_path
            with OperationalWorkbookReader(staged) as reader:
                reader.validate_layout()
    assert copy_path is not None
    assert not copy_path.exists()


def test_sensitive_and_other_unauthorized_sheets_are_blocked(tmp_path: Path) -> None:
    original = create_workbook(tmp_path / "Cadastro de Clientes.xlsm")
    with LocalFileSource(original).stage() as staged:
        with OperationalWorkbookReader(staged) as reader:
            reader.validate_layout()
            with pytest.raises(SensitiveSheetAccessError):
                list(reader.iter_sheet("CAD_USUARIOS"))
            with pytest.raises(SensitiveSheetAccessError):
                list(reader.iter_sheet("Planilha1"))
            with pytest.raises(SensitiveSheetAccessError):
                list(reader.iter_sheet("BCLI_DADOS_BANCARIOS"))
            with pytest.raises(UnauthorizedSheetError):
                list(reader.iter_sheet("NAO_AUTORIZADA"))


def test_missing_required_sheet_is_structural_error(tmp_path: Path) -> None:
    original = create_workbook(
        tmp_path / "Cadastro de Clientes.xlsm", missing_sheet="ECON_EMPRESTIMOS"
    )
    with LocalFileSource(original).stage() as staged:
        with OperationalWorkbookReader(staged) as reader:
            with pytest.raises(MissingRequiredSheetError):
                reader.validate_layout()


def test_missing_required_column_is_structural_error(tmp_path: Path) -> None:
    original = create_workbook(
        tmp_path / "Cadastro de Clientes.xlsm",
        missing_column=("DFEN_CONTRATO", "COD_CONTRATO"),
    )
    with LocalFileSource(original).stage() as staged:
        with OperationalWorkbookReader(staged) as reader:
            with pytest.raises(MissingRequiredColumnError):
                reader.validate_layout()
