"""API tests for geocoding and location_db persistence (SPEC-017)."""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.location import LocationEntry
from backend.services.geocoding import GeocodeNotFoundError
from backend.services.location_store import append_location_row
from backend.services.spatial import load_location_db

client = TestClient(app)

SAMPLE_DB = Path("fixtures/stop/sample_location_db.xlsx")
TRIMBLE_OK = {
    "Err": 0,
    "Locations": [
        {
            "ShortString": "1 Independence Way, Princeton, NJ 08540",
            "Address": {
                "StreetAddress": "1 Independence Way",
                "City": "Princeton",
                "State": "NJ",
                "Zip": "08540",
            },
            "Coords": {"Lat": "40.3573", "Lon": "-74.6672"},
        }
    ],
}


@pytest.fixture()
def writable_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "location_db.xlsx"
    pd.read_excel(SAMPLE_DB).to_excel(db, index=False)
    monkeypatch.setattr("backend.main.LOCATION_DB_PATH", db)
    return db


def test_geocode_success_returns_coordinates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRIMBLE_MAPS_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200

        def json(self):
            return TRIMBLE_OK

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("backend.services.geocoding.httpx.Client", lambda **kwargs: FakeClient())

    response = client.post(
        "/api/locations/geocode",
        json={
            "address": "1 Independence Way",
            "city": "Princeton",
            "state": "NJ",
            "zip": "08540",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["latitude"] == pytest.approx(40.3573, abs=1e-4)
    assert body["longitude"] == pytest.approx(-74.6672, abs=1e-4)
    assert body["provider"] == "trimble-single-search"


def test_geocode_failure_returns_422(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRIMBLE_MAPS_API_KEY", "test-key")

    def raise_not_found(request):
        raise GeocodeNotFoundError("Could not find coordinates for this address")

    monkeypatch.setattr("backend.main.geocode_address", raise_not_found)

    response = client.post(
        "/api/locations/geocode",
        json={"address": "Nowhere", "city": "Nowhere", "state": "ZZ", "zip": "00000"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Could not find coordinates for this address"


def test_append_location_persists_and_reloads(writable_db: Path):
    entry = LocationEntry(
        address="999 Manual Test Rd",
        city="Denver",
        state="CO",
        zip="80202",
        latitude=39.7392,
        longitude=-104.9903,
    )
    result = append_location_row(writable_db, entry)
    assert result["name"].startswith("Customer ")
    reloaded = load_location_db(writable_db)
    row = reloaded[reloaded["Address"] == "999 Manual Test Rd"].iloc[0]
    assert row["Latitude"] == pytest.approx(39.7392)
    assert row["Longitude"] == pytest.approx(-104.9903)
    assert str(row["Name"]).strip() == result["name"]
    assert str(row["Zip"]).strip() == "80202"


def test_append_duplicate_returns_409(writable_db: Path):
    payload = {
        "address": "888 Brand New Depot Rd",
        "address2": "",
        "city": "Denver",
        "state": "CO",
        "zip": "80202",
        "latitude": 39.7392,
        "longitude": -104.9903,
    }
    first = client.post("/api/locations", json=payload)
    assert first.status_code == 201
    second = client.post("/api/locations", json=payload)
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert "existing_name" in detail
    assert detail["latitude"] == pytest.approx(39.7392)


def test_concurrent_appends_do_not_corrupt_file(writable_db: Path):
    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            append_location_row(
                writable_db,
                LocationEntry(
                    address=f"{1000 + n} Concurrent Ln",
                    city="Austin",
                    state="TX",
                    zip="78701",
                    latitude=30.2672 + n * 0.0001,
                    longitude=-97.7431,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    df = load_location_db(writable_db)
    assert len(df) == len(pd.read_excel(SAMPLE_DB)) + 4


def test_stop_generation_depot_geocode_error_message(writable_db: Path):
    body = {
        "depots": [
            {
                "address": "Unknown Depot",
                "city": "Nowhere",
                "state": "ZZ",
                "zip": "00000",
                "truck_count": 1,
            }
        ],
        "weeks": 1,
        "volumes": [{"name": "Cases", "capacity": 100}],
        "selection": {"mode": "radius", "radius_miles": 50},
        "stop_count": 5,
        "fixed_time_minutes": 10,
        "volume_answers": [{"name": "Cases", "mode": "averaged", "value": 40}],
        "frequency_values": [1],
        "time_window": {"mode": "randomized", "pattern_scope": "week"},
        "generate_shapes": False,
        "generate_colors": False,
        "seed": 0,
    }
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == "Depot could not be geocoded"


def test_stop_generation_with_inline_depot_coords(writable_db: Path):
    body = {
        "depots": [
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
        "weeks": 1,
        "volumes": [{"name": "Cases", "capacity": 100}],
        "selection": {"mode": "radius", "radius_miles": 500},
        "stop_count": 3,
        "fixed_time_minutes": 10,
        "volume_answers": [{"name": "Cases", "mode": "averaged", "value": 40}],
        "frequency_values": [1],
        "time_window": {"mode": "randomized", "pattern_scope": "week"},
        "generate_shapes": False,
        "generate_colors": False,
        "seed": 0,
    }
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200


def test_manual_stop_coords_passthrough_to_output(writable_db: Path):
    append_location_row(
        writable_db,
        LocationEntry(
            address="777 Manual Stop Ave",
            city="Denver",
            state="CO",
            zip="80202",
            latitude=39.740000,
            longitude=-104.990000,
        ),
    )
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
        "selection": {"mode": "state", "states": ["CO"]},
        "stop_count": 1,
        "fixed_time_minutes": 10,
        "volume_answers": [{"name": "Cases", "mode": "averaged", "value": 40}],
        "frequency_values": [1],
        "time_window": {"mode": "randomized", "pattern_scope": "week"},
        "generate_shapes": False,
        "generate_colors": False,
        "seed": 0,
    }
    response = client.post("/api/stops/generate", json=body)
    assert response.status_code == 200

    import base64
    import io

    import pandas as pd

    content = base64.b64decode(response.json()["stop_file_base64"])
    stops = pd.read_excel(io.BytesIO(content))
    manual_rows = stops[stops["Address"] == "777 Manual Stop Ave"]
    assert len(manual_rows) == 1
    assert float(manual_rows.iloc[0]["Latitude"]) == pytest.approx(39.740000, abs=1e-6)
    assert float(manual_rows.iloc[0]["Longitude"]) == pytest.approx(-104.990000, abs=1e-6)
