"""Build backend/data/location_db.xls from the owner-supplied source workbook.

Source: a real "Customer Sites" export (store locations + a territory
conversion sheet) with 53 DirectRoute-specific columns. Per the owner's
instruction, real addresses/coordinates are kept (they're just geography),
but customer/store *names* are proprietary and are replaced with
deterministic synthetic placeholders before the file is bundled -- this
keeps SPEC-002's location_db realistic without shipping a real company's
customer roster in the repo.

Run once to (re)generate backend/data/location_db.xls:
    python backend/data/prepare_location_db.py "<path to source .xls>"
"""

import sys
from pathlib import Path

import pandas as pd

REQUIRED_OUTPUT_COLUMNS = ["Name", "ID1", "Contact", "Phone", "ID2", "ID3", "Address", "Address2", "City", "State", "Zip", "Latitude", "Longitude"]


def build_location_db(source_path: str) -> pd.DataFrame:
    source = pd.read_excel(source_path, sheet_name="store locations", engine="xlrd")

    out = pd.DataFrame()
    # Deterministic synthetic name, one per row -- scrambles the real
    # "Store Name" (e.g. "PUBLIX 889") without depending on row content,
    # so no fragment of the proprietary name survives.
    out["Name"] = [f"Customer {i + 1:05d}" for i in range(len(source))]
    out["ID1"] = source["Store #"].astype("string").fillna("")
    out["Contact"] = source.get("Contact", "")
    out["Phone"] = source.get("Phone", "")
    out["ID2"] = source.get("ID2", "")
    out["ID3"] = source.get("ID3", "")
    out["Address"] = source["Address"]
    out["Address2"] = source.get("Address2", "")
    out["City"] = source["City"]
    out["State"] = source["State"]
    out["Zip"] = source["Zip"].astype("string")
    out["Latitude"] = source["Latitude"]
    out["Longitude"] = source["Longitude"]
    return out[REQUIRED_OUTPUT_COLUMNS]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python backend/data/prepare_location_db.py <path to source .xls>")
    df = build_location_db(sys.argv[1])
    # .xlsx, not .xls: xlwt (the only .xls writer pandas supports) is
    # unmaintained and load_location_db already reads .xlsx via openpyxl.
    out_path = Path(__file__).parent / "location_db.xlsx"
    df.to_excel(out_path, index=False, engine="xlsxwriter")
    print(f"Wrote {len(df)} rows to {out_path}")
