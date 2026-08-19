from __future__ import annotations

import hashlib
import shutil
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.excel.errors import (
    SourceChangedDuringCopyError,
    SourceConfigurationError,
    SourceUnavailableError,
    UnsupportedSourceError,
)

_STAGED_FILE_TOKEN = object()
_BLOCKED_SOURCE_NAMES = {"funding remo.xlsm"}


@dataclass(frozen=True, slots=True)
class FileMetadata:
    name: str
    size: int
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class StagedFile:
    copy_path: Path
    metadata: FileMetadata
    sha256: str
    _token: object

    def is_reader_approved(self) -> bool:
        return self._token is _STAGED_FILE_TOKEN


def _approved_staged_file(path: Path, metadata: FileMetadata, sha256: str) -> StagedFile:
    """Internal bridge used by trusted FileSource implementations."""
    return StagedFile(path, metadata, sha256, _STAGED_FILE_TOKEN)


class FileSource(ABC):
    @abstractmethod
    def stage(self) -> Iterator[StagedFile]:
        """Yield an isolated binary copy and remove it when the context exits."""


class LocalFileSource(FileSource):
    def __init__(self, source_path: Path | str | None) -> None:
        if source_path is None or not str(source_path).strip():
            raise SourceConfigurationError("OPERATIONAL_EXCEL_PATH não está configurado.")
        self._source_path = Path(source_path)

    def _metadata(self) -> FileMetadata:
        try:
            stat = self._source_path.stat()
        except (FileNotFoundError, OSError) as exc:
            raise SourceUnavailableError(
                "O arquivo operacional configurado não está disponível."
            ) from exc

        if not self._source_path.is_file():
            raise SourceUnavailableError("A origem operacional configurada não é um arquivo.")
        if self._source_path.name.casefold() in _BLOCKED_SOURCE_NAMES:
            raise UnsupportedSourceError("O arquivo legado não pode ser sincronizado.")
        if self._source_path.suffix.casefold() != ".xlsm":
            raise UnsupportedSourceError("A origem operacional deve ser um arquivo .xlsm.")

        return FileMetadata(
            name=self._source_path.name,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    @contextmanager
    def stage(self) -> Iterator[StagedFile]:
        before = self._metadata()
        with tempfile.TemporaryDirectory(prefix="remo-funding-operational-") as temp_dir:
            copy_path = Path(temp_dir) / f"operational-{uuid4().hex}.xlsm"
            try:
                shutil.copyfile(self._source_path, copy_path)
            except OSError as exc:
                raise SourceUnavailableError(
                    "Não foi possível criar a cópia temporária da origem operacional."
                ) from exc
            after = self._metadata()
            if (before.size, before.modified_at) != (after.size, after.modified_at):
                raise SourceChangedDuringCopyError(
                    "O arquivo operacional mudou durante a cópia; tente novamente."
                )
            digest = _sha256(copy_path)
            yield _approved_staged_file(copy_path, before, digest)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
