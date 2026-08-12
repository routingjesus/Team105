"""Geospatial helpers for stop selection (SPEC-002).

No external geocoding: DC coordinates are resolved by matching a depot's
address against the static location database's own Latitude/Longitude
columns, per SPEC-002's research. Radius filtering uses a vectorized
NumPy Haversine calculation -- a spatial index is unnecessary at the
~10k-candidate scale this spec targets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.schemas.truck_config import DepotSpec, DepotSummary

EARTH_RADIUS_MILES = 3958.8

REQUIRED_LOCATION_DB_COLUMNS = ("Name", "Address", "City", "State", "Zip", "Latitude", "Longitude")


def load_location_db(path: str | Path) -> pd.DataFrame:
    """Load the static candidate-location database (.xls or .xlsx).

    Uses the `xlrd` engine for legacy `.xls` (pandas' pure-Python fallback --
    `python-calamine` needs a Rust toolchain with crates.io access, which
    corporate TLS interception blocks on bootcamp hosts) and pandas'
    default engine for `.xlsx`.
    """
    path = Path(path)
    engine = "xlrd" if path.suffix.lower() == ".xls" else None
    df = pd.read_excel(path, engine=engine)
    missing = [c for c in REQUIRED_LOCATION_DB_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"location_db at {path} is missing required column(s): {missing}")
    # The legacy database stores fixed-width, whitespace-padded text (e.g.
    # "VA    ", "CHESAPEAKE                "). Strip string columns on load so
    # depot address / city / state / zip matching and state filtering work
    # against normal, un-padded user input. Emitted stop rows are already
    # stripped downstream (generators.stop._clean), so this changes matching
    # only, not output content.
    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def haversine_miles(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray:
    """Vectorized great-circle distance in miles."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class DepotCoordinateError(ValueError):
    """Raised when a depot cannot be matched to any location_db record."""


def resolve_depot_coordinates(
    depot: DepotSpec | DepotSummary, location_db: pd.DataFrame
) -> tuple[float, float]:
    """Match a depot's address against location_db; fall back to City/State/Zip.

    When the depot carries inline latitude/longitude (session paste from
    the wizard), those values are used directly.

    Returns (latitude, longitude). Raises DepotCoordinateError if neither an
    exact address match nor a City/State/Zip match exists.
    """
    inline_lat = getattr(depot, "latitude", None)
    inline_lon = getattr(depot, "longitude", None)
    if inline_lat is not None and inline_lon is not None:
        return float(inline_lat), float(inline_lon)

    exact = location_db[
        location_db["Address"].str.casefold() == depot.address.casefold()
    ]
    if not exact.empty:
        row = exact.iloc[0]
        return float(row["Latitude"]), float(row["Longitude"])

    fallback = location_db[
        (location_db["City"].str.casefold() == depot.city.casefold())
        & (location_db["State"].str.casefold() == depot.state.casefold())
        & (location_db["Zip"].astype(str) == str(depot.zip))
    ]
    if not fallback.empty:
        row = fallback.iloc[0]
        return float(row["Latitude"]), float(row["Longitude"])

    raise DepotCoordinateError(
        f"No location_db match for depot address={depot.address!r} "
        f"city={depot.city!r} state={depot.state!r} zip={depot.zip!r}"
    )


def filter_by_radius(
    candidates: pd.DataFrame, dc_coordinates: list[tuple[float, float]], radius_miles: float
) -> pd.DataFrame:
    """Keep candidates within radius_miles of at least one DC coordinate."""
    within_any = np.zeros(len(candidates), dtype=bool)
    lat = candidates["Latitude"].to_numpy(dtype=float)
    lon = candidates["Longitude"].to_numpy(dtype=float)
    for dc_lat, dc_lon in dc_coordinates:
        distances = haversine_miles(lat, lon, dc_lat, dc_lon)
        within_any |= distances <= radius_miles
    return candidates[within_any].copy()


def filter_by_state(candidates: pd.DataFrame, states: list[str]) -> pd.DataFrame:
    """Keep candidates in any of the given states. No DC proximity check."""
    wanted = {s.casefold() for s in states}
    mask = candidates["State"].str.casefold().isin(wanted)
    return candidates[mask].copy()


class ZipParseError(ValueError):
    """Raised when a ZIP list/range token is invalid or inverted."""


