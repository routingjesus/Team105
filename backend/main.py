"""FastAPI app exposing truck file generation (SPEC-001).

Two delivery shapes over the same request body:
- POST /api/trucks/generate  -> JSON metadata with base64 .TRUCK content
- POST /api/trucks/download  -> raw .TRUCK file with Content-Disposition
"""

import base64

from fastapi import FastAPI
from fastapi.responses import Response

from backend.generators.truck import generate_truck_file
from backend.schemas.truck_config import (
    DepotSummary,
    TruckConfig,
    TruckGenerationResponse,
    VolumeSpec,
)

TRUCK_FILENAME = "fleet.truck"

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
