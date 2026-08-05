"""End-to-end generator chain: truck -> stop -> DRProject.config (SPEC-012).

Automates the wizard's three-artifact download path. The DirectRoute import
half remains a manual smoke test — see README "DirectRoute smoke test".
"""

import xml.etree.ElementTree as ET

import pandas as pd

from backend.generators.drproject_config import generate_drproject_config
from backend.generators.stop import generate_stop_file, select_candidates
from backend.generators.truck import generate_truck_file
from backend.schemas.stop_config import SelectionConfig, StopConfig, TimeWindowConfig, VolumeAnswer
from backend.schemas.truck_config import DepotSpec, TruckConfig
from backend.services.spatial import load_location_db

SAMPLE_DB_PATH = "fixtures/stop/sample_location_db.xlsx"


def test_truck_stop_and_drproject_config_generate_from_shared_stop_config():
    """Truck output shapes feed StopConfig, and the same StopConfig drives
    both stop-file and DRProject.config generation without field translation."""
    truck_config = TruckConfig(
        weeks=4,
        depots=[DepotSpec(address="1 Depot Way", city="Columbus", state="OH", zip="43215", trucks=3)],
        volumes=[],
        seed=1,
    )
    truck_bytes = generate_truck_file(truck_config)
    assert len(truck_bytes) > 0

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
    stop_bytes = generate_stop_file(stop_config, candidates)
    stop_df = pd.read_excel(pd.io.common.BytesIO(stop_bytes), sheet_name="Stop File")
    assert len(stop_df) == len(candidates) > 0

    drproject_bytes = generate_drproject_config(stop_config)
    root = ET.fromstring(drproject_bytes)
    assert root.tag == "AppSettings"
    stop_section = root.find("./Configuration/Stop")
    assert stop_section is not None
    assert stop_section.findtext("ID1") == "Store #"
    quantities = stop_section.findall("./Quantities/Quantity")
    assert [q.findtext("Name") for q in quantities] == ["Cube"]
