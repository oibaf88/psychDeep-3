from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field

class MobileInferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    model_id: str = Field(min_length=1, max_length=192)
    model_version: str | None = Field(default=None, max_length=192)
    prompt_version: str | None = Field(default=None, max_length=96)
    input_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    output: dict
    output_schema: str | None = Field(default=None, max_length=96)
    client_platform: str = Field(default="android", min_length=1, max_length=32)
    client_app_version: str | None = Field(default=None, max_length=64)
    inference_engine: str | None = Field(default=None, max_length=64)
    client_model_checksum: str | None = Field(default=None, max_length=128)
    client_timestamp: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0, le=600000)

class MobileInferenceOut(BaseModel):
    event_id: uuid.UUID
    model_run_id: uuid.UUID
    deployment_alias: str = "mobile-local"
    status: str = "accepted"
    synced_at: datetime
