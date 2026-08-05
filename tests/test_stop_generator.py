"""Unit tests for the stop file generator (SPEC-002)."""

import random

import pandas as pd
import pytest
from pydantic import ValidationError

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
    COLOR_VALUES,
    SHAPE_VALUES,
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
REAL_DB_PATH = "backend/data/location_db.xlsx"


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

    def test_id2_id3_aliases_override_headers(self, base_config):
        base_config.aliases = AliasConfig(id2="Customer ID", id3="Route Zone")
        header = build_header(base_config)
        assert "Customer ID" in header
        assert "Route Zone" in header
        assert "ID2" not in header
        assert "ID3" not in header

    def test_id2_id3_blank_alias_falls_back_to_technical_name(self, base_config):
        base_config.aliases = AliasConfig(id2=None, id3="")
        header = build_header(base_config)
        assert "ID2" in header
        assert "ID3" in header

    def test_id2_id3_aliases_do_not_change_row_values(self, base_config, location_db):
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
        candidates = select_candidates(base_config, location_db)[0]

        header_default = build_header(base_config)
        rows_default = build_rows(base_config, candidates)
        id2_idx_default = header_default.index("ID2")
        values_default = [row[id2_idx_default] for row in rows_default]

        base_config.aliases = AliasConfig(id2="Customer ID", id3="Route Zone")
        header_aliased = build_header(base_config)
        rows_aliased = build_rows(base_config, candidates)
        id2_idx_aliased = header_aliased.index("Customer ID")

        # Aliasing the header must not change which values land in the column.
        assert id2_idx_aliased == id2_idx_default
        assert [row[id2_idx_aliased] for row in rows_aliased] == values_default

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
        candidates = select_candidates(base_config, location_db)[0]
        with pytest.raises(FrequencyConsistencyError):
            build_rows(base_config, candidates)

    def test_build_rows_raises_when_only_some_values_are_achievable(self, base_config, location_db):
        # SPEC-006 regression: weeks=1 fits `1` but not `0.5` (needs a
        # 2-week cycle). Previously this silently proceeded with `achievable
        # == [1.0]`, so every row got Frequency=1 regardless of the 0.5
        # request -- AC #2 requires a hard rejection instead.
        base_config.weeks = 1
        base_config.frequency_values = [1, 0.5]
        candidates = select_candidates(base_config, location_db)[0]
        with pytest.raises(FrequencyConsistencyError):
            build_rows(base_config, candidates)


