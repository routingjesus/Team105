"""FastAPI app exposing truck (SPEC-001), stop (SPEC-002), DRProject.config
(SPEC-012), and stops CSV (SPEC-016) file generation.

Paired delivery shapes over the same request body, per generator:
- POST /api/trucks/generate | /api/stops/generate | /api/drproject-config/generate
  | /api/stops-csv/generate
  -> JSON metadata with base64 file content
- POST /api/trucks/download | /api/stops/download | /api/drproject-config/download
  | /api/stops-csv/download
  -> raw file bytes with Content-Disposition
"""

import base64
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from backend.generators.drproject_config import generate_drproject_config
from backend.generators.stop import (
    FrequencyConsistencyError,
    generate_stop_csv_file,
    generate_stop_file,
    select_candidates,
)
from backend.generators.truck import generate_truck_file
from backend.schemas.drproject_config import DrprojectConfigResponse
from backend.schemas.stop_config import (
    StopConfig,
    StopCsvGenerationResponse,
    StopCsvRequest,
    StopGenerationResponse,
)
from backend.schemas.truck_config import (
    DepotSummary,
    TruckConfig,
    TruckGenerationResponse,
    VolumeSpec,
)
from backend.services.spatial import DepotCoordinateError, load_location_db

RADIUS_NO_COORDS_ERROR_MESSAGE = (
    "No depot has coordinates available for radius selection. "
    "Paste coordinates for at least one depot, or choose state or zip selection."
)

TRUCK_FILENAME = "fleet.truck"
STOP_FILENAME = "stops.xlsx"
STOP_CSV_FILENAME = "stops.csv"
DRPROJECT_CONFIG_FILENAME = "DRProject.config"
LOCATION_DB_PATH = Path(__file__).parent / "data" / "location_db.xlsx"

app = FastAPI(title="Team105 Dataset Creation Wizard API")

# The wizard UI is a separate origin (e.g. http://localhost:3000) from this API
# (http://127.0.0.1:8000), so the browser needs CORS headers to allow its
# generate/download calls. Defaults cover the local dev ports; override with a
# comma-separated WIZARD_ALLOWED_ORIGINS for a deployed UI origin.
_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("WIZARD_ALLOWED_ORIGINS", ",".join(_DEFAULT_ALLOWED_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


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
                latitude=d.latitude,
                longitude=d.longitude,
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
        raise HTTPException(status_code=422, detail=RADIUS_NO_COORDS_ERROR_MESSAGE) from exc
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


@app.post("/api/drproject-config/generate", response_model=DrprojectConfigResponse)
def generate_drproject_config_endpoint(config: StopConfig) -> DrprojectConfigResponse:
    content = generate_drproject_config(config)
    return DrprojectConfigResponse(
        filename=DRPROJECT_CONFIG_FILENAME,
        drproject_config_file_base64=base64.b64encode(content).decode("ascii"),
    )


@app.post("/api/drproject-config/download")
def download_drproject_config(config: StopConfig) -> Response:
    content = generate_drproject_config(config)
    return Response(
        content=content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{DRPROJECT_CONFIG_FILENAME}"',
        },
    )


def _generate_stop_csv_content(request: StopCsvRequest) -> tuple[bytes, int, int, int]:
    location_db = _load_location_db_or_503()
    try:
        candidates, candidate_count = select_candidates(request, location_db)
    except DepotCoordinateError as exc:
        raise HTTPException(status_code=422, detail=RADIUS_NO_COORDS_ERROR_MESSAGE) from exc
    try:
        content = generate_stop_csv_file(request, candidates, request.branch)
    except FrequencyConsistencyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines_per_customer = (
        request.consolidation.lines_per_customer
        if request.consolidation and request.consolidation.enabled
        else 1
    )
    return content, candidate_count, len(candidates), len(candidates) * lines_per_customer


@app.post("/api/stops-csv/generate", response_model=StopCsvGenerationResponse)
def generate_stops_csv(request: StopCsvRequest) -> StopCsvGenerationResponse:
    content, candidate_count, selected_count, output_row_count = _generate_stop_csv_content(request)
    return StopCsvGenerationResponse(
        candidate_count=candidate_count,
        selected_stop_count=selected_count,
        output_row_count=output_row_count,
        seed=request.seed,
        filename=STOP_CSV_FILENAME,
        stop_csv_file_base64=base64.b64encode(content).decode("ascii"),
    )


@app.post("/api/stops-csv/download")
def download_stops_csv(request: StopCsvRequest) -> Response:
    content, _, _, _ = _generate_stop_csv_content(request)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{STOP_CSV_FILENAME}"',
        },
    )


