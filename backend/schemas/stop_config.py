"""Request/response models for stop file generation (SPEC-002).

Imports depot/volume shapes from `backend.schemas.truck_config` (SPEC-001's
canonical contract) rather than redefining them, per that module's own
docstring and SPEC-002's research findings.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.schemas.truck_config import DepotSummary, VolumeSpec, _validate_ascii

# Per the owner-supplied golden stop-file templates: Frequency represents
# service occurrences per week (1 = 1x/wk; .5 = 2x/mo; .25 = 1x/mo; sub-.25
# values are quarterly-and-longer cadences).
FREQUENCY_VALUES: tuple[float, ...] = (7, 6, 5, 4, 3, 2, 1, 0.5, 0.25, 0.125, 0.083, 0.077)

# Pattern1 uses one letter per day of week, Sunday-first, matching the
# DirectRoute SMTWRFA convention. "A" stands in for Saturday.
PATTERN_DAY_LETTERS = "SMTWRFA"

# SPEC-011: DirectRoute draws Symbol ("shape") and Color from a fixed,
# product-defined list. This is the authoritative "Optional Colors" /
# "Optional Shapes" allowlist from the owner-supplied DirectRoute
# supplemental reference document (see SPEC-011's meta.yaml learnings for
# provenance), superseding the earlier anecdotal placeholder list.
SHAPE_VALUES: tuple[str, ...] = (
    "Circle",
    "Square",
    "Diamond",
    "Hdiamond",
    "Vdiamond",
    "UpArrow",
    "DnArrow",
    "RtArrow",
    "LfArrow",
    "Plus",
    "X",
    "Asterick",
    "Truck",
    "Star1",
    "Plane",
    "TruckSW",
    "TruckNW",
    "TruckE",
    "TruckNE",
    "TruckSE",
    "TruckS",
    "TruckN",
    "Car",
    "Bus",
    "Boat",
    "House",
    "Church",
    "School",
    "Factory",
    "Tower",
    "Pin",
    "Flag",
    "Cross",
    "Phone",
    "Star2",
    "Star3",
)
COLOR_VALUES: tuple[str, ...] = (
    "Black",
    "Blue",
    "Brick",
    "Chocolate",
    "Crimson",
    "Cyan",
    "DarkBlue",
    "DarkGray",
    "DarkGreen",
    "DarkKhaki",
    "DarkOlive",
    "DarkPurple",
    "DarkRed",
    "DarkTeal",
    "Fuchsia",
    "Gray",
    "Green",
    "LemonChiffon",
    "LightBlue",
    "LightCyan",
    "LightGray",
    "LightGreen",
    "LightPeach",
    "LightPink",
    "LightViolet",
    "LightYellow",
    "Lime",
    "LimeGreen",
    "Maroon",
    "MediumBlue",
    "Navy",
    "Olive",
    "Orange",
    "Orchid",
    "PaleGreen",
    "PaleTurquoise",
    "Peach",
    "Pink",
    "Purple",
    "Red",
    "RoyalBlue",
    "SaddleBrown",
    "Silver",
    "Teal",
    "Turquoise",
    "Violet",
    "White",
    "Yellow",
)

# Single source of truth for aliasable output columns -> AliasConfig
# attribute names, reused by both AliasConfig's own validation and
# backend.generators.stop.build_header's header substitution.
ALIAS_FIELD_MAP: dict[str, str] = {
    "Name": "name",
    "Contact": "contact",
    "Phone": "phone",
    "ID1": "id1",
    "ID2": "id2",
    "ID3": "id3",
    "Address_2": "address_2",
}


def _military_to_minutes(value: int) -> int:
    return (value // 100) * 60 + (value % 100)


def validate_time_window(open1: int, close1: int, fixed_time_minutes: float) -> bool:
    """True iff the window is in-range and wide enough to fit FixedTime."""
    if not (0 <= open1 <= close1 <= 2359):
        return False
    width_minutes = _military_to_minutes(close1) - _military_to_minutes(open1)
    return width_minutes >= fixed_time_minutes


class SelectionConfig(BaseModel):
    """How candidate stops are drawn from the static location database."""

    mode: Literal["radius", "state", "zip"]
    radius_miles: float | None = Field(default=None, gt=0)
    states: list[str] | None = Field(default=None, min_length=1)
    zips: list[str] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def mode_matches_fields(self) -> "SelectionConfig":
        if self.mode == "radius" and self.radius_miles is None:
            raise ValueError("radius_miles is required when mode is 'radius'")
        if self.mode == "state" and not self.states:
            raise ValueError("states is required when mode is 'state'")
        if self.mode == "zip" and not self.zips:
            raise ValueError("zips is required when mode is 'zip'")
        return self

    @field_validator("states")
    @classmethod
    def states_ascii(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [_validate_ascii(s, "state") for s in v]

    @field_validator("zips")
    @classmethod
    def zips_normalized(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        normalized: list[str] = []
        for zip_code in v:
            text = _validate_ascii(zip_code, "zip")
            digits = text.strip()
            if not digits:
                raise ValueError("zips entries must be non-empty")
            if not digits.isdigit() or len(digits) > 5:
                raise ValueError(f"invalid zip code: {zip_code!r}")
            normalized.append(digits.zfill(5))
        return normalized


class ManualStop(BaseModel):
    """Session-only stop supplied by the wizard (not persisted to location_db)."""

    address: str = Field(min_length=1)
    address2: str = Field(default="")
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("address", "address2", "city", "state", "zip")
    @classmethod
    def fields_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "manual stop field")

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


class VolumeAnswer(BaseModel):
    """How a single truck-config volume is populated on stop rows."""

    name: str = Field(min_length=1)
    mode: Literal["fixed", "averaged"]
    value: float = Field(gt=0, description="Fixed value, or averaged-mode target mean")

    @field_validator("name")
    @classmethod
    def name_ascii(cls, v: str) -> str:
        return _validate_ascii(v, "volume answer name")


class TimeWindowConfig(BaseModel):
    """Open1/Close1/Pattern1 generation strategy."""

    mode: Literal["fixed", "randomized"]
    open1: int | None = Field(default=None, ge=0, le=2359)
    close1: int | None = Field(default=None, ge=0, le=2359)
    pattern_scope: Literal["week", "weekday", "weekend", "random", "specific_days"] = "week"
    specific_days: list[Literal["S", "M", "T", "W", "R", "F", "A"]] | None = None

    @model_validator(mode="after")
    def fixed_requires_window(self) -> "TimeWindowConfig":
        if self.mode == "fixed":
            if self.open1 is None or self.close1 is None:
                raise ValueError("open1 and close1 are required when mode is 'fixed'")
        if self.pattern_scope == "specific_days" and not self.specific_days:
            raise ValueError("specific_days is required when pattern_scope is 'specific_days'")
        return self


class EqCodeConfig(BaseModel):
    """Optional EQ code randomization across a subset of stops."""

    enabled: bool = True
    codes: list[str] = Field(min_length=1)
    fraction: float = Field(default=0.25, gt=0, le=1)

    @field_validator("codes")
    @classmethod
    def codes_ascii(cls, v: list[str]) -> list[str]:
        return [_validate_ascii(c, "EQ code") for c in v]


class ConsolidationConfig(BaseModel):
    """Optional multi-line-item consolidation testing."""

    enabled: bool = True
    lines_per_customer: int = Field(gt=1, le=20)


class AliasConfig(BaseModel):
    """Header aliases for the named passthrough fields."""

    name: str | None = None
    contact: str | None = None
    phone: str | None = None
    id1: str | None = None
    id2: str | None = None
    id3: str | None = None
    address_2: str | None = None

    @model_validator(mode="after")
    def aliases_ascii(self) -> "AliasConfig":
        for field_name in ALIAS_FIELD_MAP.values():
            value = getattr(self, field_name)
            if value is not None:
                _validate_ascii(value, f"alias for {field_name}")
        return self


class StopConfig(BaseModel):
    """Generation request: truck-config context plus stop question answers."""

    depots: list[DepotSummary] = Field(min_length=1)
    weeks: int = Field(gt=0)
    volumes: list[VolumeSpec] = Field(min_length=1)

    selection: SelectionConfig
    stop_count: int = Field(gt=0, description="Target output stop count after density thinning")
    fixed_time_minutes: float = Field(gt=0, description="Stop service duration (FixedTime)")

    volume_answers: list[VolumeAnswer] = Field(min_length=1)
    frequency_values: list[float] = Field(min_length=1)
    time_window: TimeWindowConfig
    eq_code: EqCodeConfig | None = None
    consolidation: ConsolidationConfig | None = None
    aliases: AliasConfig | None = None
    generate_shapes: bool = False
    generate_colors: bool = False
    manual_stops: list[ManualStop] = Field(default_factory=list)
    seed: int = Field(default=0)

    @field_validator("frequency_values")
    @classmethod
    def frequency_values_known(cls, v: list[float]) -> list[float]:
        unknown = [val for val in v if val not in FREQUENCY_VALUES]
        if unknown:
            raise ValueError(f"unknown frequency value(s): {unknown}; must be a subset of {FREQUENCY_VALUES}")
        return v

    @model_validator(mode="after")
    def volume_answers_match_volumes(self) -> "StopConfig":
        volume_names = {v.name for v in self.volumes}
        answer_names = {a.name for a in self.volume_answers}
        unknown = answer_names - volume_names
        if unknown:
            raise ValueError(f"volume_answers reference unknown volume(s): {unknown}")
        return self

    @model_validator(mode="after")
    def fixed_time_window_is_valid(self) -> "StopConfig":
        # Randomized mode always satisfies this by construction (see
        # backend.generators.stop.build_time_window); only a caller-supplied
        # fixed window can be inverted or narrower than FixedTime.
        tw = self.time_window
        if tw.mode == "fixed" and not validate_time_window(tw.open1, tw.close1, self.fixed_time_minutes):
            raise ValueError(
                f"fixed time window ({tw.open1}-{tw.close1}) must satisfy "
                f"0 <= Open1 <= Close1 <= 2359 and (Close1 - Open1) >= FixedTime ({self.fixed_time_minutes})"
            )
        return self


class StopGenerationResponse(BaseModel):
    """Metadata plus base64-encoded .XLSX content."""

    candidate_count: int
    selected_stop_count: int
    output_row_count: int
    seed: int
    filename: str
    stop_file_base64: str


class StopCsvRequest(StopConfig):
    """Stop generation request plus required Branch for CSV (SPEC-016)."""

    branch: str = Field(min_length=1)

    @field_validator("branch")
    @classmethod
    def branch_nonempty_ascii(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("branch must be non-empty")
        return _validate_ascii(stripped, "branch")


class StopCsvGenerationResponse(BaseModel):
    """Metadata plus base64-encoded stops CSV content (SPEC-016)."""

    candidate_count: int
    selected_stop_count: int
    output_row_count: int
    seed: int
    filename: str
    stop_csv_file_base64: str
