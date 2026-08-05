## Lane result

- **Status**: `USEFUL`
- **Summary**: Symbol/Color are chosen inside the per-line loop with independent `rng.choice`; consolidation groups by outer-loop `SelectedStop` (Store # / ID1), so SPEC-015 should hoist assignment to the per-stop scope like `eq_code` and `volume_cells`.

---

## Answers to research questions

### 1. Exact current code path (Symbol/Color in `lines_per_customer` loop)

**Function**: `build_rows` in `backend/generators/stop.py`

**Flow**:
1. `lines_per_customer` set at **270–272** (default 1; from `config.consolidation.lines_per_customer` when enabled).
2. **Outer loop** `for stop_index, stop in enumerate(stops)` at **275** — one `SelectedStop` per thinned location-db row.
3. Per-stop values computed **before** line expansion: `frequency` (276), `build_time_window` (277), `eq_code` (278), `_volume_cells` (279).
4. **Inner loop** `for line in range(1, lines_per_customer + 1)` at **281** — consolidation line items.
5. **Symbol/Color assigned inside inner loop** at **304–307**:

```304:307:backend/generators/stop.py
            if config.generate_shapes:
                row_by_col["Symbol"] = rng.choice(SHAPE_VALUES)
            if config.generate_colors:
                row_by_col["Color"] = rng.choice(COLOR_VALUES)
```

**Call chain**: `generate_stop_file` (**334–338**) → `build_rows(config, candidates, rng)` with `random.Random(config.seed)`.

**Allowlists**: `SHAPE_VALUES` / `COLOR_VALUES` in `backend/schemas/stop_config.py` (**28–115**).

---

### 2. Customer identity key — how consolidation groups lines

**Grouping mechanism**: structural — the **outer loop over `stops`** (`selected_stops_from_candidates(candidates)` at **264**), not a post-hoc group-by on output rows.

Each `SelectedStop` (**182–197**) maps to one physical customer location after thinning. Consolidation emits N rows from the same `stop` object in the inner loop.

**Store # / ID1** is the customer identifier **column**:
- `SelectedStop.id1` populated from location_db `ID1`, falling back to `Name` (**216** in `selected_stops_from_candidates`).
- Written to output as `"Store #": stop.id1` (**287**).
- Header alias: `COLUMN_ORDER` `"Store #"` ↔ `ALIAS_FIELD_MAP["ID1"]` (**68**, **120–124** in `stop_config.py`).

**ID2** is **per line item** (order number): `ORD-{stop_index+1:04d}-{line:02d}` (**282**) — unique within a consolidation group; **not** the customer identity key.

**Evidence from consolidation tests**: groups share `Address` and `FixedTime` but have unique `ID2` (`tests/test_stop_generator.py` **381–398**). Coordinates shared across line items (**501–514**).

**Inference**: “Customer ID” in SPEC-015 means **Store # (ID1) / physical stop**, not ID2. Implementation should key off the outer-loop `stop`, not re-read Store # from rows.

**Terminology note**: SPEC-010 test aliases ID2 as `"Customer ID"` (**103–104** in tests) — domain naming is inconsistent; consolidation semantics use ID1/Store # for customer, ID2 for orders.

---

### 3. `ConsolidationConfig` shape and `lines_per_customer` determination

**Schema** (`backend/schemas/stop_config.py` **211–216**):

```211:216:backend/schemas/stop_config.py
class ConsolidationConfig(BaseModel):
    """Optional multi-line-item consolidation testing."""

    enabled: bool = True
    lines_per_customer: int = Field(gt=1, le=20)
```

**On `StopConfig`**: `consolidation: ConsolidationConfig | None = None` (**253**).

**Generator logic** (`backend/generators/stop.py` **270–272**):
- `consolidation is None` or `enabled=False` → `lines_per_customer = 1`
- `enabled=True` → `lines_per_customer = config.consolidation.lines_per_customer`

**API row count** (`backend/main.py` **120–125**): `output_row_count = len(candidates) * lines_per_customer`.

**Wizard → API** (`lib/build-config.ts` **92–95**): sends consolidation only when `consolidationEnabled && linesPerCustomer != null`.

**Frontend mirror** (`lib/wizard-types.ts` **98–100**, `lib/wizard-schema.ts` **86–87**, defaults **295–296**): `linesPerCustomer` default 3, min 2, max 20 in UI.

---

### 4. Existing SPEC-011 / consolidation tests and patterns to extend

**SPEC-011 shape/color tests** — `TestBuildRows` in `tests/test_stop_generator.py`:
| Test | Lines | What it asserts |
|------|-------|-----------------|
| `test_shapes_and_colors_blank_by_default` | 419–427 | Symbol/Color empty |
| `test_shapes_generated_from_allowlist_when_enabled` | 429–438 | Symbol ∈ allowlist; Color blank |
| `test_colors_generated_from_allowlist_when_enabled` | 440–449 | Color ∈ allowlist; Symbol blank |
| `test_shapes_and_colors_both_generated_when_both_enabled` | 451–461 | Both ∈ allowlists **per row** (no consolidation) |

**Consolidation tests** (no shape/color today):
| Test | Lines | Pattern to reuse |
|------|-------|------------------|
| `test_consolidation_creates_n_rows_per_customer_with_unique_id2` | 381–398 | Stride grouping `rows[i:i+3]`; shared Address/FixedTime |
| `test_consolidation_shares_coordinates_across_line_items` | 501–514 | Same stride; shared lon/lat |
| `test_id2_id3_aliases_do_not_change_row_values` | 116–132 | Consolidation + alias regression |

**Pattern to follow for per-stop shared fields** (already in `build_rows`):
- `eq_code` (**278**) — one value per `stop_index`, reused on all lines
- `volume_cells` (**279**) — one draw per stop, all lines share
- `frequency`, time window (**276–277**) — per stop, all lines share

**Suggested new test**: consolidation + `generate_shapes`/`generate_colors` → within each stride group, single Symbol and single Color; optionally assert different groups *may* differ (not required to be unique).

**Frontend test mirror**: `lib/build-config.test.ts` **77–80**, **90–96**, **147–151** — no SPEC-015 changes unless API shape changes (not expected).

---

### 5. Frontend/wizard involvement

**No UI changes needed** for matching behavior.

SPEC-015 scope: *“Does not change how many line items are generated or consolidation config UX.”*

Existing controls (`components/wizard/stop-questions.tsx` **280–317**):
- Consolidation: `consolidationEnabled` + `linesPerCustomer`
- Shapes/colors: `generateShapes` + `generateColors`

Matching is **automatic backend behavior** when both consolidation and shape/color flags are on. Wiring already complete via `lib/build-config.ts`, `lib/wizard-schema.ts`, `lib/api.ts`.

---

### 6. Coupling with SPEC-014 (Size) — hard dependency or independent?

**Independent** — no hard coupling.

| Spec | Change | Trigger |
|------|--------|---------|
| SPEC-014 | `Size = "28"` on every row | `generate_shapes` OR `generate_colors` |
| SPEC-015 | Shared Symbol/Color per stop | consolidation enabled AND shape/color enabled |

Both touch `build_rows` near **281–307**, but:
- SPEC-014 is static, unconditional per row when flags on
- SPEC-015 only changes **when** Symbol/Color are picked (per stop vs per line)
- SPEC-014 explicitly: *“existing Symbol/Color behavior from SPEC-011 is unchanged”*
- SPEC-015 scope: *“Does not address Size (see SPEC-014)”*

Can ship separately; merge order only affects line proximity in one function.

**Current Size**: in `COLUMN_ORDER` (**47**) but never set in `row_by_col` — always blank (same gap SPEC-014 fixes).

---

### 7. Files likely affected vs NOT to modify

**Likely affected**:
| Path | Why |
|------|-----|
| `backend/generators/stop.py` | Hoist Symbol/Color before inner loop (or assign once, reuse in loop) |
| `tests/test_stop_generator.py` | New consolidation + shape/color tests; optional regression for consolidation-off |

**NOT to modify** (for SPEC-015):
| Path | Why |
|------|-----|
| `backend/schemas/stop_config.py` | No new config fields |
| `backend/main.py` | Row-count math unchanged |
| `components/wizard/stop-questions.tsx` | No UX change |
| `lib/wizard-schema.ts`, `lib/wizard-types.ts`, `lib/build-config.ts`, `lib/api.ts` | Existing flags sufficient |
| `lib/build-config.test.ts` | Unless schema changes |
| `backend/generators/truck.py` | Out of scope (SPEC-011 precedent) |
| `fixtures/stop/TEMPLATE_*.xls` | Read-only golden reference |
| `backend/services/spatial.py` | Thinning already at customer level |

---

### 8. Related done / in-progress specs

| Spec | Status | Relevance |
|------|--------|-----------|
| **SPEC-011** | `done` | Shape/color generation, allowlists, wizard toggles, `build_rows` assignment — direct upstream |
| **SPEC-002** | `done` | Consolidation feature origin, AC8 (N rows, unique ID2), thin-before-expand |
| **SPEC-005** | `done` | Consolidation lines share lat/long (mirror for Symbol/Color) |
| **SPEC-010** | `done` | ID2/ID3 aliases; ID2 ≠ customer ID |
| **SPEC-014** | `research` | Sibling — static Size=28 when shapes/colors on; independent |
| **SPEC-015** | `research` | This spec |
| **SPEC-016** | `research` | Stops CSV download — unrelated surface |

---

## Patterns to follow

- **Per-stop shared fields before line loop**: `backend/generators/stop.py` **276–279** (`eq_code`, `volume_cells`, time window).
- **Consolidation grouping tests**: `tests/test_stop_generator.py` **381–398**, **501–514** (stride-based groups).
- **SPEC-011 enable-flag pattern**: boolean flags on `StopConfig`, no nested config (`SPEC-011` meta learnings).

---

## Open questions / risks

1. **Duplicate ID1 across different stops**: grouping is per `SelectedStop` iteration, not global ID1 uniqueness — aligns with spec (“different customers may differ”) but duplicate Store # values across stops would get different symbols (edge case).
2. **“Customer ID” naming**: UI/spec may mean ID1/Store #; ID2 is order ID in consolidation — document in implementation guidance.
3. **Determinism**: moving `rng.choice` before inner loop preserves seed stability; extra RNG draws per stop vs per line could shift downstream random fields if order changes — hoist picks without changing other RNG call order.

---

## Findings (structured)

1. Symbol/Color assigned per line inside inner loop  
   - **Evidence**: `backend/generators/stop.py` **304–307**  
   - **Why it matters**: root cause of SPEC-015 bug

2. Consolidation groups by outer-loop `SelectedStop`, not ID2  
   - **Evidence**: `backend/generators/stop.py` **275–282**, **287**; `tests/test_stop_generator.py` **391–396**  
   - **Why it matters**: fix scope is per-stop, not row group-by

3. Store # = ID1 from location_db (Name fallback)  
   - **Evidence**: `backend/generators/stop.py` **216**, **287**; `stop_config.py` **68**, **124**  
   - **Why it matters**: confirms customer identity column for AC wording

4. No API/schema/UI extension required  
   - **Evidence**: SPEC-015 scope; existing wizard fields in `stop-questions.tsx` **280–317**  
   - **Why it matters**: backend-only implementation

5. SPEC-014 independent sibling  
   - **Evidence**: `.spec/SPEC-014-static-size-28-with-shape-color/spec.md` AC3; SPEC-015 scope boundaries  
   - **Why it matters**: parallel PRs possible on same file with care

[REDACTED]