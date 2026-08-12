"""Request/response models for truck file generation.

This module is the canonical API contract that SPEC-002 (stop generator)
and SPEC-003 (wizard UI) mirror. Field semantics come from the legacy
"Explode my Trucks.xlsxm" macro baseline documented in the PRD.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError


def _validate_ascii(value: str, field_name: str) -> str:
    """Generated content must stay ASCII-only so cp1252 (VBA `Print #`)
    and UTF-8-without-BOM byte streams are identical."""
    if not value.isascii():
        raise ValueError(f"{field_name} must contain only ASCII characters")
    if any(ch in value for ch in ("\t", "\r", "\n")):
        raise ValueError(f"{field_name} must not contain tabs or line breaks")
    return value


class _LocationCompleteness(Protocol):
    address: str
    city: str
    state: str
    zip: str
    latitude: float | None
    longitude: float | None


TLocation = TypeVar("TLocation", bound=_LocationCompleteness)


def _has_valid_coordinates(latitude: float | None, longitude: float | None) -> bool:
    """Match wizard `hasValidCoordinates`: both present, in bounds, not (0, 0)."""
    if latitude is None or longitude is None:
        return False
    if latitude == 0 and longitude == 0:
        return False
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def _has_complete_address(address: str, city: str, state: str, zip_code: str) -> bool:
    return all(part.strip() for part in (address, city, state, zip_code))


def require_coords_or_address(model: TLocation) -> TLocation:
    """Either-or completeness: valid coords, a full address quartet, or both.

    Raises field-level `Required` errors (not a model-scoped ValueError) so
    FastAPI 422 `loc`s map onto `depots.N.address` / `manualStops.N.city`.
    """
    if _has_valid_coordinates(model.latitude, model.longitude):
        return model
    if _has_complete_address(model.address, model.city, model.state, model.zip):
        return model
    errors: list[InitErrorDetails] = []
    for field_name in ("address", "city", "state", "zip"):
        value = getattr(model, field_name)
        if not str(value).strip():
            errors.append(
                {
                    "type": PydanticCustomError("required", "Required"),
                    "loc": (field_name,),
                    "input": value,
                }
            )
    if errors:
        raise ValidationError.from_exception_data(type(model).__name__, errors)
    return model


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
    Optional latitude/longitude are session paste values (SPEC-019). A depot
    is complete with valid coords, a full address quartet, or both (SPEC-020);
    omitted coords emit blank cells in the truck file.
    """

    address: str = Field(default="")
    city: str = Field(default="")
    state: str = Field(default="")
    zip: str = Field(default="")
    trucks: int = Field(gt=0)
    latitude: float | None = Field(default=None, description="Optional WGS84 latitude")
    longitude: float | None = Field(default=None, description="Optional WGS84 longitude")

    @field_validator("address", "city", "state", "zip")
    @classmethod
    def fields_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "depot field")

    @field_validator("latitude")
    @classmethod
    def latitude_bounds(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (-90.0 <= v <= 90.0):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def longitude_bounds(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (-180.0 <= v <= 180.0):
            raise ValueError("longitude must be between -180 and 180")
        return v

    @model_validator(mode="after")
    def coords_or_address(self) -> "DepotSpec":
        return require_coords_or_address(self)


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
    latitude: float | None = Field(default=None, description="Inline WGS84 latitude (SPEC-019)")
    longitude: float | None = Field(default=None, description="Inline WGS84 longitude (SPEC-019)")


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
