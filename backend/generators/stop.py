"""`.XLSX` stop file generator (SPEC-002).

Column order and required-field minimums come from the owner-supplied
golden templates (`fixtures/stop/TEMPLATE_NewConfigStopFile.xls`,
customer-facing variant). Mirrors SPEC-001's `backend/generators/truck.py`
pattern: an ordered column-definition table drives row rendering, plus a
dynamic segment (here, volume columns) that expands based on the request.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from backend.schemas.stop_config import (
    ALIAS_FIELD_MAP,
    COLOR_VALUES,
    PATTERN_DAY_LETTERS,
    SHAPE_VALUES,
    StopConfig,
    validate_time_window,
)
from backend.schemas.truck_config import _validate_ascii
from backend.services.spatial import (
    filter_by_radius,
    filter_by_state,
    resolve_depot_coordinates,
    thin_to_target,
)

# Golden column order (customer-facing template, 70 columns) with the two
# generic volume slots ("Cube", "Weight") collapsed into one dynamic
# segment marker -- volume columns are named after the request's own
# volume names ("can be named anything" per the template's own field
# description), not hardcoded.
VOLUMES_MARKER = "__VOLUMES__"

COLUMN_ORDER: tuple[str, ...] = (
    "Name", "Contact", "Phone", "Store #", "ID2", "ID3", "Address", "Address2",
    "City", "State", "Zip", "FixedTime", "Rt", "Seq", "SzRestriction", "EqCode",
    VOLUMES_MARKER, "UnldCube", "UnldWeight", "CloseTW", "Open1", "Close1",
    "Pattern1", "Open2", "Close2", "Pattern2", "Longitude", "Latitude", "Symbol",
    "Size", "Color", "Selected", "EarliestDate", "LatestDate", "EarlyBuffer",
    "LateBuffer", "PenaltyCost", "AddressErr", "GeoResult", "MaxSplits",
    "CurrentRoute", "RouteSequence", "ServiceDate", "Zone", "AMStart", "AMEnd",
    "AMAdj", "PMStart", "PMEnd", "PMAdj", "Territory", "Day", "Frequency",
    "ServTm", "EstTime", "StemTm", "DrvBtwnStop", "Lock", "OrgTerritory",
    "OrgDay", "Change", "MinDaysBetweenDeliveries", "MaxDaysBetweenDeliveries",
    "Patterns", "Delivery Day", "AssignedDays", "Priority", "OnFinalize", "Country",
)

REQUIRED_COLUMNS = (
    "Name", "Store #", "Address", "City", "State", "Zip", "FixedTime",
    "Open1", "Close1", "Pattern1", "Frequency",
)

# COLUMN_ORDER uses the golden template's literal header text ("Store #",
# "Address2"), which differs slightly from ALIAS_FIELD_MAP's canonical
# field names ("ID1", "Address_2") -- bridge the two here.
_ALIAS_TARGETS = {
    "Name": ALIAS_FIELD_MAP["Name"],
    "Contact": ALIAS_FIELD_MAP["Contact"],
    "Phone": ALIAS_FIELD_MAP["Phone"],
    "Store #": ALIAS_FIELD_MAP["ID1"],
    "ID2": ALIAS_FIELD_MAP["ID2"],
    "ID3": ALIAS_FIELD_MAP["ID3"],
    "Address2": ALIAS_FIELD_MAP["Address_2"],
}

PATTERN_SCOPE_DAYS: dict[str, tuple[str, ...]] = {
    "week": tuple(PATTERN_DAY_LETTERS),
    "weekday": ("M", "T", "W", "R", "F"),
    "weekend": ("S", "A"),
}


class FrequencyConsistencyError(ValueError):
    """Raised when any requested frequency value doesn't fit the routing horizon."""


def _alias(aliases, key: str, default: str) -> str:
    if aliases is None:
        return default
    value = getattr(aliases, key)
    return value if value else default


