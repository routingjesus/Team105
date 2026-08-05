"""Unit tests for DC-coordinate resolution, filtering, and density thinning (SPEC-002)."""

import numpy as np
import pandas as pd
import pytest

from backend.schemas.truck_config import DepotSpec
from backend.services.spatial import (
    DepotCoordinateError,
    filter_by_radius,
    filter_by_state,
    haversine_miles,
    load_location_db,
    resolve_depot_coordinates,
    thin_to_target,
)

SAMPLE_DB_PATH = "fixtures/stop/sample_location_db.xlsx"


@pytest.fixture(scope="module")
def location_db() -> pd.DataFrame:
    return load_location_db(SAMPLE_DB_PATH)


def test_load_location_db_has_required_columns(location_db):
    for col in ("Name", "Address", "City", "State", "Zip", "Latitude", "Longitude"):
        assert col in location_db.columns
    assert len(location_db) == 56


def test_haversine_known_distance():
    # Columbus, OH to Cleveland, OH is ~125 miles great-circle.
    miles = haversine_miles(39.9612, -82.9988, 41.4993, -81.6944)
    assert 115 < miles < 135


def test_resolve_depot_coordinates_exact_address_match(location_db):
    depot = DepotSpec(address="1 Depot Way", city="Columbus", state="OH", zip="43215", trucks=1)
    lat, lon = resolve_depot_coordinates(depot, location_db)
    assert lat == pytest.approx(39.9612, abs=0.01)
    assert lon == pytest.approx(-82.9988, abs=0.01)


def test_resolve_depot_coordinates_falls_back_to_city_state_zip(location_db):
    # Address doesn't exist verbatim in the DB, but city/state/zip does.
    depot = DepotSpec(address="Unknown Address", city="Columbus", state="OH", zip="43215", trucks=1)
    lat, lon = resolve_depot_coordinates(depot, location_db)
    assert lat == pytest.approx(39.9612, abs=0.3)
    assert lon == pytest.approx(-82.9988, abs=0.3)


def test_resolve_depot_coordinates_raises_when_no_match(location_db):
    depot = DepotSpec(address="Nowhere", city="Nowhere", state="ZZ", zip="00000", trucks=1)
    with pytest.raises(DepotCoordinateError):
        resolve_depot_coordinates(depot, location_db)


def test_filter_by_radius_keeps_only_nearby_stops(location_db):
    dc_coords = [(39.9612, -82.9988)]  # Columbus
    filtered = filter_by_radius(location_db, dc_coords, radius_miles=50)
    assert len(filtered) < len(location_db)
    assert (filtered["State"] == "OH").all()


def test_filter_by_radius_wider_radius_includes_more(location_db):
    dc_coords = [(39.9612, -82.9988)]
    narrow = filter_by_radius(location_db, dc_coords, radius_miles=10)
    wide = filter_by_radius(location_db, dc_coords, radius_miles=2000)
    assert len(wide) >= len(narrow)
    assert len(wide) == len(location_db)  # TX cluster within 2000mi of OH


def test_filter_by_state_ignores_dc_location(location_db):
    filtered = filter_by_state(location_db, ["TX"])
    assert len(filtered) == 15
    assert (filtered["State"] == "TX").all()


def test_filter_by_state_is_case_insensitive(location_db):
    filtered = filter_by_state(location_db, ["tx"])
    assert len(filtered) == 15


def test_thin_to_target_reduces_to_exact_count(location_db):
    thinned = thin_to_target(location_db, target_count=10, seed=1)
    assert len(thinned) == 10


def test_thin_to_target_noop_when_already_under_target(location_db):
    thinned = thin_to_target(location_db, target_count=1000, seed=1)
    assert len(thinned) == len(location_db)


def test_thin_to_target_returns_empty_for_non_positive_target(location_db):
    assert len(thin_to_target(location_db, target_count=0, seed=1)) == 0
    assert len(thin_to_target(location_db, target_count=-5, seed=1)) == 0


def test_filter_by_state_returns_empty_for_unmatched_state(location_db):
    filtered = filter_by_state(location_db, ["ZZ"])
    assert len(filtered) == 0
    # Thinning an already-empty frame should not error.
    assert len(thin_to_target(filtered, target_count=10, seed=1)) == 0


def test_thin_to_target_preserves_spatial_spread_not_clustered(location_db):
    # Thinning the OH+TX mix down to 10 should keep representation from
    # both clusters, not collapse onto one (a naive prefix/random-without-
    # weighting approach could drop the smaller TX cluster entirely).
    thinned = thin_to_target(location_db, target_count=10, seed=3)
    states_present = set(thinned["State"])
    assert "OH" in states_present
    assert "TX" in states_present


def test_thin_to_target_is_deterministic_for_a_given_seed(location_db):
    first = thin_to_target(location_db, target_count=12, seed=99)
    second = thin_to_target(location_db, target_count=12, seed=99)
    assert sorted(first.index) == sorted(second.index)


def test_load_location_db_strips_whitespace_padding(tmp_path):
    # The real legacy database stores fixed-width, whitespace-padded text.
    # The loader must normalize it so matching against un-padded user input
    # works (regression: padded values broke both address/city/state/zip
    # resolution and state filtering).
    padded = pd.DataFrame(
        {
            "Name": ["Customer 1                "],
            "Address": ["1216 GREENBRIER PARKWAY   "],
            "City": ["CHESAPEAKE                "],
            "State": ["VA    "],
            "Zip": ["23320 "],
            "Latitude": [36.7689],
            "Longitude": [-76.2304],
        }
    )
    db_path = tmp_path / "padded_location_db.xlsx"
    padded.to_excel(db_path, index=False)

    loaded = load_location_db(db_path)
    assert loaded.loc[0, "State"] == "VA"
    assert loaded.loc[0, "City"] == "CHESAPEAKE"
    assert loaded.loc[0, "Address"] == "1216 GREENBRIER PARKWAY"
    assert str(loaded.loc[0, "Zip"]).strip() == "23320"

    # Un-padded, differently-cased user input now resolves.
    depot = DepotSpec(
        address="1216 Greenbrier Parkway", city="Chesapeake", state="VA", zip="23320", trucks=1
    )
    lat, lon = resolve_depot_coordinates(depot, loaded)
    assert lat == pytest.approx(36.7689, abs=0.01)
    assert lon == pytest.approx(-76.2304, abs=0.01)

    # State filtering also works against the normalized value.
    assert len(filter_by_state(loaded, ["va"])) == 1


def test_resolve_depot_coordinates_uses_inline_coords(location_db):
    from backend.schemas.truck_config import DepotSummary

    depot = DepotSummary(
        address="Unknown",
        city="Denver",
        state="CO",
        zip="80202",
        truck_count=1,
        latitude=39.7392,
        longitude=-104.9903,
    )
    lat, lon = resolve_depot_coordinates(depot, location_db)
    assert lat == pytest.approx(39.7392)
    assert lon == pytest.approx(-104.9903)
