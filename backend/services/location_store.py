"""Concurrent-safe append to location_db.xlsx (SPEC-017)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
from filelock import FileLock

from backend.schemas.location import LocationEntry
from backend.services.spatial import load_location_db

LOCATION_DB_COLUMNS = [
    "Name",
    "ID1",
    "Contact",
    "Phone",
    "ID2",
    "ID3",
    "Address",
    "Address2",
    "City",
    "State",
    "Zip",
    "Latitude",
    "Longitude",
]


class LocationDuplicateError(Exception):
    """Raised when a normalized address key already exists in location_db."""

    def __init__(self, name: str, id1: str, latitude: float, longitude: float) -> None:
        self.existing_name = name
        self.existing_id1 = id1
        self.latitude = latitude
        self.longitude = longitude
        super().__init__(f"Duplicate location: {name} ({id1})")


def normalize_address_key(address: str, city: str, state: str, zip_code: str) -> tuple[str, str, str, str]:
    return (
        address.strip().casefold(),
        city.strip().casefold(),
        state.strip().casefold(),
        str(zip_code).strip(),
    )


def _lock_path(db_path: Path) -> Path:
    return db_path.with_suffix(db_path.suffix + ".lock")


def _next_synthetic_ids(df: pd.DataFrame) -> tuple[str, str]:
    max_n = 0
    for name in df["Name"]:
        if isinstance(name, str) and name.startswith("Customer "):
            suffix = name.replace("Customer ", "").strip()
            if suffix.isdigit():
                max_n = max(max_n, int(suffix))
    for id1 in df["ID1"]:
        text = str(id1).strip()
        if text.isdigit():
            max_n = max(max_n, int(text))
    next_n = max_n + 1
    return f"Customer {next_n:05d}", f"{next_n:06d}"


def find_existing_by_key(
    df: pd.DataFrame, address: str, city: str, state: str, zip_code: str
) -> pd.Series | None:
    key = normalize_address_key(address, city, state, zip_code)
    for _, row in df.iterrows():
        row_key = normalize_address_key(
            str(row["Address"]), str(row["City"]), str(row["State"]), str(row["Zip"])
        )
        if row_key == key:
            return row
    return None


def append_location_row(db_path: Path, entry: LocationEntry) -> dict:
    """Append one row to location_db with file lock and atomic replace.

    Returns dict with name, id1, latitude, longitude.
    Raises LocationDuplicateError if the normalized address key exists.
    Raises FileNotFoundError if db_path does not exist.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"location_db not found at {db_path}")

    lock = FileLock(_lock_path(db_path), timeout=30)
    with lock:
        df = load_location_db(db_path)
        existing = find_existing_by_key(df, entry.address, entry.city, entry.state, entry.zip)
        if existing is not None:
            raise LocationDuplicateError(
                str(existing["Name"]),
                str(existing["ID1"]),
                float(existing["Latitude"]),
                float(existing["Longitude"]),
            )

        name, id1 = _next_synthetic_ids(df)
        new_row = {
            "Name": name,
            "ID1": id1,
            "Contact": "",
            "Phone": "",
            "ID2": "",
            "ID3": "",
            "Address": entry.address.strip(),
            "Address2": entry.address2.strip(),
            "City": entry.city.strip(),
            "State": entry.state.strip(),
            "Zip": str(entry.zip).strip(),
            "Latitude": float(entry.latitude),
            "Longitude": float(entry.longitude),
        }
        out = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        out = out[LOCATION_DB_COLUMNS]

        parent = db_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(suffix=".xlsx", dir=parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            out.to_excel(tmp_path, index=False, engine="openpyxl")
            tmp_path.replace(db_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    return {
        "name": name,
        "id1": id1,
        "latitude": float(entry.latitude),
        "longitude": float(entry.longitude),
    }