class TestStopConfigRejectsInvalidFixedWindow:
    """AC6 regression: an invalid caller-supplied fixed window must be
    rejected at request validation, not silently written to output."""

    def _config_kwargs(self, base_config, **overrides) -> dict:
        kwargs = base_config.model_dump()
        kwargs.update(overrides)
        return kwargs

    def test_inverted_fixed_window_rejected_at_request_validation(self, base_config):
        kwargs = self._config_kwargs(
            base_config, time_window={"mode": "fixed", "open1": 1700, "close1": 800, "pattern_scope": "week"}
        )
        with pytest.raises(ValidationError):
            StopConfig(**kwargs)

    def test_fixed_window_narrower_than_fixed_time_rejected_at_request_validation(self, base_config):
        # 08:00-08:10 is 10 minutes wide; base_config.fixed_time_minutes is 15.
        kwargs = self._config_kwargs(
            base_config, time_window={"mode": "fixed", "open1": 800, "close1": 810, "pattern_scope": "week"}
        )
        with pytest.raises(ValidationError):
            StopConfig(**kwargs)

    def test_valid_fixed_window_at_exact_fixed_time_width_is_accepted(self, base_config):
        # 08:00-08:15 is exactly 15 minutes wide, matching fixed_time_minutes.
        kwargs = self._config_kwargs(
            base_config, time_window={"mode": "fixed", "open1": 800, "close1": 815, "pattern_scope": "week"}
        )
        StopConfig(**kwargs)  # should not raise


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

    def test_midnight_open1_renders_zero_padded_not_falsy_blank(self, base_config, location_db):
        # Regression: open1=0 (midnight) must render "0000", not "0" --
        # `if open1 else ...` treats the legitimate int 0 as falsy.
        base_config.time_window = TimeWindowConfig(mode="fixed", open1=0, close1=100, pattern_scope="week")
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        open1_idx = header.index("Open1")
        rows = build_rows(base_config, candidates)
        assert all(row[open1_idx] == "0000" for row in rows)

    def test_generated_pattern1_column_matches_day_letters_only_regex(self, base_config, location_db):
        # AC3 (SPEC-007): Pattern1 column values across generated output must
        # match ^[SMTWRFA]*$ -- no dash or other stray character, for every
        # pattern_scope choice.
        import re

        pattern1_regex = re.compile(r"^[SMTWRFA]*$")
        header = build_header(base_config)
        pattern1_idx = header.index("Pattern1")
        for scope in ("week", "weekday", "weekend", "random"):
            base_config.time_window = TimeWindowConfig(mode="randomized", pattern_scope=scope)
            candidates = select_candidates(base_config, location_db)[0]
            rows = build_rows(base_config, candidates)
            assert rows, "expected at least one generated stop row"
            assert all(pattern1_regex.match(row[pattern1_idx]) for row in rows)

        # The bug report's own reproduction case: specific_days=["M","W","F"]
        # previously rendered as "-M-W-F-" (interior + edge dashes).
        base_config.time_window = TimeWindowConfig(
            mode="randomized", pattern_scope="specific_days", specific_days=["M", "W", "F"]
        )
        candidates = select_candidates(base_config, location_db)[0]
        rows = build_rows(base_config, candidates)
        assert rows, "expected at least one generated stop row"
        assert all(pattern1_regex.match(row[pattern1_idx]) for row in rows)
        assert all(row[pattern1_idx] == "MWF" for row in rows)

    def test_randomized_mode_always_satisfies_fixed_time_constraint(self, base_config):
        base_config.time_window = TimeWindowConfig(mode="randomized", pattern_scope="week")
        rng = random.Random(2)
        for _ in range(50):
            open1, close1, _ = build_time_window(base_config, rng)
            assert validate_time_window(open1, close1, base_config.fixed_time_minutes)

    def test_randomized_mode_biases_toward_business_hours(self, base_config):
        # SPEC-009 regression: real-world stops are rarely open past 1700, so
        # the majority of generated windows should fall within 0500-1600 and
        # only a small minority should close after 1700.
        base_config.time_window = TimeWindowConfig(mode="randomized", pattern_scope="week")
        rng = random.Random(3)
        sample_size = 3000
        within_business_hours = 0
        closes_after_1700 = 0
        for _ in range(sample_size):
            open1, close1, _ = build_time_window(base_config, rng)
            if open1 >= 500 and close1 <= 1600:
                within_business_hours += 1
            if close1 > 1700:
                closes_after_1700 += 1

        assert within_business_hours / sample_size >= 0.75
        assert closes_after_1700 / sample_size <= 0.20

    def test_build_pattern1_week_scope_is_all_active(self):
        pattern = build_pattern1("week", None, random.Random(0))
        assert pattern == "SMTWRFA"

    def test_build_pattern1_weekday_scope_excludes_weekend(self):
        pattern = build_pattern1("weekday", None, random.Random(0))
        assert pattern == "MTWRF"

    def test_build_pattern1_specific_days(self):
        pattern = build_pattern1("specific_days", ["M", "W", "F"], random.Random(0))
        assert pattern == "MWF"

    def test_build_pattern1_never_contains_dash(self):
        # Regression (SPEC-007): Pattern1 must contain only SMTWRFA day
        # letters, never a leading/trailing/interior separator dash.
        import re

        for scope, specific_days in [
            ("week", None),
            ("weekday", None),
            ("weekend", None),
            ("specific_days", ["M", "W", "F"]),
            ("specific_days", []),
            ("random", None),
        ]:
            rng = random.Random(0)
            for _ in range(10):
                pattern = build_pattern1(scope, specific_days, rng)
                assert re.fullmatch(r"[SMTWRFA]*", pattern), (scope, pattern)


class TestSelectedStops:
    def test_id1_falls_back_to_name_when_missing(self):
        df = pd.DataFrame(
            [
                {
                    "Name": "Acme Co",
                    "ID1": "",
                    "ID3": "",
                    "Address": "1 St",
                    "City": "X",
                    "State": "OH",
                    "Zip": "1",
                    "Latitude": 39.1,
                    "Longitude": -82.9,
                }
            ]
        )
        stops = selected_stops_from_candidates(df)
        assert stops[0].id1 == "Acme Co"


