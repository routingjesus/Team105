"""Generate a small synthetic location_db fixture for SPEC-002 tests.

Not owner data -- fabricated coordinates/names spread across two clusters
(a dense one near a test DC in Columbus, OH, and a sparse one in Texas) so
radius, state, and density-thinning tests have realistic geometry to work
with.
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

rows = []

# Dense cluster near Columbus, OH (test DC), within ~40 miles.
columbus_lat, columbus_lon = 39.9612, -82.9988
for i in range(40):
    lat = columbus_lat + rng.normal(0, 0.25)
    lon = columbus_lon + rng.normal(0, 0.25)
    rows.append(
        {
            "Name": f"OH Customer {i + 1:03d}",
            "Contact": f"Contact {i + 1}",
            "Phone": "6145550100",
            "ID1": f"C-OH-{i + 1:03d}",
            "ID2": "",
            "ID3": "",
            "Address": f"{100 + i} Main St",
            "Address2": "",
            "City": "Columbus",
            "State": "OH",
            "Zip": "43215",
            "Latitude": round(lat, 6),
            "Longitude": round(lon, 6),
        }
    )

# Sparse cluster in Texas, far outside any reasonable radius of Columbus.
for i in range(15):
    lat = 31.0 + rng.normal(0, 1.5)
    lon = -99.0 + rng.normal(0, 1.5)
    rows.append(
        {
            "Name": f"TX Customer {i + 1:03d}",
            "Contact": f"Contact {i + 1}",
            "Phone": "5125550100",
            "ID1": f"C-TX-{i + 1:03d}",
            "ID2": "",
            "ID3": "",
            "Address": f"{200 + i} Ranch Rd",
            "Address2": "",
            "City": "Austin",
            "State": "TX",
            "Zip": "73301",
            "Latitude": round(lat, 6),
            "Longitude": round(lon, 6),
        }
    )

# The depot itself, resolvable by exact-address match.
rows.append(
    {
        "Name": "Test DC",
        "Contact": "",
        "Phone": "",
        "ID1": "DC-001",
        "ID2": "",
        "ID3": "",
        "Address": "1 Depot Way",
        "Address2": "",
        "City": "Columbus",
        "State": "OH",
        "Zip": "43215",
        "Latitude": columbus_lat,
        "Longitude": columbus_lon,
    }
)

df = pd.DataFrame(rows)
out_path = Path(__file__).parent / "sample_location_db.xlsx"
df.to_excel(out_path, index=False, engine="xlsxwriter")
print(f"Wrote {len(df)} rows to {out_path}")
