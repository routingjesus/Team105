"""Tab-delimited .TRUCK file generator (Explode my Trucks macro baseline).

Pure functions, no I/O. The 76-column layout is driven by an ordered
column-definition table (data, not code); dynamic volume capacity columns
are appended after the base columns without forking emitter logic.

Formatting fidelity rules (per SPEC-001 research):
- booleans emit literal uppercase TRUE/FALSE
- costs are pre-formatted to fixed two decimals
- CRLF line endings, no BOM, no trailing tab, ASCII-only content
- EDate/LDate are dispatch-day offsets (1 = dispatch date), per the
  DirectRoute truck-file field reference
"""

import csv
import io
import random
from dataclasses import dataclass
from typing import Callable

from backend.schemas.truck_config import DepotSpec, TruckConfig

DAY_CODES = ("SU", "MO", "TU", "WE", "TH", "FR", "SA")

# Literal helper values the macro keeps in its trailing columns and reuses
# when composing TrkID.
WK_REPEATER = "Wk"
DASH_REPEATER = "-"


@dataclass(frozen=True)
class RowContext:
    """All inputs needed to render one truck row (one territory-day)."""

    config: TruckConfig
    depot: DepotSpec
    territory: str  # e.g. "T01"
    dispatch_day: int  # 1-based, 1..weeks*7
    week: int  # 1-based
    day_code: str  # SU..SA
    route: int  # global auto-increment, 1-based
    rng: random.Random


def format_cost(value: float) -> str:
    return f"{value:.2f}"


def format_number(value: float) -> str:
    """Integral floats emit without a decimal part (14 -> "14")."""
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def _trk_id(ctx: RowContext) -> str:
    # Territory & dash & "Wk" & week & dash & day, e.g. "T01-Wk1-SU".
    # Provisional composition pending the known-good macro fixture
    # (see fixtures/truck/README.md).
    return (
        f"{ctx.territory}{DASH_REPEATER}{WK_REPEATER}{ctx.week}"
        f"{DASH_REPEATER}{ctx.day_code}"
    )


def _empty(_ctx: RowContext) -> str:
    return ""


