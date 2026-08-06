"""Stops CSV generation (SPEC-016): Branch/Action columns + Delete selection."""

import base64
import csv
import io
import random

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.generators.stop import (
    build_header,
    build_rows,
    delete_action_count,
    generate_stop_csv_file,
    generate_stop_file,
    select_candidates,
)
from backend.main import LOCATION_DB_PATH, app
from backend.schemas.stop_config import (
    AliasConfig,
    SelectionConfig,
    StopConfig,
    StopCsvRequest,
    TimeWindowConfig,
    VolumeAnswer,
)
from backend.schemas.truck_config import DepotSummary, VolumeSpec
from backend.services.spatial import load_location_db

client = TestClient(app)
SAMPLE_DB_PATH = "fixtures/stop/sample_location_db.xlsx"


@pytest.fixture(scope="module")
def location_db() -> pd.DataFrame:
    return load_location_db(SAMPLE_DB_PATH)


@pytest.fixture
def base_config() -> StopConfig:
    return StopConfig(
        depots=[DepotSummary(address="1 Depot Way", city="Columbus", state="OH", zip="43215", truck_count=3)],
        weeks=4,
        volumes=[VolumeSpec(name="Cube", capacity=1800)],
        selection=SelectionConfig(mode="radius", radius_miles=50),
        stop_count=10,
        fixed_time_minutes=15,
        volume_answers=[VolumeAnswer(name="Cube", mode="fixed", value=25)],
        frequency_values=[1, 0.5],
        time_window=TimeWindowConfig(mode="fixed", open1=800, close1=1700, pattern_scope="week"),
        seed=5,
    )


@pytest.fixture
def request_body() -> dict:
    if LOCATION_DB_PATH.exists():
        first_row = load_location_db(LOCATION_DB_PATH).iloc[0]
        depot = {
            "address": str(first_row["Address"]),
            "city": str(first_row["City"]),
            "state": str(first_row["State"]),
            "zip": str(first_row["Zip"]),
            "truck_count": 3,
        }
    else:
        depot = {
            "address": "1 Depot Way",
            "city": "Columbus",
            "state": "OH",
            "zip": "43215",
            "truck_count": 3,
        }

    return {
        "depots": [depot],
        "weeks": 4,
        "volumes": [{"name": "Cube", "capacity": 1800}],
        "selection": {"mode": "radius", "radius_miles": 50},
        "stop_count": 10,
        "fixed_time_minutes": 15,
        "volume_answers": [{"name": "Cube", "mode": "fixed", "value": 25}],
        "frequency_values": [1, 0.5],
        "time_window": {"mode": "fixed", "open1": 800, "close1": 1700, "pattern_scope": "week"},
        "seed": 5,
        "branch": "ATL01",
    }


def _parse_csv(content: bytes) -> tuple[list[str], list[list[str]]]:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), dialect=csv.excel)
    rows = list(reader)
    return rows[0], rows[1:]


class TestDeleteActionCount:
    def test_formula_for_common_sizes(self):
        assert delete_action_count(0) == 0
        assert delete_action_count(1) == 1
        assert delete_action_count(5) == 1
        assert delete_action_count(10) == 1
        assert delete_action_count(14) == 1
        assert delete_action_count(15) == 2


