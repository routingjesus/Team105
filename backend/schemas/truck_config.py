"""Request/response models for truck file generation.

This module is the canonical API contract that SPEC-002 (stop generator)
and SPEC-003 (wizard UI) mirror. Field semantics come from the legacy
"Explode my Trucks.xlsxm" macro baseline documented in the PRD.
"""

from pydantic import BaseModel, Field, field_validator


def _validate_ascii(value: str, field_name: str) -> str:
    """Generated content must stay ASCII-only so cp1252 (VBA `Print #`)
    and UTF-8-without-BOM byte streams are identical."""
    if not value.isascii():
        raise ValueError(f"{field_name} must contain only ASCII characters")
    if any(ch in value for ch in ("\t", "\r", "\n")):
        raise ValueError(f"{field_name} must not contain tabs or line breaks")
    return value


class VolumeSpec(BaseModel):
    """A named volume (e.g. Cube, Weight) with per-truck capacity."""

    name: str = Field(min_length=1)
    capacity: float = Field(gt=0)

    @field_validator("name")
    @classmethod
    def name_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "volume name")


class DepotSpec(BaseModel):
    """A DC/depot with its address and fleet size.

    `trucks` is the number of trucks (territories) exploded for this depot;
    territory numbering (T01, T02, ...) continues across depots.
    """

    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    trucks: int = Field(gt=0)

    @field_validator("address", "city", "state", "zip")
    @classmethod
    def fields_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "depot field")


class TruckConfig(BaseModel):
    """Generation request. Defaults match the Explode my Trucks macro."""

    weeks: int = Field(gt=0, description="Routing weeks; dispatch days = weeks * 7")
    depots: list[DepotSpec] = Field(min_length=1)
    mi_cost: float = Field(default=1.39, ge=0)
    hr_cost: float = Field(default=30.00, ge=0)
    fixed_cost: float = Field(default=250.00, ge=0)
    max_work: float = Field(default=14, gt=0, description="MaxWorkTm, hours")
    max_drive: float = Field(default=11, gt=0, description="MaxDriveTm, hours")
    pre_trip: int = Field(default=15, ge=0, description="PreTrip, minutes")
    post_trip: int = Field(default=30, ge=0, description="PostTrip, minutes")
    sp_eq: str = Field(default="", description="SpEq equipment code applied to all trucks")
    volumes: list[VolumeSpec] = Field(default_factory=list)
    seed: int = Field(default=0, description="Deterministic RNG seed")

    @field_validator("sp_eq")
    @classmethod
    def sp_eq_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "sp_eq")

    @field_validator("volumes")
    @classmethod
    def volume_names_unique(cls, v: list[VolumeSpec]) -> list[VolumeSpec]:
        names = [vol.name for vol in v]
        if len(names) != len(set(names)):
            raise ValueError("volume names must be unique")
        return v

    @property
    def territory_count(self) -> int:
        return sum(depot.trucks for depot in self.depots)


class DepotSummary(BaseModel):
    """Depot echo in the generation response, for downstream stop generation."""

    address: str
    city: str
    state: str
    zip: str
    truck_count: int


class TruckGenerationResponse(BaseModel):
    """Metadata plus base64-encoded .TRUCK content (AC6 routing metadata)."""

    truck_row_count: int
    weeks: int
    territory_count: int
    depot_count: int
    depots: list[DepotSummary]
    volume_names: list[VolumeSpec]
    seed: int
    filename: str
    truck_file_base64: str
