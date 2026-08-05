"""FastAPI contract tests for DRProject.config generation endpoints (SPEC-012)."""

import base64

import pytest
from fastapi.testclient import TestClient

from backend.generators.drproject_config import generate_drproject_config
from backend.main import app
from backend.schemas.stop_config import SelectionConfig, StopConfig, TimeWindowConfig, VolumeAnswer
from backend.schemas.truck_config import DepotSummary, VolumeSpec

client = TestClient(app)


@pytest.fixture
def request_body() -> dict:
    return {
        "depots": [
            {"address": "100 Depot Way", "city": "Dallas", "state": "TX", "zip": "75201", "truck_count": 5},
        ],
        "weeks": 2,
        "volumes": [{"name": "Cube", "capacity": 1800}],
        "selection": {"mode": "radius", "radius_miles": 50},
        "stop_count": 20,
        "fixed_time_minutes": 15,
        "volume_answers": [{"name": "Cube", "mode": "fixed", "value": 25}],
        "frequency_values": [1],
        "time_window": {"mode": "fixed", "open1": 800, "close1": 1700, "pattern_scope": "week"},
        "seed": 0,
    }


class TestGenerateEndpoint:
    def test_returns_metadata_and_base64_content(self, request_body):
        response = client.post("/api/drproject-config/generate", json=request_body)
        assert response.status_code == 200

        body = response.json()
        assert body["filename"] == "DRProject.config"
        decoded = base64.b64decode(body["drproject_config_file_base64"])
        assert decoded == generate_drproject_config(StopConfig(**request_body))


class TestDownloadEndpoint:
    def test_returns_attachment_with_content_disposition(self, request_body):
        response = client.post("/api/drproject-config/download", json=request_body)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert 'filename="DRProject.config"' in response.headers["content-disposition"]
        assert response.content == generate_drproject_config(StopConfig(**request_body))
