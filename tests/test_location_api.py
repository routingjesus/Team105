"""API tests for session coords / removed geocode-persist stack (SPEC-019)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import RADIUS_NO_COORDS_ERROR_MESSAGE, app

client = TestClient(app)

SAMPLE_DB = Path("fixtures/stop/sample_location_db.xlsx")


@pytest.fixture()
def sample_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "location_db.xlsx"
    pd.read_excel(SAMPLE_DB).to_excel(db, index=False)
    monkeypatch.setattr("backend.main.LOCATION_DB_PATH", db)
    return db


def _stop_body(**overrides):
    body = {
        "depots": [
            {
                "address": "1 Depot Way",
                "city": "Columbus",
                "state": "OH",
                "zip": "43215",
                "truck_count": 1,
                "latitude": 39.9612,
                "longitude": -82.9988,
            }
        ],
        "weeks": 1,
        "volumes": [{"name": "Cases", "capacity": 100}],
        "selection": {"mode": "state", "states": ["OH"]},
        "stop_count": 5,
        "fixed_time_minutes": 10,
        "volume_answers": [{"name": "Cases", "mode": "averaged", "value": 40}],
        "frequency_values": [1],
        "time_window": {"mode": "randomized", "pattern_scope": "week"},
        "generate_shapes": False,
        "generate_colors": False,
        "seed": 0,
    }
    body.update(overrides)
    return body


def test_geocode_route_removed():
    response = client.post(
        "/api/locations/geocode",
        json={"address": "1 Main", "city": "Denver", "state": "CO", "zip": "80202"},
    )
    assert response.status_code == 404


def test_append_location_route_removed():
    response = client.post(
        "/api/locations",
        json={
            "address": "1 Main",
            "city": "Denver",
            "state": "CO",
            "zip": "80202",
            "latitude": 39.7,
            "longitude": -104.9,
        },
    )
    assert response.status_code == 404


def test_radius_without_depot_coords_returns_non_geocode_422(sample_db: Path):
    body = _stop_body(
        depots=[
            {
                "address": "Unknown Depot",
                "city": "Nowhere",
                "state": "ZZ",
                "zip": "00000",
                "truck_count": 1,
            }
        ],
        selection={"mode": "radius", "radius_miles": 50},
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == RADIUS_NO_COORDS_ERROR_MESSAGE
    assert "geocode" not in detail.lower()


def test_stop_generation_with_inline_depot_coords(sample_db: Path):
    body = _stop_body(
        depots=[
            {
                "address": "Unknown Depot",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
                "truck_count": 1,
                "latitude": 39.7392,
                "longitude": -104.9903,
            }
        ],
        selection={"mode": "radius", "radius_miles": 500},
        stop_count=3,
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200


def test_session_manual_stop_with_blank_coords_in_output(sample_db: Path):
    body = _stop_body(
        selection={"mode": "state", "states": ["OH"]},
        stop_count=1,
        manual_stops=[
            {
                "address": "777 Manual Stop Ave",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
            }
        ],
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200

    content = base64.b64decode(response.json()["stop_file_base64"])
    stops = pd.read_excel(io.BytesIO(content))
    manual_rows = stops[stops["Address"] == "777 Manual Stop Ave"]
    assert len(manual_rows) == 1
    lat = manual_rows.iloc[0]["Latitude"]
    lon = manual_rows.iloc[0]["Longitude"]
    assert pd.isna(lat) or str(lat).strip() == ""
    assert pd.isna(lon) or str(lon).strip() == ""


def test_session_manual_stop_survives_aggressive_thinning(sample_db: Path):
    body = _stop_body(
        selection={"mode": "state", "states": ["OH"]},
        stop_count=1,
        manual_stops=[
            {
                "address": "999 Protected Manual",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
                "latitude": 39.74,
                "longitude": -104.99,
            }
        ],
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200
    content = base64.b64decode(response.json()["stop_file_base64"])
    stops = pd.read_excel(io.BytesIO(content))
    assert (stops["Address"] == "999 Protected Manual").any()


def test_truck_file_emits_depot_coords_when_present():
    response = client.post(
        "/api/trucks/generate",
        json={
            "weeks": 1,
            "depots": [
                {
                    "address": "1 Depot Way",
                    "city": "Columbus",
                    "state": "OH",
                    "zip": "43215",
                    "trucks": 1,
                    "latitude": 39.9612,
                    "longitude": -82.9988,
                }
            ],
            "volumes": [{"name": "Cases", "capacity": 100}],
            "seed": 0,
        },
    )
    assert response.status_code == 200
    content = base64.b64decode(response.json()["truck_file_base64"]).decode("ascii")
    header, first_row = content.splitlines()[:2]
    cols = header.split("\t")
    cells = first_row.split("\t")
    lat_i = cols.index("Latitude")
    lon_i = cols.index("Longitude")
    assert cells[lat_i] == "39.961200"
    assert cells[lon_i] == "-82.998800"


def test_truck_file_emits_blank_depot_coords_when_omitted():
    response = client.post(
        "/api/trucks/generate",
        json={
            "weeks": 1,
            "depots": [
                {
                    "address": "1 Depot Way",
                    "city": "Columbus",
                    "state": "OH",
                    "zip": "43215",
                    "trucks": 1,
                }
            ],
            "volumes": [{"name": "Cases", "capacity": 100}],
            "seed": 0,
        },
    )
    assert response.status_code == 200
    content = base64.b64decode(response.json()["truck_file_base64"]).decode("ascii")
    header, first_row = content.splitlines()[:2]
    cols = header.split("\t")
    cells = first_row.split("\t")
    assert cells[cols.index("Latitude")] == ""
    assert cells[cols.index("Longitude")] == ""


def test_coords_only_manual_stop_generate_ok(sample_db: Path):
    body = _stop_body(
        selection={"mode": "state", "states": ["OH"]},
        stop_count=1,
        manual_stops=[
            {
                "address": "",
                "city": "",
                "state": "",
                "zip": "",
                "latitude": 38.38080520110032,
                "longitude": -97.4279212147894,
            }
        ],
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200
    content = base64.b64decode(response.json()["stop_file_base64"])
    stops = pd.read_excel(io.BytesIO(content))
    manual_rows = stops[stops["Name"] == "Manual stop 1"]
    assert len(manual_rows) == 1
    row = manual_rows.iloc[0]
    assert pd.isna(row["Address"]) or str(row["Address"]).strip() == ""
    assert pd.isna(row["City"]) or str(row["City"]).strip() == ""
    assert str(row["Latitude"]).startswith("38.380805")
    assert str(row["Longitude"]).startswith("-97.427921")


def test_neither_manual_stop_returns_422_on_address_fields(sample_db: Path):
    body = _stop_body(
        selection={"mode": "state", "states": ["OH"]},
        stop_count=1,
        manual_stops=[{"address": "", "city": "", "state": "", "zip": ""}],
    )
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 422
    locs = [tuple(item["loc"]) for item in response.json()["detail"]]
    assert ("body", "manual_stops", 0, "address") in locs
    assert ("body", "manual_stops", 0, "city") in locs
    assert ("body", "manual_stops", 0, "state") in locs
    assert ("body", "manual_stops", 0, "zip") in locs