# Ordered 76-column map matching the Explode my Trucks header row
# (A1-BX1 equivalents). Order is load-bearing: golden parity tests
# compare bytes.
BASE_COLUMNS: tuple[tuple[str, Callable[[RowContext], str]], ...] = (
    ("TrkID", _trk_id),
    ("Available", lambda ctx: "TRUE"),
    ("OneWay", lambda ctx: "FALSE"),
    ("Redispatch", lambda ctx: "FALSE"),
    ("MinTm", _empty),
    ("TurnTm", _empty),
    ("SpEq", lambda ctx: ctx.config.sp_eq),
    ("UnldPerf%", _empty),
    ("MiCost", lambda ctx: format_cost(ctx.config.mi_cost)),
    ("HrCost", lambda ctx: format_cost(ctx.config.hr_cost)),
    ("OTCost1", _empty),
    ("OTCost2", _empty),
    ("OTCost3", _empty),
    ("OTCost4", _empty),
    ("OTHrs1", _empty),
    ("OTHrs2", _empty),
    ("OTHrs3", _empty),
    ("OTHrs4", _empty),
    ("UnldHrCost", _empty),
    ("DropCost", _empty),
    ("WaitHrCost", _empty),
    ("UnitCost", _empty),
    ("FixedCost", lambda ctx: format_cost(ctx.config.fixed_cost)),
    ("LayoverCost", _empty),
    ("EarStart", _empty),
    ("EDate", lambda ctx: str(ctx.dispatch_day)),
    ("LatStart", _empty),
    ("LatFinish", _empty),
    ("LDate", lambda ctx: str(ctx.dispatch_day)),
    ("WorkDay", _empty),
    ("NormalStart", _empty),
    ("Brk1Start", _empty),
    ("Brk1Duration", _empty),
    ("Brk2Start", _empty),
    ("Brk2Duration", _empty),
    ("Brk3Start", _empty),
    ("Brk3Duration", _empty),
    ("Brk4Start", _empty),
    ("Brk4Duration", _empty),
    ("Brk5Start", _empty),
    ("Brk5Duration", _empty),
    ("MaxWorkTm", lambda ctx: format_number(ctx.config.max_work)),
    ("TargetWrkTm", _empty),
    ("MaxDriveTm", lambda ctx: format_number(ctx.config.max_drive)),
    ("MinLayover", _empty),
    ("MaxLayover", _empty),
    ("MaxDrvTmB4Layover", _empty),
    ("MaxLayovers", _empty),
    ("Longitude", _empty),  # geocoding out of scope (SPEC-002 boundary)
    ("Latitude", _empty),
    ("Address", lambda ctx: ctx.depot.address),
    ("City", lambda ctx: ctx.depot.city),
    ("State", lambda ctx: ctx.depot.state),
    ("Zip", lambda ctx: ctx.depot.zip),
    ("GeoResult", _empty),
    ("Zone", _empty),
    ("Symbol", _empty),
    ("Size", lambda ctx: "12"),
    ("Color", _empty),
    ("PreTrip", lambda ctx: str(ctx.config.pre_trip)),
    ("PostTrip", lambda ctx: str(ctx.config.post_trip)),
    ("Territory", lambda ctx: ctx.territory),
    ("LoadID", _empty),
    ("DriverID", _empty),
    ("DeviceID", _empty),
    ("AMStart", _empty),
    ("AMEnd", _empty),
    ("AMAdj", _empty),
    ("PMStart", _empty),
    ("PMEnd", _empty),
    ("PMAdj", _empty),
    ("Day", lambda ctx: ctx.day_code),
    ("Week", lambda ctx: str(ctx.week)),
    ("Route", lambda ctx: str(ctx.route)),
    ("Wk Repeater", lambda ctx: WK_REPEATER),
    ("Dash Repeater", lambda ctx: DASH_REPEATER),
)

BASE_COLUMN_COUNT = len(BASE_COLUMNS)  # 76


def build_header(config: TruckConfig) -> list[str]:
    """76 base headers, plus one capacity column per named volume."""
    return [name for name, _ in BASE_COLUMNS] + [v.name for v in config.volumes]


def _iter_row_contexts(config: TruckConfig, rng: random.Random):
    dispatch_days = config.weeks * 7
    territory_index = 0
    route = 0
    for depot in config.depots:
        for _ in range(depot.trucks):
            territory_index += 1
            territory = f"T{territory_index:02d}"
            for day in range(1, dispatch_days + 1):
                route += 1
                yield RowContext(
                    config=config,
                    depot=depot,
                    territory=territory,
                    dispatch_day=day,
                    week=(day - 1) // 7 + 1,
                    day_code=DAY_CODES[(day - 1) % 7],
                    route=route,
                    rng=rng,
                )


def build_rows(config: TruckConfig, rng: random.Random | None = None) -> list[list[str]]:
    """Data rows as pre-formatted strings: (sum of trucks per depot) * weeks * 7."""
    rng = rng if rng is not None else random.Random(config.seed)
    volume_cells = [format_number(v.capacity) for v in config.volumes]
    return [
        [render(ctx) for _, render in BASE_COLUMNS] + volume_cells
        for ctx in _iter_row_contexts(config, rng)
    ]


def generate_truck_file(config: TruckConfig) -> bytes:
    """Emit the complete .TRUCK file as bytes (header row + data rows)."""
    rng = random.Random(config.seed)
    buffer = io.StringIO()
    writer = csv.writer(buffer, dialect="excel-tab", lineterminator="\r\n")
    writer.writerow(build_header(config))
    writer.writerows(build_rows(config, rng))
    return buffer.getvalue().encode("ascii")
