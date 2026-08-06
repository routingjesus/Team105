"""Request/response models for geocoding and location_db persistence (SPEC-017)."""

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.schemas.truck_config import _validate_ascii

WGS84_LAT_MIN = -90.0
WGS84_LAT_MAX = 90.0
WGS84_LON_MIN = -180.0
WGS84_LON_MAX = 180.0


def _validate_coords(latitude: float, longitude: float) -> tuple[float, float]:
    if not (WGS84_LAT_MIN <= latitude <= WGS84_LAT_MAX):
        raise ValueError(f"latitude must be between {WGS84_LAT_MIN} and {WGS84_LAT_MAX}")
    if not (WGS84_LON_MIN <= longitude <= WGS84_LON_MAX):
        raise ValueError(f"longitude must be between {WGS84_LON_MIN} and {WGS84_LON_MAX}")
    return latitude, longitude


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip: str = Field(min_length=1)

    @field_validator("address", "city", "state", "zip")
    @classmethod
    def fields_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "geocode field")


class GeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    formatted_address: str | None = None
    provider: str = "trimble-single-search"


class LocationEntry(BaseModel):
    """A location row to append to location_db."""

    address: str = Field(min_length=1)
    address2: str = Field(default="")
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    latitude: float
    longitude: float

    @field_validator("address", "city", "state", "zip", "address2")
    @classmethod
    def fields_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "location field")

    @model_validator(mode="after")
    def coords_in_range(self) -> "LocationEntry":
        _validate_coords(self.latitude, self.longitude)
        return self


class LocationAppendResponse(BaseModel):
    name: str
    id1: str
    latitude: float
    longitude: float
    message: str = "Location added to database"


class LocationDuplicateResponse(BaseModel):
    existing_name: str
    existing_id1: str
    latitude: float
    longitude: float
    message: str = "A location with this address already exists in the database"