class TestBuildRows:
    def test_row_count_matches_selected_stops_without_consolidation(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        rows = build_rows(base_config, candidates)
        assert len(rows) == len(candidates) == base_config.stop_count

    def test_required_columns_are_populated_for_every_row(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        indices = {col: header.index(col if col != "Store #" else "Store #") for col in REQUIRED_COLUMNS}
        for row in rows:
            for col, idx in indices.items():
                assert row[idx] != "", f"{col} was left blank"

    def test_frequency_values_come_from_requested_subset(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        freq_idx = header.index("Frequency")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        seen = {float(row[freq_idx]) for row in rows}
        assert seen <= set(base_config.frequency_values)

    def test_fractional_frequency_actually_populates_output(self, base_config, location_db):
        # SPEC-006 AC #1 and #3: a requested 0.5 must actually appear in the
        # rendered output, not just survive a subset-membership check (which
        # the bug satisfied even when every row was 1). weeks=2 is enough
        # for a 0.5 (biweekly) cycle to fit.
        base_config.weeks = 2
        base_config.stop_count = 20
        base_config.frequency_values = [1, 0.5]
        base_config.seed = 5
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        freq_idx = header.index("Frequency")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        seen = {float(row[freq_idx]) for row in rows}
        assert 0.5 in seen

    def test_consolidation_creates_n_rows_per_customer_with_unique_id2(self, base_config, location_db):
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
        candidates = select_candidates(base_config, location_db)[0]
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
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        eq_idx = header.index("EqCode")
        rows = build_rows(base_config, candidates)
        with_code = [row for row in rows if row[eq_idx] != ""]
        assert 0 < len(with_code) < len(rows)
        for row in with_code:
            assert row[eq_idx] in {"LIFT", "PALLET"}

    def test_deterministic_output_for_same_seed(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        first = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        second = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        assert first == second

    def test_shapes_and_colors_blank_by_default(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates)
        for row in rows:
            assert row[symbol_idx] == ""
            assert row[color_idx] == ""

    def test_shapes_generated_from_allowlist_when_enabled(self, base_config, location_db):
        base_config.generate_shapes = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates)
        for row in rows:
            assert row[symbol_idx] in SHAPE_VALUES
            assert row[color_idx] == ""

    def test_colors_generated_from_allowlist_when_enabled(self, base_config, location_db):
        base_config.generate_colors = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates)
        for row in rows:
            assert row[symbol_idx] == ""
            assert row[color_idx] in COLOR_VALUES

    def test_shapes_and_colors_both_generated_when_both_enabled(self, base_config, location_db):
        base_config.generate_shapes = True
        base_config.generate_colors = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates)
        for row in rows:
            assert row[symbol_idx] in SHAPE_VALUES
            assert row[color_idx] in COLOR_VALUES

    def test_consolidation_shares_symbol_and_color_across_line_items(
        self, base_config, location_db
    ):
        # SPEC-015 AC1: same customer (stride group) shares Symbol/Color.
        n = 3
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=n)
        base_config.generate_shapes = True
        base_config.generate_colors = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        assert len(rows) == len(candidates) * n

        for i in range(0, len(rows), n):
            group = rows[i : i + n]
            symbols = {row[symbol_idx] for row in group}
            colors = {row[color_idx] for row in group}
            assert len(symbols) == 1
            assert len(colors) == 1
            assert next(iter(symbols)) in SHAPE_VALUES
            assert next(iter(colors)) in COLOR_VALUES

    def test_consolidation_shapes_colors_blank_when_disabled(self, base_config, location_db):
        # SPEC-015 AC4: consolidation on, shapes/colors off → blank Symbol/Color.
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates)
        for row in rows:
            assert row[symbol_idx] == ""
            assert row[color_idx] == ""

    def test_consolidation_shares_symbol_only_when_shapes_enabled(self, base_config, location_db):
        # SPEC-015 AC1 (shapes and/or): shapes-only under consolidation.
        n = 3
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=n)
        base_config.generate_shapes = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        for i in range(0, len(rows), n):
            group = rows[i : i + n]
            symbols = {row[symbol_idx] for row in group}
            assert len(symbols) == 1
            assert next(iter(symbols)) in SHAPE_VALUES
            assert all(row[color_idx] == "" for row in group)

    def test_consolidation_shares_color_only_when_colors_enabled(self, base_config, location_db):
        # SPEC-015 AC1 (shapes and/or): colors-only under consolidation.
        n = 3
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=n)
        base_config.generate_colors = True
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        symbol_idx = header.index("Symbol")
        color_idx = header.index("Color")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        for i in range(0, len(rows), n):
            group = rows[i : i + n]
            colors = {row[color_idx] for row in group}
            assert len(colors) == 1
            assert next(iter(colors)) in COLOR_VALUES
            assert all(row[symbol_idx] == "" for row in group)


