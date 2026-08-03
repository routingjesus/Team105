"""Unit tests for the stop file generator (SPEC-002)."""

import random

import pandas as pd
import pytest

from backend.generators.stop import (
    COLUMN_ORDER,
    REQUIRED_COLUMNS,
    VOLUMES_MARKER,
    FrequencyConsistencyError,
    achievable_frequency_values,
    build_header,
    build_pattern1,
    build_rows,
    build_time_window,
    generate_stop_file,
    select_candidates,
    selected_stops_from_candidates,
    validate_time_window,
)
from backend.schemas.stop_config import (
    AliasConfig,
    ConsolidationConfig,
    EqCodeConfig,
    SelectionConfig,
    StopConfig,
    TimeWindowConfig,
    VolumeAnswer,
)
from backend.schemas.truck_config import DepotSummary, VolumeSpec
from backend.services.spatial import load_location_db

SAMPLE_DB_PATH = "fixtures/stop/sample_location_db.xlsx"
GOLDEN_TEMPLATE_PATH = "fixtures/stop/TEMPLATE_NewConfigStopFile.xls"


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


class TestGoldenColumnOrder:
    def test_output_column_order_matches_golden_template(self, base_config):
        golden = pd.ExcelFile(GOLDEN_TEMPLATE_PATH, engine="xlrd").parse("Stop File", nrows=1)
        golden_columns = list(golden.columns)

        # The golden template's two generic volume slots ("Cube", "Weight")
        # collapse into one dynamic VOLUMES_MARKER segment in COLUMN_ORDER.
        # Requesting exactly those two volume names reproduces the golden
        # header exactly, proving the surrounding column order matches.
        base_config.volumes = [VolumeSpec(name="Cube", capacity=1800), VolumeSpec(name="Weight", capacity=44000)]
        base_config.volume_answers = [
            VolumeAnswer(name="Cube", mode="fixed", value=25),
            VolumeAnswer(name="Weight", mode="fixed", value=500),
        ]
        header = build_header(base_config)
        assert header == golden_columns

    def test_required_columns_are_a_subset_of_golden_columns(self):
        golden = pd.ExcelFile(GOLDEN_TEMPLATE_PATH, engine="xlrd").parse("Stop File", nrows=1)
        golden_columns = set(golden.columns) | {"Store #"}
        for col in REQUIRED_COLUMNS:
            assert col in golden_columns


class TestBuildHeader:
    def test_default_headers_used_without_aliases(self, base_config):
        header = build_header(base_config)
        assert "Name" in header
        assert "Store #" in header

    def test_aliases_override_default_headers(self, base_config):
        base_config.aliases = AliasConfig(name="Customer Name", id1="Account #")
        header = build_header(base_config)
        assert "Customer Name" in header
        assert "Account #" in header
        assert "Name" not in header
        assert "Store #" not in header

    def test_volume_columns_expand_for_multiple_volumes(self, base_config):
        base_config.volumes = [VolumeSpec(name="Cube", capacity=1800), VolumeSpec(name="Weight", capacity=44000)]
        base_config.volume_answers = [
            VolumeAnswer(name="Cube", mode="fixed", value=25),
            VolumeAnswer(name="Weight", mode="fixed", value=500),
        ]
        header = build_header(base_config)
        assert "Cube" in header
        assert "Weight" in header
        assert VOLUMES_MARKER not in header


class TestAchievableFrequency:
    def test_weekly_values_always_achievable(self):
        assert achievable_frequency_values([7, 1], weeks=1) == [7, 1]

    def test_sub_weekly_requires_enough_weeks(self):
        # .25 = monthly cadence, needs a 4-week horizon.
        assert achievable_frequency_values([0.25], weeks=1) == []
        assert achievable_frequency_values([0.25], weeks=4) == [0.25]

    def test_build_rows_raises_when_nothing_is_achievable(self, base_config, location_db):
        base_config.weeks = 1
        base_config.frequency_values = [0.083]  # ~quarterly, needs ~12 weeks
        candidates = select_candidates(base_config, location_db)
        with pytest.raises(FrequencyConsistencyError):
            build_rows(base_config, candidates)


