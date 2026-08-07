class OperationalExcelError(Exception):
    """Base error with messages that never expose the configured source path."""


class SourceConfigurationError(OperationalExcelError):
    pass


class SourceUnavailableError(OperationalExcelError):
    pass


class SourceChangedDuringCopyError(OperationalExcelError):
    pass


class UnsupportedSourceError(OperationalExcelError):
    pass


class WorkbookAccessError(OperationalExcelError):
    pass


class UnauthorizedSheetError(WorkbookAccessError):
    pass


class SensitiveSheetAccessError(UnauthorizedSheetError):
    pass


class WorkbookStructureError(OperationalExcelError):
    pass


class MissingRequiredSheetError(WorkbookStructureError):
    pass


class MissingRequiredColumnError(WorkbookStructureError):
    pass


class DuplicateSourceError(OperationalExcelError):
    pass
