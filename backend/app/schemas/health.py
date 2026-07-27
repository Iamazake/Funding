from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    api: Literal["ok"]
    database: Literal["connected", "unavailable"]

