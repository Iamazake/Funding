from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ConnectionStatus = Literal[
    "CONNECTED", "DISCONNECTED", "RECONNECT_REQUIRED", "FILE_NOT_FOUND"
]
UpdateStatus = Literal[
    "UNKNOWN", "CURRENT", "UPDATE_AVAILABLE", "FILE_NOT_FOUND", "RECONNECT_REQUIRED", "ERROR"
]


class IntegrationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OneDriveConnectResponse(IntegrationSchema):
    authorization_url: str
    expires_at: datetime


class OperationalSourceStatus(IntegrationSchema):
    source_type: Literal["local", "onedrive"]
    connection_status: ConnectionStatus
    update_status: UpdateStatus
    file_name: str | None = None
    file_path: str | None = None
    size: int | None = None
    modified_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_sync_sha256: str | None = None
    last_batch_id: int | None = None
    message: str


class SyncResponse(IntegrationSchema):
    sync_run_id: int
    import_batch_id: int | None = None
    status: str
    counters: dict[str, object]
    message: str
