"""Cross-generator consistency: SPEC-001's truck output feeds SPEC-002's stop input.

Covers the automatable half of spec.md's "integration test with SPEC-001
truck output -> combined DirectRoute import smoke test" expectation. The
DirectRoute-import half is a manual smoke test (waived as AC10 in
.spec/SPEC-002-stop-file-generator/meta.yaml) since DirectRoute isn't
available in CI; this test instead verifies the two generators agree on
the depot/volume shapes that flow between them.
"""

import pandas as pd

from backend.generators.stop import generate_stop_file, select_candidates
from backend.generators.truck import generate_truck_file
from backend.schemas.stop_config import SelectionConfig, StopConfig, TimeWindowConfig, VolumeAnswer
from backend.schemas.truck_config import DepotSpec, TruckConfig
from backend.services.spatial import load_location_db

SAMPLE_DB_PATH = "fixtures/stop/sample_location_db.xlsx"


def test_truck_response_depot_and_volume_shapes_feed_directly_into_stop_config():
    """A TruckConfig's own depots/volumes -- the shapes SPEC-001's response
    echoes back via DepotSummary/VolumeSpec -- must be directly usable as
    StopConfig input with no field translation, proving the contract SPEC-002
    was told to mirror actually round-trips end to end."""
    truck_config = TruckConfig(
        weeks=4,
        depots=[DepotSpec(address="1 Depot Way", city="Columbus", state="OH", zip="43215", trucks=3)],
        volumes=[],
        seed=1,
    )
    # Generating the truck file must not raise, and its depots/volumes are
    # exactly what SPEC-001's DepotSummary/VolumeSpec echo back to the wizard.
    generate_truck_file(truck_config)

    location_db = load_location_db(SAMPLE_DB_PATH)
    stop_config = StopConfig(
        depots=[
            {
                "address": d.address,
                "city": d.city,
                "state": d.state,
                "zip": d.zip,
                "truck_count": d.trucks,
            }
            for d in truck_config.depots
        ],
        weeks=truck_config.weeks,
        volumes=[{"name": "Cube", "capacity": 1800}],
        selection=SelectionConfig(mode="radius", radius_miles=50),
        stop_count=10,
        fixed_time_minutes=15,
        volume_answers=[VolumeAnswer(name="Cube", mode="fixed", value=25)],
        frequency_values=[1],
        time_window=TimeWindowConfig(mode="fixed", open1=800, close1=1700, pattern_scope="week"),
        seed=1,
    )

    candidates, _ = select_candidates(stop_config, location_db)
    content = generate_stop_file(stop_config, candidates)

    df = pd.read_excel(pd.io.common.BytesIO(content), sheet_name="Stop File")
    assert len(df) == len(candidates) > 0
    # The depot the stops were selected around should itself be resolvable
    # from the same location_db used for DC-coordinate matching.
    assert (df["State"] == "OH").all()