class TestTimeWindow:
    def test_validate_time_window_rejects_out_of_range(self):
        assert validate_time_window(-1, 100, 15) is False
        assert validate_time_window(100, 2400, 15) is False

    def test_validate_time_window_rejects_close_before_open(self):
        assert validate_time_window(900, 800, 15) is False

    def test_validate_time_window_rejects_window_narrower_than_fixed_time(self):
        # 08:00-08:10 is only 10 minutes wide but FixedTime needs 15.
        assert validate_time_window(800, 810, 15) is False

    def test_validate_time_window_accepts_wide_enough_window(self):
        assert validate_time_window(800, 900, 15) is True

    def test_fixed_mode_returns_configured_window_for_every_call(self, base_config):
        rng = random.Random(1)
        for _ in range(5):
            open1, close1, pattern1 = build_time_window(base_config, rng)
            assert (open1, close1) == (800, 1700)

    def test_randomized_mode_always_satisfies_fixed_time_constraint(self, base_config):
        base_config.time_window = TimeWindowConfig(mode="randomized", pattern_scope="week")
        rng = random.Random(2)
        for _ in range(50):
            open1, close1, _ = build_time_window(base_config, rng)
            assert validate_time_window(open1, close1, base_config.fixed_time_minutes)

    def test_build_pattern1_week_scope_is_all_active(self):
        pattern = build_pattern1("week", None, random.Random(0))
        assert pattern == "SMTWRFA"

    def test_build_pattern1_weekday_scope_excludes_weekend(self):
        pattern = build_pattern1("weekday", None, random.Random(0))
        assert pattern[0] == "-"  # Sunday
        assert pattern[-1] == "-"  # Saturday ("A")
        assert pattern[1:6] == "MTWRF"

    def test_build_pattern1_specific_days(self):
        pattern = build_pattern1("specific_days", ["M", "W", "F"], random.Random(0))
        assert pattern == "-M-W-F-"


class TestSelectedStops:
    def test_id1_falls_back_to_name_when_missing(self):
        df = pd.DataFrame([{"Name": "Acme Co", "ID1": "", "ID3": "", "Address": "1 St", "City": "X", "State": "OH", "Zip": "1"}])
        stops = selected_stops_from_candidates(df)
        assert stops[0].id1 == "Acme Co"


class TestBuildRows:
    def test_row_count_matches_selected_stops_without_consolidation(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)
        rows = build_rows(base_config, candidates)
        assert len(rows) == len(candidates) == base_config.stop_count

    def test_required_columns_are_populated_for_every_row(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        indices = {col: header.index(col if col != "Store #" else "Store #") for col in REQUIRED_COLUMNS}
        for row in rows:
            for col, idx in indices.items():
                assert row[idx] != "", f"{col} was left blank"

    def test_frequency_values_come_from_requested_subset(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)
        header = build_header(base_config)
        freq_idx = header.index("Frequency")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        seen = {float(row[freq_idx]) for row in rows}
        assert seen <= set(base_config.frequency_values)

    def test_consolidation_creates_n_rows_per_customer_with_unique_id2(self, base_config, location_db):
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
        candidates = select_candidates(base_config, location_db)
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        assert len(rows) == len(candidates) * 3

        id2_idx = header.index("ID2")
        address_idx = header.index("Address")
        fixed_time_idx = header.index("FixedTime")
        for i in range(0, len(rows), 3):
            group = rows[i : i + 3]
            ids2 = {row[id2_idx] for row in group}
            assert len(ids2) == 3  # unique per line item
            addresses = {row[address_idx] for row in group}
            assert len(addresses) == 1  # shared physical stop
            fixed_times = {row[fixed_time_idx] for row in group}
            assert len(fixed_times) == 1  # FixedTime once per stop, not per line

    def test_eq_code_assigned_to_a_subset_not_all(self, base_config, location_db):
        base_config.stop_count = 20
        base_config.selection = SelectionConfig(mode="state", states=["OH"])
        base_config.eq_code = EqCodeConfig(enabled=True, codes=["LIFT", "PALLET"], fraction=0.25)
        candidates = select_candidates(base_config, location_db)
        header = build_header(base_config)
        eq_idx = header.index("EqCode")
        rows = build_rows(base_config, candidates)
        with_code = [row for row in rows if row[eq_idx] != ""]
        assert 0 < len(with_code) < len(rows)
        for row in with_code:
            assert row[eq_idx] in {"LIFT", "PALLET"}

    def test_deterministic_output_for_same_seed(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)
        first = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        second = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        assert first == second


class TestGenerateStopFile:
    def test_generates_valid_xlsx_readable_by_pandas(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)
        content = generate_stop_file(base_config, candidates)
        assert content[:2] == b"PK"  # xlsx is a zip container
        df = pd.read_excel(pd.io.common.BytesIO(content), sheet_name="Stop File")
        assert len(df) == len(candidates)
        assert list(df.columns) == build_header(base_config)
