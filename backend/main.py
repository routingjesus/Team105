"""FastAPI app exposing truck (SPEC-001) and stop (SPEC-002) file generation.

Paired delivery shapes over the same request body, per generator:
- POST /api/trucks/generate | /api/stops/generate  -> JSON metadata with
  base64 file content
- POST /api/trucks/download | /api/stops/download  -> raw file bytes with
  Content-Disposition
"""

import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from backend.generators.stop import FrequencyConsistencyError, generate_stop_file, select_candidates
from backend.generators.truck import generate_truck_file
from backend.schemas.stop_config import StopConfig, StopGenerationResponse
from backend.schemas.truck_config import (
    DepotSummary,
    TruckConfig,
    TruckGenerationResponse,
    VolumeSpec,
)
from backend.services.spatial import DepotCoordinateError, load_location_db

TRUCK_FILENAME = "fleet.truck"
STOP_FILENAME = "stops.xlsx"
LOCATION_DB_PATH = Path(__file__).parent / "data" / "location_db.xlsx"

app = FastAPI(title="Team105 Dataset Creation Wizard API")


@app.post("/api/trucks/generate", response_model=TruckGenerationResponse)
def generate_trucks(config: TruckConfig) -> TruckGenerationResponse:
    content = generate_truck_file(config)
    return TruckGenerationResponse(
        truck_row_count=config.territory_count * config.weeks * 7,
        weeks=config.weeks,
        territory_count=config.territory_count,
        depot_count=len(config.depots),
        depots=[
            DepotSummary(
                address=d.address,
                city=d.city,
                state=d.state,
                zip=d.zip,
                truck_count=d.trucks,
            )
            for d in config.depots
        ],
        volume_names=[VolumeSpec(name=v.name, capacity=v.capacity) for v in config.volumes],
        seed=config.seed,
        filename=TRUCK_FILENAME,
        truck_file_base64=base64.b64encode(content).decode("ascii"),
    )


@app.post("/api/trucks/download")
def download_trucks(config: TruckConfig) -> Response:
    content = generate_truck_file(config)
    return Response(
        content=content,
        media_type="text/tab-separated-values",
        headers={
            "Content-Disposition": f'attachment; filename="{TRUCK_FILENAME}"',
        },
    )


def _load_location_db_or_503():
    if not LOCATION_DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Static location database not found at {LOCATION_DB_PATH}. "
                "This bundled file is a deployment prerequisite, not user input."
            ),
        )
    return load_location_db(LOCATION_DB_PATH)


def _generate_stop_content(config: StopConfig) -> tuple[bytes, int, int, int]:
    location_db = _load_location_db_or_503()
    try:
        candidates, candidate_count = select_candidates(config, location_db)
    except DepotCoordinateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        content = generate_stop_file(config, candidates)
    except FrequencyConsistencyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines_per_customer = (
        config.consolidation.lines_per_customer
        if config.consolidation and config.consolidation.enabled
        else 1
    )
    return content, candidate_count, len(candidates), len(candidates) * lines_per_customer


@app.post("/api/stops/generate", response_model=StopGenerationResponse)
def generate_stops(config: StopConfig) -> StopGenerationResponse:
    content, candidate_count, selected_count, output_row_count = _generate_stop_content(config)
    return StopGenerationResponse(
        candidate_count=candidate_count,
        selected_stop_count=selected_count,
        output_row_count=output_row_count,
        seed=config.seed,
        filename=STOP_FILENAME,
        stop_file_base64=base64.b64encode(content).decode("ascii"),
    )


@app.post("/api/stops/download")
def download_stops(config: StopConfig) -> Response:
    content, _, _, _ = _generate_stop_content(config)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{STOP_FILENAME}"',
        },
    )