class TestGenerateStopCsvFile:
    def test_bom_and_leading_columns(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        content = generate_stop_csv_file(base_config, candidates, "ATL01")
        assert content[:3] == b"\xef\xbb\xbf"
        header, data = _parse_csv(content)
        assert header[:2] == ["Branch", "Action"]
        assert header[2:] == build_header(base_config)
        assert all(row[0] == "ATL01" for row in data)
        assert set(row[1] for row in data) <= {"Modify", "Delete"}

    def test_delete_count_and_seed_determinism(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        a = generate_stop_csv_file(base_config, candidates, "BR01")
        b = generate_stop_csv_file(base_config, candidates, "BR01")
        assert a == b

        _, data = _parse_csv(a)
        n = len(data)
        assert n >= 1
        k = delete_action_count(n)
        delete_indices = [i for i, row in enumerate(data) if row[1] == "Delete"]
        assert len(delete_indices) == k
        expected = sorted(random.Random(base_config.seed).sample(range(n), k))
        assert delete_indices == expected

    def test_row_parity_with_xlsx(self, base_config, location_db):
        base_config.aliases = AliasConfig(name="Customer Name", id1="Account #")
        candidates = select_candidates(base_config, location_db)[0]
        csv_bytes = generate_stop_csv_file(base_config, candidates, "X1")
        xlsx_bytes = generate_stop_file(base_config, candidates)

        csv_header, csv_data = _parse_csv(csv_bytes)
        xlsx_df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Stop File", dtype=str)
        xlsx_df = xlsx_df.fillna("")
        assert csv_header[2:] == list(xlsx_df.columns)
        assert len(csv_data) == len(xlsx_df)
        for i, row in enumerate(csv_data):
            assert row[2:] == [str(v) for v in xlsx_df.iloc[i].tolist()]

    def test_build_rows_stream_isolation(self, base_config, location_db):
        """Delete indices must not depend on build_rows RNG consumption."""
        candidates = select_candidates(base_config, location_db)[0]
        rows = build_rows(base_config, candidates, random.Random(base_config.seed))
        n = len(rows)
        k = delete_action_count(n)
        expected = set(random.Random(base_config.seed).sample(range(n), k))

        _, data = _parse_csv(generate_stop_csv_file(base_config, candidates, "ISO"))
        actual = {i for i, row in enumerate(data) if row[1] == "Delete"}
        assert actual == expected


class TestStopCsvRequestValidation:
    def test_empty_branch_rejected(self):
        with pytest.raises(ValidationError):
            StopCsvRequest(
                depots=[DepotSummary(address="1", city="A", state="OH", zip="1", truck_count=1)],
                weeks=1,
                volumes=[VolumeSpec(name="Cube", capacity=1)],
                selection=SelectionConfig(mode="state", states=["OH"]),
                stop_count=1,
                fixed_time_minutes=15,
                volume_answers=[VolumeAnswer(name="Cube", mode="fixed", value=1)],
                frequency_values=[1],
                time_window=TimeWindowConfig(mode="fixed", open1=800, close1=1700),
                branch="   ",
            )


@pytest.mark.skipif(not LOCATION_DB_PATH.exists(), reason="bundled location_db.xls not present")
class TestStopsCsvApi:
    def test_generate_returns_metadata_and_bom_csv(self, request_body):
        response = client.post("/api/stops-csv/generate", json=request_body)
        assert response.status_code == 200
        body = response.json()
        assert body["filename"] == "stops.csv"
        assert body["seed"] == 5
        decoded = base64.b64decode(body["stop_csv_file_base64"])
        assert decoded[:3] == b"\xef\xbb\xbf"
        header, data = _parse_csv(decoded)
        assert header[:2] == ["Branch", "Action"]
        assert all(row[0] == "ATL01" for row in data)

    def test_download_attachment(self, request_body):
        response = client.post("/api/stops-csv/download", json=request_body)
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="stops.csv"'
        assert "text/csv" in response.headers["content-type"]
        assert response.content[:3] == b"\xef\xbb\xbf"

    def test_whitespace_branch_rejected(self, request_body):
        request_body["branch"] = "   "
        assert client.post("/api/stops-csv/generate", json=request_body).status_code == 422

    def test_missing_branch_rejected(self, request_body):
        del request_body["branch"]
        assert client.post("/api/stops-csv/generate", json=request_body).status_code == 422

    def test_identical_seed_and_branch_yields_identical_bytes(self, request_body):
        a = client.post("/api/stops-csv/generate", json=request_body).json()["stop_csv_file_base64"]
        b = client.post("/api/stops-csv/generate", json=request_body).json()["stop_csv_file_base64"]
        assert a == b
