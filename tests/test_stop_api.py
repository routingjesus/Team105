"""FastAPI contract tests for the stop generation endpoints (SPEC-002)."""

import base64

import pytest
from fastapi.testclient import TestClient

from backend.main import LOCATION_DB_PATH, app

client = TestClient(app)


@pytest.fixture
def request_body() -> dict:
    return {
        "depots": [{"address": "1 Depot Way", "city": "Columbus", "state": "OH", "zip": "43215", "truck_count": 3}],
        "weeks": 4,
        "volumes": [{"name": "Cube", "capacity": 1800}],
        "selection": {"mode": "radius", "radius_miles": 50},
        "stop_count": 10,
        "fixed_time_minutes": 15,
        "volume_answers": [{"name": "Cube", "mode": "fixed", "value": 25}],
        "frequency_values": [1, 0.5],
        "time_window": {"mode": "fixed", "open1": 800, "close1": 1700, "pattern_scope": "week"},
        "seed": 5,
    }


class TestLocationDbPrerequisite:
    def test_generate_returns_503_when_bundled_db_missing(self, request_body):
        if LOCATION_DB_PATH.exists():
            pytest.skip("location_db.xls is present in this environment")
        response = client.post("/api/stops/generate", json=request_body)
        assert response.status_code == 503


class TestRequestValidation:
    def test_radius_mode_requires_radius_miles(self, request_body):
        request_body["selection"] = {"mode": "radius"}
        assert client.post("/api/stops/generate", json=request_body).status_code == 422

    def test_state_mode_requires_states(self, request_body):
        request_body["selection"] = {"mode": "state"}
        assert client.post("/api/stops/generate", json=request_body).status_code == 422

    def test_unknown_frequency_value_rejected(self, request_body):
        request_body["frequency_values"] = [0.9]
        assert client.post("/api/stops/generate", json=request_body).status_code == 422

    def test_volume_answer_referencing_unknown_volume_rejected(self, request_body):
        request_body["volume_answers"] = [{"name": "NotAVolume", "mode": "fixed", "value": 1}]
        assert client.post("/api/stops/generate", json=request_body).status_code == 422

    def test_zero_stop_count_rejected(self, request_body):
        request_body["stop_count"] = 0
        assert client.post("/api/stops/generate", json=request_body).status_code == 422


@pytest.mark.skipif(not LOCATION_DB_PATH.exists(), reason="bundled location_db.xls not present")
class TestGenerateEndpoint:
    def test_returns_metadata_and_base64_content(self, request_body):
        response = client.post("/api/stops/generate", json=request_body)
        assert response.status_code == 200
        body = response.json()
        assert body["filename"] == "stops.xlsx"
        assert body["seed"] == 5
        assert body["selected_stop_count"] > 0
        decoded = base64.b64decode(body["stop_file_base64"])
        assert decoded[:2] == b"PK"


@pytest.mark.skipif(not LOCATION_DB_PATH.exists(), reason="bundled location_db.xls not present")
class TestDownloadEndpoint:
    def test_returns_attachment_with_content_disposition(self, request_body):
        response = client.post("/api/stops/download", json=request_body)
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="stops.xlsx"'
        assert response.content[:2] == b"PK"
