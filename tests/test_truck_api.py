"""FastAPI contract tests for the truck generation endpoints (SPEC-001, AC6)."""

import base64

import pytest
from fastapi.testclient import TestClient

from backend.generators.truck import generate_truck_file
from backend.main import app
from backend.schemas.truck_config import TruckConfig

client = TestClient(app)


@pytest.fixture
def request_body() -> dict:
    return {
        "weeks": 2,
        "depots": [
            {"address": "100 Depot Way", "city": "Dallas", "state": "TX", "zip": "75201", "trucks": 5},
            {"address": "9 Harbor Rd", "city": "Reno", "state": "NV", "zip": "89501", "trucks": 2},
        ],
        "volumes": [
            {"name": "Cube", "capacity": 1800},
            {"name": "Weight", "capacity": 44000},
        ],
        "seed": 7,
    }


class TestGenerateEndpoint:
    def test_returns_routing_metadata(self, request_body):
        response = client.post("/api/trucks/generate", json=request_body)
        assert response.status_code == 200

        body = response.json()
        assert body["truck_row_count"] == 7 * 2 * 7  # territories * weeks * 7
        assert body["weeks"] == 2
        assert body["territory_count"] == 7
        assert body["depot_count"] == 2
        assert body["seed"] == 7
        assert body["filename"] == "fleet.truck"

        assert [d["truck_count"] for d in body["depots"]] == [5, 2]
        assert body["depots"][0] == {
            "address": "100 Depot Way",
            "city": "Dallas",
            "state": "TX",
            "zip": "75201",
            "truck_count": 5,
            "latitude": None,
            "longitude": None,
        }
        assert [v["name"] for v in body["volume_names"]] == ["Cube", "Weight"]
        assert [v["capacity"] for v in body["volume_names"]] == [1800, 44000]

    def test_base64_content_round_trips_to_generator_bytes(self, request_body):
        response = client.post("/api/trucks/generate", json=request_body)
        decoded = base64.b64decode(response.json()["truck_file_base64"])
        assert decoded == generate_truck_file(TruckConfig(**request_body))

    def test_defaults_applied_for_minimal_request(self):
        response = client.post(
            "/api/trucks/generate",
            json={
                "weeks": 1,
                "depots": [
                    {"address": "1 Main St", "city": "Waco", "state": "TX", "zip": "76701", "trucks": 1}
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["truck_row_count"] == 7
        assert body["volume_names"] == []
        assert body["seed"] == 0


class TestDownloadEndpoint:
    def test_returns_attachment_with_content_disposition(self, request_body):
        response = client.post("/api/trucks/download", json=request_body)
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="fleet.truck"'
        assert response.headers["content-type"].startswith("text/tab-separated-values")
        assert response.content == generate_truck_file(TruckConfig(**request_body))


class TestRequestValidation:
    def test_zero_weeks_rejected(self, request_body):
        request_body["weeks"] = 0
        assert client.post("/api/trucks/generate", json=request_body).status_code == 422

    def test_missing_depots_rejected(self):
        assert client.post("/api/trucks/generate", json={"weeks": 1, "depots": []}).status_code == 422

    def test_duplicate_volume_names_rejected(self, request_body):
        request_body["volumes"] = [
            {"name": "Cube", "capacity": 100},
            {"name": "Cube", "capacity": 200},
        ]
        assert client.post("/api/trucks/generate", json=request_body).status_code == 422