def build_header(config: StopConfig) -> list[str]:
    """Column headers with aliases applied and volume columns expanded."""
    volume_names = [a.name for a in config.volume_answers]
    header: list[str] = []
    for col in COLUMN_ORDER:
        if col == VOLUMES_MARKER:
            header.extend(volume_names)
        elif col in _ALIAS_TARGETS:
            header.append(_alias(config.aliases, _ALIAS_TARGETS[col], col))
        else:
            header.append(col)
    return header


def achievable_frequency_values(frequency_values: list[float], weeks: int) -> list[float]:
    """Filter requested Frequency values to ones representable in the routing horizon.

    Values >= 1 are weekly-or-more-often and always fit. Values < 1 imply a
    multi-week cycle (cycle_weeks = 1 / value); a value only "fits" if that
    cycle completes at least once within the routing horizon.
    """
    achievable = []
    for value in frequency_values:
        if value >= 1:
            achievable.append(value)
            continue
        cycle_weeks = 1 / value
        if cycle_weeks <= weeks:
            achievable.append(value)
    return achievable


def build_pattern1(scope: str, specific_days: list[str] | None, rng: random.Random) -> str:
    """Render the active day letters only, in SMTWRFA order; no separators for inactive days."""
    if scope == "specific_days":
        active = set(specific_days or [])
    elif scope == "random":
        all_days = list(PATTERN_DAY_LETTERS)
        k = rng.randint(1, len(all_days))
        active = set(rng.sample(all_days, k))
    else:
        active = set(PATTERN_SCOPE_DAYS[scope])
    return "".join(letter for letter in PATTERN_DAY_LETTERS if letter in active)


# Realistic business-hours bias for `mode="randomized"` (SPEC-009): real-world
# stops are rarely open past 1700, so most generated windows should open and
# close within a 0500-1600 band, with only a small tail extending later.
_DAY_END_MINUTES = 23 * 60 + 59
_BUSINESS_OPEN_FLOOR_MINUTES = 5 * 60  # 0500
_BUSINESS_CLOSE_CEILING_MINUTES = 16 * 60  # 1600
_EVENING_TAIL_PROBABILITY = 0.12


