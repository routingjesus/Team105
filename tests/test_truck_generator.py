"""Unit and golden-parity tests for the .TRUCK generator (SPEC-001)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.generators.truck import (
    BASE_COLUMN_COUNT,
    DAY_CODES,
    build_header,
    build_rows,
    generate_truck_file,
)
from backend.schemas.truck_config import DepotSpec, TruckConfig, VolumeSpec

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "truck"

EXPECTED_HEADERS = [
    "TrkID", "Available", "OneWay", "Redispatch", "MinTm", "TurnTm", "SpEq",
    "UnldPerf%", "MiCost", "HrCost", "OTCost1", "OTCost2", "OTCost3",
    "OTCost4", "OTHrs1", "OTHrs2", "OTHrs3", "OTHrs4", "UnldHrCost",
    "DropCost", "WaitHrCost", "UnitCost", "FixedCost", "LayoverCost",
    "EarStart", "EDate", "LatStart", "LatFinish", "LDate", "WorkDay",
    "NormalStart", "Brk1Start", "Brk1Duration", "Brk2Start", "Brk2Duration",
    "Brk3Start", "Brk3Duration", "Brk4Start", "Brk4Duration", "Brk5Start",
    "Brk5Duration", "MaxWorkTm", "TargetWrkTm", "MaxDriveTm", "MinLayover",
    "MaxLayover", "MaxDrvTmB4Layover", "MaxLayovers", "Longitude",
    "Latitude", "Address", "City", "State", "Zip", "GeoResult", "Zone",
    "Symbol", "Size", "Color", "PreTrip", "PostTrip", "Territory", "LoadID",
    "DriverID", "DeviceID", "AMStart", "AMEnd", "AMAdj", "PMStart", "PMEnd",
    "PMAdj", "Day", "Week", "Route", "Wk Repeater", "Dash Repeater",
]


def macro_default_config(**overrides) -> TruckConfig:
    """Single-DC request matching Explode my Trucks macro defaults (AC1)."""
    params = {
        "weeks": 2,
        "depots": [
            {
                "address": "100 Depot Way",
                "city": "Dallas",
                "state": "TX",
                "zip": "75201",
                "trucks": 5,
            }
        ],
    }
    params.update(overrides)
    return TruckConfig(**params)


def parse_lines(content: bytes) -> list[list[str]]:
    text = content.decode("ascii")
    return [line.split("\t") for line in text.split("\r\n") if line]


class TestHeader:
    def test_header_has_76_columns_matching_macro(self):
        header = build_header(macro_default_config())
        assert len(header) == 76
        assert BASE_COLUMN_COUNT == 76
        assert header == EXPECTED_HEADERS

    def test_header_starts_trkid_ends_dash_repeater(self):
        header = build_header(macro_default_config())
        assert header[0] == "TrkID"
        assert header[-1] == "Dash Repeater"


class TestSeedValues:
    """AC2: row 2 seed values match macro defaults."""

    def test_row2_matches_macro_defaults(self):
        config = macro_default_config()
        lines = parse_lines(generate_truck_file(config))
        header, row2 = lines[0], lines[1]
        cell = dict(zip(header, row2))

        assert cell["Available"] == "TRUE"
        assert cell["OneWay"] == "FALSE"
        assert cell["Redispatch"] == "FALSE"
        assert cell["Size"] == "12"
        assert cell["MiCost"] == "1.39"
        assert cell["HrCost"] == "30.00"
        assert cell["FixedCost"] == "250.00"
        assert cell["MaxWorkTm"] == "14"
        assert cell["MaxDriveTm"] == "11"
        assert cell["PreTrip"] == "15"
        assert cell["PostTrip"] == "30"
        assert cell["Territory"] == "T01"
        assert cell["EDate"] == "1"
        assert cell["LDate"] == "1"
        assert cell["Day"] == "SU"
        assert cell["Week"] == "1"
        assert cell["Route"] == "1"
        assert cell["Wk Repeater"] == "Wk"
        assert cell["Dash Repeater"] == "-"

    def test_costs_always_two_decimals(self):
        config = macro_default_config(mi_cost=2, hr_cost=27.5)
        row = build_rows(config)[0]
        header = build_header(config)
        cell = dict(zip(header, row))
        assert cell["MiCost"] == "2.00"
        assert cell["HrCost"] == "27.50"


class TestRowLogic:
    """AC3: T x (W x 7) rows with macro auto-fill cycles."""

    @pytest.mark.parametrize(("weeks", "territories"), [(1, 1), (2, 5), (3, 2)])
    def test_row_count_formula(self, weeks, territories):
        config = macro_default_config(weeks=weeks)
        config.depots[0].trucks = territories
        rows = build_rows(config)
        assert len(rows) == territories * weeks * 7

    def test_day_cycle_su_through_sa(self):
        config = macro_default_config(weeks=1)
        config.depots[0].trucks = 1
        header = build_header(config)
        day_idx = header.index("Day")
        days = [row[day_idx] for row in build_rows(config)]
        assert days == ["SU", "MO", "TU", "WE", "TH", "FR", "SA"]
        assert DAY_CODES == ("SU", "MO", "TU", "WE", "TH", "FR", "SA")

    def test_edate_ldate_week_route_territory_autofill(self):
        config = macro_default_config(weeks=2)
        config.depots[0].trucks = 2
        header = build_header(config)
        rows = build_rows(config)
        idx = {name: header.index(name) for name in ("EDate", "LDate", "Week", "Route", "Territory", "TrkID")}

        dispatch_days = 14
        for i, row in enumerate(rows):
            territory_num = i // dispatch_days + 1
            day = i % dispatch_days + 1
            assert row[idx["Territory"]] == f"T{territory_num:02d}"
            assert row[idx["EDate"]] == str(day)
            assert row[idx["LDate"]] == str(day)
            assert row[idx["Week"]] == str((day - 1) // 7 + 1)
            assert row[idx["Route"]] == str(i + 1)

        # Territory labels: T01, T02 across the two trucks
        territories = {row[idx["Territory"]] for row in rows}
        assert territories == {"T01", "T02"}

    def test_trkid_composed_from_territory_week_day(self):
        config = macro_default_config(weeks=1)
        config.depots[0].trucks = 1
        header = build_header(config)
        row = build_rows(config)[0]
        assert row[header.index("TrkID")] == "T01-Wk1-SU"


class TestMultiDepot:
    """AC4: per-depot addresses and continued territory numbering."""

    def two_depot_config(self) -> TruckConfig:
        return macro_default_config(
            depots=[
                {"address": "100 Depot Way", "city": "Dallas", "state": "TX", "zip": "75201", "trucks": 2},
                {"address": "9 Harbor Rd", "city": "Reno", "state": "NV", "zip": "89501", "trucks": 3},
            ]
        )

    def test_total_rows_sum_trucks_per_depot(self):
        config = self.two_depot_config()
        assert len(build_rows(config)) == (2 + 3) * config.weeks * 7

    def test_depot_address_columns_per_row(self):
        config = self.two_depot_config()
        header = build_header(config)
        rows = build_rows(config)
        idx = {name: header.index(name) for name in ("Address", "City", "State", "Zip", "Territory")}
        dispatch_days = config.weeks * 7

        first_depot_rows = rows[: 2 * dispatch_days]
        second_depot_rows = rows[2 * dispatch_days:]
        assert all(r[idx["City"]] == "Dallas" and r[idx["Zip"]] == "75201" for r in first_depot_rows)
        assert all(r[idx["City"]] == "Reno" and r[idx["Zip"]] == "89501" for r in second_depot_rows)

    def test_territory_numbering_continues_across_depots(self):
        config = self.two_depot_config()
        header = build_header(config)
        idx = header.index("Territory")
        territories = {row[idx] for row in build_rows(config)}
        assert territories == {"T01", "T02", "T03", "T04", "T05"}


class TestVolumes:
    """AC5: named volume capacity columns."""

    def test_volume_columns_appended_with_user_names(self):
        config = macro_default_config(
            volumes=[{"name": "Cube", "capacity": 1800}, {"name": "Weight", "capacity": 44000}]
        )
        header = build_header(config)
        assert len(header) == 78
        assert header[76:] == ["Cube", "Weight"]

        row = build_rows(config)[0]
        assert row[76:] == ["1800", "44000"]

    def test_no_volumes_keeps_76_columns(self):
        content = generate_truck_file(macro_default_config())
        lines = parse_lines(content)
        assert all(len(line) == 76 for line in lines)

    def test_duplicate_volume_names_rejected(self):
        with pytest.raises(ValidationError):
            macro_default_config(
                volumes=[{"name": "Cube", "capacity": 100}, {"name": "Cube", "capacity": 200}]
            )


class TestFileFidelity:
    def test_crlf_line_endings_no_bom_no_trailing_tab(self):
        content = generate_truck_file(macro_default_config())
        assert not content.startswith(b"\xef\xbb\xbf")
        assert content.endswith(b"\r\n")
        text = content.decode("ascii")
        for line in text.split("\r\n"):
            assert "\n" not in line and "\r" not in line
            assert not line.endswith("\t")

    def test_deterministic_output_for_same_config_and_seed(self):
        a = generate_truck_file(macro_default_config(seed=42))
        b = generate_truck_file(macro_default_config(seed=42))
        assert a == b

    def test_non_ascii_input_rejected(self):
        with pytest.raises(ValidationError):
            macro_default_config(
                depots=[
                    {"address": "Stra\u00dfe 5", "city": "K\u00f6ln", "state": "TX", "zip": "75201", "trucks": 1}
                ]
            )


class TestGoldenParity:
    """Byte-equality against a known-good macro sample (raw bytes, not
    parsed CSV). Skips until the fixture lands - see fixtures/truck/README.md."""

    FIXTURE = FIXTURES_DIR / "single_depot_baseline.truck"
    FIXTURE_CONFIG = FIXTURES_DIR / "single_depot_baseline.json"

    @pytest.mark.skipif(
        not (FIXTURE.exists() and FIXTURE_CONFIG.exists()),
        reason="macro golden sample not yet available (SPEC-001 open item)",
    )
    def test_byte_parity_with_macro_baseline(self):
        config = TruckConfig(**json.loads(self.FIXTURE_CONFIG.read_text(encoding="ascii")))
        expected = self.FIXTURE.read_bytes()
        assert generate_truck_file(config) == expected


class TestValidation:
    def test_weeks_must_be_positive(self):
        with pytest.raises(ValidationError):
            macro_default_config(weeks=0)

    def test_at_least_one_depot_required(self):
        with pytest.raises(ValidationError):
            macro_default_config(depots=[])

    def test_trucks_per_depot_must_be_positive(self):
        with pytest.raises(ValidationError):
            macro_default_config(
                depots=[{"address": "A", "city": "B", "state": "TX", "zip": "1", "trucks": 0}]
            )
