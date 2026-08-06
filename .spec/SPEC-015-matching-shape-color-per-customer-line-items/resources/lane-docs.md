## Lane result

**Status:** `USEFUL`

**Summary:** SPEC-015 is a small generator fix—hoist `Symbol`/`Color` assignment out of the consolidation line-item loop to match existing per-stop fields (`EqCode`, `FixedTime`, coordinates); contracts are already documented in SPEC-002, SPEC-011, and consolidation tests.

---

## Sources

| Source | Why authoritative |
|--------|-------------------|
| `.spec/SPEC-015-matching-shape-color-per-customer-line-items/spec.md` | Target spec ACs and scope |
| `.spec/SPEC-011-optional-shape-color-generation/spec.md` + `meta.yaml` | Shape/color generation contract, allowlist provenance |
| `.spec/SPEC-002-stop-file-generator/spec.md` | Consolidation AC8, column order, per-customer sharing rules |
| `.spec/SPEC-005-stop-lat-long-dropped-from-stop-file/spec.md` | Consolidation coordinate-sharing precedent |
| `.spec/SPEC-014-static-size-28-with-shape-color/spec.md` | Related map-marker `Size` behavior (out of SPEC-015 scope) |
| `fixtures/stop/README.md` | Golden template role and column derivation |
| `backend/schemas/stop_config.py` | `SHAPE_VALUES` / `COLOR_VALUES` allowlists, `ConsolidationConfig` |
| `backend/generators/stop.py` | Current `build_rows` loop structure |
| `tests/test_stop_generator.py` | Consolidation + shape/color test patterns |
| [Python `random` module docs](https://docs.python.org/3/library/random.html) | `Random(seed)` + `choice()` determinism |
| [Pydantic v2 models](https://docs.pydantic.dev/latest/concepts/models/) | `ConsolidationConfig` validation (`gt=1`, `le=20`) |

---

## Findings

### 1. In-repo stop generation, consolidation, shapes/colors

**Consolidation contract (SPEC-002 AC8 + implementation guidance)**

- When `consolidation.enabled`, each selected customer produces `lines_per_customer` rows with **unique `ID2`** (`ORD-{stop_index:04d}-{line:02d}`).
- Consolidation rows for the same physical stop **share** address, time-window fields, `FixedTime`, and coordinates—not per line item.
- Density thinning happens at the **customer** level before line-item expansion.

Evidence: `.spec/SPEC-002-stop-file-generator/spec.md` (AC8, lines 24, 44, 86–88); `tests/test_stop_generator.py` (`test_consolidation_creates_n_rows_per_customer_with_unique_id2`, `test_consolidation_shares_coordinates_across_line_items`).

**Why it matters:** Symbol/Color should follow the same per-stop / per-customer grouping as `EqCode`, `FixedTime`, and lat/long—not the per-line-item `ID2` assignment.

---

**Customer identity for matching**

- Consolidation groups by **selected stop** (`stop_index` outer loop), not by `ID2`.
- `Store #` in output maps to `stop.id1` (canonical `ID1` from location DB); all line items for one stop reuse the same `Store #`.

Evidence:

```281:288:backend/generators/stop.py
        for line in range(1, lines_per_customer + 1):
            id2 = f"ORD-{stop_index + 1:04d}-{line:02d}"
            row_by_col = {
                ...
                "Store #": stop.id1,
                "ID2": id2,
```

**Why it matters:** SPEC-015 scope boundary (“Customer identity … Store # / ID1”) is already how consolidation works—no new identity key needed.

---

**Current bug (root cause)**

`rng.choice` for `Symbol`/`Color` runs **inside** the `for line` loop, so each line item gets independent values:

```304:307:backend/generators/stop.py
            if config.generate_shapes:
                row_by_col["Symbol"] = rng.choice(SHAPE_VALUES)
            if config.generate_colors:
                row_by_col["Color"] = rng.choice(COLOR_VALUES)
```

Contrast with per-stop fields assigned **before** the inner loop (`frequency`, `eq_code`, `open1`/`close1`/`pattern1`, `volume_cells` at lines 276–279).

**Why it matters:** Move shape/color picks to the outer loop (or precompute once per `stop_index`), then copy into each `row_by_col`.

---

**SPEC-011 shape/color contract**

- Wizard toggles: `generate_shapes`, `generate_colors` (booleans on `StopConfig`; no nested config).
- Values must come only from `SHAPE_VALUES` (35) and `COLOR_VALUES` (48) in `backend/schemas/stop_config.py`.
- When disabled, `Symbol`/`Color` stay blank (existing `row_by_col.get(col, "")` fallback).
- Deterministic given `seed` (NFR in SPEC-011).

Evidence: `.spec/SPEC-011-optional-shape-color-generation/spec.md`; `backend/schemas/stop_config.py` lines 23–115.

**Why it matters:** Hoisting choices preserves determinism if RNG call order changes minimally (one `choice` per stop vs. per line). Existing `test_deterministic_output_for_same_seed` should still pass; add consolidation+shapes test.

---

**No consolidation-specific spec beyond SPEC-002**

Consolidation is introduced in SPEC-002 (AC8, user scenario for Sales Engineers). SPEC-011 only places shape/color checkboxes alongside consolidation in the wizard UI—no interaction rule until SPEC-015.

---

### 2. DirectRoute Symbol/Color → map markers

**Column mapping (stop file)**

| Column | Role | Template description |
|--------|------|----------------------|
| `Symbol` | Shape / marker icon | “recommended but not required” |
| `Color` | Marker color | “recommended but not required, use for enhanced map interaction” |
| `Size` | Marker size | SPEC-014: static `28` when shapes/colors enabled (separate spec) |

Evidence: SPEC-011 research (golden `Header Desc.` via `xlrd`); `COLUMN_ORDER` in `backend/generators/stop.py` lines 46–47 (`… Longitude, Latitude, Symbol, Size, Color …`).

**Allowlist source**

- No complete public DirectRoute enum in repo or reachable Notion doc.
- Authoritative lists live in an **internal owner handout** (not tracked); encoded as `SHAPE_VALUES` / `COLOR_VALUES`.
- Earlier anecdotal samples (`Tower`, `Cyan`, etc.) are subsets of the real lists.

Evidence: `.spec/SPEC-011-optional-shape-color-generation/meta.yaml` learnings (`gap_found` entry).

**Why it matters:** Implementation must not invent values; import `SHAPE_VALUES` / `COLOR_VALUES`. No external DirectRoute API docs found for runtime marker rendering—file-column contract only.

---

### 3. Related specs (contracts)

| Spec | Relevance to SPEC-015 |
|------|------------------------|
| **SPEC-011** | Defines shape/color generation ACs, allowlists, `build_rows` wiring, test patterns |
| **SPEC-002** | Consolidation AC8; per-customer field sharing; `Store #` = ID1 |
| **SPEC-005** | Consolidation coordinate sharing mirrors required Symbol/Color sharing |
| **SPEC-014** | `Size=28` when shapes/colors on; does not change Symbol/Color logic |

---

### 4. Library / tool documentation

**`random.Random` (stdlib)**

- `build_rows` accepts optional `rng: random.Random | None`; defaults to `random.Random(config.seed)`.
- `Random(seed)` is isolated from global state; same seed → same sequence ([docs](https://docs.python.org/3/library/random.html#random.Random)).
- `choice(seq)` picks one element from a non-empty sequence.

**Why it matters:** Per-stop `rng.choice` once, reused across line items, keeps determinism and matches `test_deterministic_output_for_same_seed`.

**Pydantic v2 (`pydantic==2.13.4`)**

```211:215:backend/schemas/stop_config.py
class ConsolidationConfig(BaseModel):
    enabled: bool = True
    lines_per_customer: int = Field(gt=1, le=20)
```

No schema changes expected for SPEC-015.

**pytest patterns in repo**

- Consolidation groups asserted in strides of `lines_per_customer` (e.g. `for i in range(0, len(rows), 3)`).
- Column lookup via `header.index("Symbol")` / `header.index("Color")`.
- Allowlist checks: `assert row[symbol_idx] in SHAPE_VALUES`.
- Optional explicit RNG: `build_rows(..., rng=random.Random(base_config.seed))`.

**Suggested test shape for SPEC-015:**

```python
base_config.consolidation = ConsolidationConfig(enabled=True, lines_per_customer=3)
base_config.generate_shapes = True
base_config.generate_colors = True
# For each group of 3 rows: assert len({symbol}) == 1 and len({color}) == 1
# Optionally: two different groups may differ (AC2 — not required)
```

---

### 5. Files / areas (implementation guidance)

| Area | Action |
|------|--------|
| `backend/generators/stop.py` | Hoist `Symbol`/`Color` assignment to outer `for stop_index` loop |
| `tests/test_stop_generator.py` | Add consolidation + shapes/colors sharing test(s) |
| **NOT** wizard / schema / API | No UX or config changes per SPEC-015 scope |

**Pattern to mirror:** `eq_code` (lines 276–278, 298)—chosen once per stop, same value on every line item.

---

## Version caveats

- **Pydantic 2.13.4** — `ConsolidationConfig` constraints already enforced; no SPEC-015 schema work.
- **DirectRoute 26.x** — import smoke test referenced in SPEC-002 AC10; no version-specific Symbol/Color docs in repo.

---

## Fallback note

Public DirectRoute documentation for map marker rendering (beyond stop-file column names and internal allowlists) is **not available** in this environment. All Symbol/Color guidance is repo-internal (SPEC-011 handout → `SHAPE_VALUES`/`COLOR_VALUES`, golden template descriptions). Lane stayed useful because implementation contracts are fully specified in-repo.

[REDACTED]