def normalize_zip5(raw: str) -> str:
    """Normalize a ZIP token to a 5-digit string (ZIP+4 → base-5, left-pad)."""
    digits = str(raw).strip().replace(" ", "")
    if len(digits) == 10 and digits[5] == "-" and digits[:5].isdigit() and digits[6:].isdigit():
        return digits[:5]
    if len(digits) == 9 and digits.isdigit():
        return digits[:5]
    if digits.isdigit() and 1 <= len(digits) <= 5:
        return digits.zfill(5)
    raise ZipParseError(f"Invalid ZIP code: {raw}")


def parse_zips(raw: str) -> list[str]:
    """Parse comma-separated ZIP codes and inclusive ranges into 5-digit strings."""
    tokens = [part.strip() for part in raw.split(",") if part.strip()]
    if not tokens:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if "-" in token:
            left, right = token.split("-", 1)
            left, right = left.strip(), right.strip()
            # ZIP+4 (#####-####) is a single code, not a range.
            if left.isdigit() and len(left) == 5 and right.isdigit() and len(right) == 4:
                zip5 = normalize_zip5(f"{left}-{right}")
                if zip5 not in seen:
                    seen.add(zip5)
                    result.append(zip5)
                continue
            start = normalize_zip5(left)
            end = normalize_zip5(right)
            start_num = int(start)
            end_num = int(end)
            if end_num < start_num:
                raise ZipParseError(
                    f"Zip range end must be greater than or equal to start: {token}"
                )
            for n in range(start_num, end_num + 1):
                zip5 = f"{n:05d}"
                if zip5 not in seen:
                    seen.add(zip5)
                    result.append(zip5)
            continue
        zip5 = normalize_zip5(token)
        if zip5 not in seen:
            seen.add(zip5)
            result.append(zip5)
    return result


def _zip5_or_empty(value: object) -> str:
    text = str(value).strip() if value is not None and not (isinstance(value, float) and pd.isna(value)) else ""
    if not text:
        return ""
    try:
        return normalize_zip5(text)
    except ZipParseError:
        return ""


def filter_by_zip(candidates: pd.DataFrame, zips: list[str]) -> pd.DataFrame:
    """Keep candidates whose normalized 5-digit Zip is in the given set."""
    wanted = {_zip5_or_empty(z) for z in zips}
    wanted.discard("")
    normalized = candidates["Zip"].map(_zip5_or_empty)
    return candidates[normalized.isin(wanted)].copy()


def thin_to_target(candidates: pd.DataFrame, target_count: int, seed: int = 0) -> pd.DataFrame:
    """Grid-based quota sampling: thin to target_count while preserving spread.

    Divides the candidates' bounding box into a roughly sqrt(target_count)
    square grid, then samples proportionally from each occupied cell rather
    than uniformly at random, so dense clusters don't crowd out sparser
    areas. Deterministic for a given seed.
    """
    n = len(candidates)
    if n <= target_count:
        return candidates.copy()
    if target_count <= 0:
        return candidates.iloc[0:0].copy()

    rng = np.random.default_rng(seed)
    lat = candidates["Latitude"].to_numpy(dtype=float)
    lon = candidates["Longitude"].to_numpy(dtype=float)

    grid_dim = max(1, int(np.ceil(np.sqrt(target_count))))
    lat_edges = np.linspace(lat.min(), lat.max() + 1e-9, grid_dim + 1)
    lon_edges = np.linspace(lon.min(), lon.max() + 1e-9, grid_dim + 1)
    lat_cell = np.clip(np.digitize(lat, lat_edges) - 1, 0, grid_dim - 1)
    lon_cell = np.clip(np.digitize(lon, lon_edges) - 1, 0, grid_dim - 1)
    cell_id = lat_cell * grid_dim + lon_cell

    order = candidates.index.to_numpy()
    cells: dict[int, list[int]] = {}
    for idx, cid in zip(order, cell_id):
        cells.setdefault(int(cid), []).append(idx)

    cell_ids = sorted(cells)
    for cid in cell_ids:
        rng.shuffle(cells[cid])

    selected: list[int] = []
    round_robin = list(cell_ids)
    while len(selected) < target_count and round_robin:
        remaining_round: list[int] = []
        for cid in round_robin:
            bucket = cells[cid]
            if bucket:
                selected.append(bucket.pop())
            if bucket:
                remaining_round.append(cid)
            if len(selected) >= target_count:
                break
        round_robin = remaining_round

    return candidates.loc[selected].copy()
