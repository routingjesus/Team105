"""Request/response models for DRProject.config generation (SPEC-012)."""

from pydantic import BaseModel

from backend.schemas.stop_config import StopConfig


class DrprojectConfigResponse(BaseModel):
    """Metadata plus base64-encoded DRProject.config XML content."""

    filename: str
    drproject_config_file_base64: str


# Re-export StopConfig as the request body — the generator only needs aliases
# and volumes, which are already on StopConfig alongside truck context.
DrprojectConfigRequest = StopConfig
