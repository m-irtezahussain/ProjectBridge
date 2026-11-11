from typing import Literal

from pydantic import BaseModel, ConfigDict


class ServiceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: Literal["projectbridge"] = "projectbridge"
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"


class ReadinessStatus(ServiceStatus):
    database: Literal["ok"] = "ok"