class TestCoordinateCarryThrough:
    """SPEC-005 regression: Latitude/Longitude must survive from location_db
    into the generated output rows, matching the source values exactly."""

    def test_coordinates_match_source_location_db(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        lon_idx = header.index("Longitude")
        lat_idx = header.index("Latitude")
        address_idx = header.index("Address")

        by_address = location_db.set_index("Address")
        for row in rows:
            assert row[lon_idx] != ""
            assert row[lat_idx] != ""
            source = by_address.loc[row[address_idx]]
            assert float(row[lon_idx]) == pytest.approx(float(source["Longitude"]), abs=1e-6)
            assert float(row[lat_idx]) == pytest.approx(float(source["Latitude"]), abs=1e-6)

    def test_coordinates_match_source_against_real_location_db(self, base_config):
        real_db = load_location_db(REAL_DB_PATH)
        candidates = select_candidates(base_config, real_db)[0]
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        lon_idx = header.index("Longitude")
        lat_idx = header.index("Latitude")
        address_idx = header.index("Address")

        by_address = real_db.set_index("Address")
        for row in rows:
            assert row[lon_idx] != ""
            assert row[lat_idx] != ""
            source = by_address.loc[row[address_idx]]
            assert float(row[lon_idx]) == pytest.approx(float(source["Longitude"]), abs=1e-6)
            assert float(row[lat_idx]) == pytest.approx(float(source["Latitude"]), abs=1e-6)

    def test_consolidation_shares_coordinates_across_line_items(self, base_config, location_db):
        base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        rows = build_rows(base_config, candidates)
        lon_idx = header.index("Longitude")
        lat_idx = header.index("Latitude")

        for i in range(0, len(rows), 3):
            group = rows[i : i + 3]
            longitudes = {row[lon_idx] for row in group}
            latitudes = {row[lat_idx] for row in group}
            assert len(longitudes) == 1
            assert len(latitudes) == 1


class TestVolumeCells:
    def test_fixed_mode_values_are_unchanged(self, base_config, location_db):
        # Regression guard: SPEC-008 only touches "averaged" mode.
        base_config.volume_answers = [VolumeAnswer(name="Cube", mode="fixed", value=25)]
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        cube_idx = header.index("Cube")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        assert all(row[cube_idx] == "25.00" for row in rows)

    def test_averaged_mode_produces_whole_numbers_with_meaningful_spread(self, base_config, location_db):
        # AC1 + AC2: averaged-mode volumes must render as whole numbers, and
        # the spread across many stops must be wide enough to look like real
        # variance rather than clustering within ~1 unit of the target mean.
        base_config.stop_count = 40
        base_config.volume_answers = [VolumeAnswer(name="Cube", mode="averaged", value=12)]
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        cube_idx = header.index("Cube")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        cells = [row[cube_idx] for row in rows]

        assert all("." not in cell for cell in cells), "averaged volumes must render without a decimal component"
        values = [int(cell) for cell in cells]
        assert max(values) - min(values) >= 4, "spread around the requested mean is too narrow"

    def test_averaged_mode_never_produces_non_positive_volumes(self, base_config, location_db):
        # A small requested mean with wide jitter must still floor at 1, not
        # a zero/negative unit count.
        base_config.stop_count = 40
        base_config.volume_answers = [VolumeAnswer(name="Cube", mode="averaged", value=2)]
        candidates = select_candidates(base_config, location_db)[0]
        header = build_header(base_config)
        cube_idx = header.index("Cube")
        rows = build_rows(base_config, candidates, rng=random.Random(base_config.seed))
        assert all(int(row[cube_idx]) >= 1 for row in rows)


class TestZeroCandidates:
    def test_no_matching_state_produces_empty_but_valid_output(self, base_config, location_db):
        base_config.selection = SelectionConfig(mode="state", states=["ZZ"])
        candidates = select_candidates(base_config, location_db)[0]
        assert len(candidates) == 0
        rows = build_rows(base_config, candidates)
        assert rows == []
        content = generate_stop_file(base_config, candidates)
        df = pd.read_excel(pd.io.common.BytesIO(content), sheet_name="Stop File")
        assert len(df) == 0
        assert list(df.columns) == build_header(base_config)


class TestGenerateStopFile:
    def test_generates_valid_xlsx_readable_by_pandas(self, base_config, location_db):
        candidates = select_candidates(base_config, location_db)[0]
        content = generate_stop_file(base_config, candidates)
        assert content[:2] == b"PK"  # xlsx is a zip container
        df = pd.read_excel(pd.io.common.BytesIO(content), sheet_name="Stop File")
        assert len(df) == len(candidates)
        assert list(df.columns) == build_header(base_config)