def build_time_window(config: StopConfig, rng: random.Random) -> tuple[int, int, str]:
    """(open1, close1, pattern1) satisfying 0<=open1<=close1<=2359 and width>=FixedTime."""
    tw = config.time_window
    fixed_time = int(config.fixed_time_minutes)
    if tw.mode == "fixed":
        open1, close1 = tw.open1, tw.close1
    else:
        # Military-time minutes-of-day, avoiding the 24:00-01:00 gap in the
        # HHMM encoding by working in real minutes then converting back.
        latest_open_minutes = max(0, _DAY_END_MINUTES - fixed_time)
        business_latest_open = max(0, min(_BUSINESS_CLOSE_CEILING_MINUTES - fixed_time, latest_open_minutes))

        if rng.random() < _EVENING_TAIL_PROBABILITY and latest_open_minutes > business_latest_open:
            # Small tail: a minority of stops open later in the day and may
            # close past 1700.
            open_minutes = rng.randint(business_latest_open + 1, latest_open_minutes)
            jitter_cap = 180
        else:
            # Majority: stay within the realistic 0500-1600 business-hours band.
            business_open_floor = min(_BUSINESS_OPEN_FLOOR_MINUTES, business_latest_open)
            open_minutes = rng.randint(business_open_floor, business_latest_open)
            jitter_cap = max(0, min(180, _BUSINESS_CLOSE_CEILING_MINUTES - (open_minutes + fixed_time)))

        max_close_minutes = min(_DAY_END_MINUTES, open_minutes + fixed_time + rng.randint(0, jitter_cap))
        close_minutes = max(open_minutes + fixed_time, max_close_minutes)
        close_minutes = min(close_minutes, _DAY_END_MINUTES)
        open1 = (open_minutes // 60) * 100 + (open_minutes % 60)
        close1 = (close_minutes // 60) * 100 + (close_minutes % 60)
    pattern1 = build_pattern1(tw.pattern_scope, tw.specific_days, rng)
    assert validate_time_window(open1, close1, config.fixed_time_minutes), (
        f"generated window ({open1}-{close1}) violates the AC6 invariant; "
        f"this should be impossible by construction for fixed_time_minutes={config.fixed_time_minutes}"
    )
    return open1, close1, pattern1


@dataclass(frozen=True)
class SelectedStop:
    """One candidate row from location_db, resolved to output-ready fields."""

    name: str
    contact: str
    phone: str
    id1: str
    id3: str
    address: str
    address2: str
    city: str
    state: str
    zip: str
    latitude: float
    longitude: float


def _clean(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return _validate_ascii(text, "location_db field") if text else text


def selected_stops_from_candidates(candidates: pd.DataFrame) -> list[SelectedStop]:
    """Map location_db rows (post filter+thin) into output-ready stop records."""
    stops = []
    for _, row in candidates.iterrows():
        stops.append(
            SelectedStop(
                name=_clean(row.get("Name")),
                contact=_clean(row.get("Contact")),
                phone=_clean(row.get("Phone")),
                id1=_clean(row.get("ID1")) or _clean(row.get("Name")),
                id3=_clean(row.get("ID3")),
                address=_clean(row["Address"]),
                address2=_clean(row.get("Address2")),
                city=_clean(row["City"]),
                state=_clean(row["State"]),
                zip=_clean(row["Zip"]),
                latitude=float(row["Latitude"]),
                longitude=float(row["Longitude"]),
            )
        )
    return stops


AVERAGED_VOLUME_JITTER = 0.35  # +/-35% around the target mean; whole units.


def _volume_cells(config: StopConfig, rng: random.Random) -> list[str]:
    cells = []
    for answer in config.volume_answers:
        if answer.mode == "fixed":
            cells.append(f"{answer.value:.2f}")
        else:
            # Averaged mode represents a whole-unit count (e.g. cartons, pieces),
            # so it must round to an integer -- a fractional jitter around the
            # mean produces decimal values a real routing system never sees for
            # a unit count. The jitter width is also widened relative to the
            # value so a small requested mean still yields a visible spread.
            jittered = answer.value * (1 + rng.uniform(-AVERAGED_VOLUME_JITTER, AVERAGED_VOLUME_JITTER))
            value = max(1, round(jittered))
            cells.append(str(value))
    return cells


def build_rows(config: StopConfig, candidates: pd.DataFrame, rng: random.Random | None = None) -> list[list[str]]:
    """Data rows, one (or more, if consolidation is enabled) per selected stop."""
    rng = rng if rng is not None else random.Random(config.seed)
    achievable = achievable_frequency_values(config.frequency_values, config.weeks)
    unfit = [value for value in config.frequency_values if value not in achievable]
    if unfit:
        # Any non-empty `unfit` -- not just a totally empty `achievable` --
        # must reject: otherwise rng.choice() below silently narrows to a
        # smaller set than the caller requested.
        raise FrequencyConsistencyError(
            f"Requested frequency value(s) {unfit} do not fit within a {config.weeks}-week "
            "routing horizon; increase weeks or remove these values from frequency_values."
        )

    stops = selected_stops_from_candidates(candidates)
    eq_targets: set[int] = set()
    if config.eq_code is not None and config.eq_code.enabled:
        count = max(1, round(len(stops) * config.eq_code.fraction))
        eq_targets = set(rng.sample(range(len(stops)), min(count, len(stops))))

    lines_per_customer = 1
    if config.consolidation is not None and config.consolidation.enabled:
        lines_per_customer = config.consolidation.lines_per_customer

    rows: list[list[str]] = []
    for stop_index, stop in enumerate(stops):
        frequency = rng.choice(achievable)
        open1, close1, pattern1 = build_time_window(config, rng)
        eq_code = rng.choice(config.eq_code.codes) if stop_index in eq_targets else ""
        volume_cells = _volume_cells(config, rng)
        # Draw once per stop so consolidation line items share Symbol/Color.
        symbol = rng.choice(SHAPE_VALUES) if config.generate_shapes else None
        color = rng.choice(COLOR_VALUES) if config.generate_colors else None

        for line in range(1, lines_per_customer + 1):
            id2 = f"ORD-{stop_index + 1:04d}-{line:02d}"
            row_by_col = {
                "Name": stop.name,
                "Contact": stop.contact,
                "Phone": stop.phone,
                "Store #": stop.id1,
                "ID2": id2,
                "ID3": stop.id3,
                "Address": stop.address,
                "Address2": stop.address2,
                "City": stop.city,
                "State": stop.state,
                "Zip": stop.zip,
                "Longitude": f"{stop.longitude:.6f}",
                "Latitude": f"{stop.latitude:.6f}",
                "FixedTime": f"{config.fixed_time_minutes:g}",
                "EqCode": eq_code,
                "Open1": str(open1).zfill(4),
                "Close1": str(close1).zfill(4),
                "Pattern1": pattern1,
                "Frequency": f"{frequency:g}",
            }
            if symbol is not None:
                row_by_col["Symbol"] = symbol
            if color is not None:
                row_by_col["Color"] = color
            if config.generate_shapes or config.generate_colors:
                row_by_col["Size"] = "28"
            row = []
            for col in COLUMN_ORDER:
                if col == VOLUMES_MARKER:
                    row.extend(volume_cells)
                else:
                    row.append(row_by_col.get(col, ""))
            rows.append(row)
    return rows


def select_candidates(config: StopConfig, location_db: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Filter (radius or state) then density-thin to the requested stop count.

    Returns (thinned_candidates, pre_thin_candidate_count) so callers can
    report both the raw candidate pool size and the post-thinning selection.
    """
    selection = config.selection
    if selection.mode == "radius":
        dc_coordinates = [resolve_depot_coordinates(depot, location_db) for depot in config.depots]
        filtered = filter_by_radius(location_db, dc_coordinates, selection.radius_miles)
    else:
        filtered = filter_by_state(location_db, selection.states)
    thinned = thin_to_target(filtered, config.stop_count, config.seed)
    return thinned, len(filtered)


def generate_stop_file(config: StopConfig, candidates: pd.DataFrame) -> bytes:
    """Emit the complete `.XLSX` stop file as bytes."""
    rng = random.Random(config.seed)
    header = build_header(config)
    rows = build_rows(config, candidates, rng)
    df = pd.DataFrame(rows, columns=header)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Stop File", index=False)
    return buffer.getvalue()


def delete_action_count(n: int) -> int:
    """Exact Delete row count for N ≥ 1 data rows (SPEC-016).

    Mirrors EQ-code subset math (`max(1, round(N * fraction))`) with
    fraction 0.1, capped at N so sample stays valid.
    """
    if n < 1:
        return 0
    return min(n, max(1, round(0.1 * n)))


def generate_stop_csv_file(config: StopConfig, candidates: pd.DataFrame, branch: str) -> bytes:
    """Emit stops as UTF-8-BOM CSV with leading Branch/Action columns (SPEC-016).

    Stop content matches `generate_stop_file` for the same config + seed
    (same `build_header` / `build_rows` stream). Delete indices use a
    dedicated `random.Random(config.seed)` after rows are materialized so
    they stay stable if `build_rows` RNG consumption changes.
    """
    rng = random.Random(config.seed)
    header = build_header(config)
    rows = build_rows(config, candidates, rng)

    n = len(rows)
    actions = ["Modify"] * n
    if n >= 1:
        k = delete_action_count(n)
        for idx in random.Random(config.seed).sample(range(n), k):
            actions[idx] = "Delete"

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect=csv.excel)
    writer.writerow(["Branch", "Action", *header])
    for i, row in enumerate(rows):
        writer.writerow([branch, actions[i], *row])
    return buffer.getvalue().encode("utf-8-sig")
