## Lane result

**Status:** `USEFUL`  
**Summary:** Prior learnings strongly support SPEC-015 as a small `build_rows` loop change (hoist `rng.choice` for Symbol/Color to the per-stop scope), with consolidation-group test patterns and SPEC-011 allowlists as the main constraints.

**Fallback note:** Ledger has no consolidation/shape/color-specific entries; strongest signal is raw learnings from SPEC-011, SPEC-002, SPEC-005, and SPEC-006. No delta-refresh inputs were provided.

---

### Customer identity (code confirmation — for parent synthesis)

Consolidation grouping is keyed by the **outer `stop` / `SelectedStop`**, not `ID2`:

- `build_rows()` iterates `for stop_index, stop in enumerate(stops)`; the inner `for line in range(1, lines_per_customer + 1)` emits line items.
- Customer ID is `stop.id1`, written to the `"Store #"` column (`row_by_col["Store #"] = stop.id1`).
- `ID2` is unique per line item (`ORD-{stop_index+1:04d}-{line:02d}`).
- Existing consolidation tests group contiguous `lines_per_customer` rows and assert shared `Address`, `FixedTime`, and coordinates — same grouping SPEC-015 should use for Symbol/Color.

---

## Ranked prior-learning candidates

### Ledger (` .spec/_ledger/*.yaml`)

| Rank | Type | Summary | Source | Tags | Relevance to SPEC-015 |
|------|------|---------|--------|------|------------------------|
| 1 | `pattern_discovered` | Row-assembly fixes live in `build_rows()`’s `row_by_col` dict; passthrough bugs are fixed by reading source once and setting the key before the `COLUMN_ORDER` loop | `.spec/_ledger/directroute-file-formats.yaml` (SPEC-005) | `directroute`, `stop-file`, `row-assembly`, `passthrough-bug` | Symbol/Color assignment is already in `row_by_col` inside the inner line loop (~304–307). Fix is hoist `rng.choice` to per-stop scope, same surface as lat/long/Address sharing. |
| 2 | `pattern_discovered` | Stop-file headers are aliasable; `ID1` defaults to **"Store #"**; `build_rows()` always keys cells by canonical name (`"ID2"`, not aliased header) | `.spec/_ledger/directroute-file-formats.yaml` (SPEC-010) | `directroute`, `stop-file`, `aliasing` | Confirms **Store # / ID1** is the customer-identity column. Grouping should follow `stop.id1` / outer stop, not per-line `ID2`. |
| 3 | `constraint_found` | `location_db.xlsx` has whitespace-padded cells; normalize on load | `.spec/_ledger/directroute-file-formats.yaml` (SPEC-003) | `location-db`, `data-hygiene` | Low direct relevance; only matters if tests key off padded vs trimmed ID1 (unlikely). |

**Ledger gap:** No entries for consolidation, `lines_per_customer`, Symbol, Color, or `generate_shapes`/`generate_colors`.

---

### Raw (done specs’ `meta.yaml` learnings)

| Rank | Type | Summary | Source | Tags | Relevance to SPEC-015 |
|------|------|---------|--------|------|------------------------|
| 1 | `gap_found` | Authoritative DirectRoute Symbol/Color allowlists (35 shapes, 48 colors) swapped into `SHAPE_VALUES` / `COLOR_VALUES` in `stop_config.py` | SPEC-011 `meta.yaml` | `directroute`, `stop-file`, `shape`, `color` | AC still requires allowlist-only values. No schema change; reuse existing constants and per-row `rng.choice` source. |
| 2 | `pattern_discovered` | `generate_shapes` / `generate_colors` are plain `bool` on `StopConfig` (not nested config); `build_rows` uses two `if` blocks; `ConsolidationConfig` exists because it needs `lines_per_customer` | SPEC-011 `meta.yaml` | `directroute`, `stop-file`, `api-design` | Direct implementation map: extend the two `if` blocks so choice runs once per stop when consolidation is on. No new config type for SPEC-015. |
| 3 | `pattern_discovered` | Consolidation line items should share per-stop fields; existing tests assert one `Address` / `FixedTime` / coordinates per `lines_per_customer` group | SPEC-005 `meta.yaml` + `tests/test_stop_generator.py` (SPEC-002 design) | `stop-generator`, `testing`, `location_db` | Precedent for “shared across line items, unique per customer.” Symbol/Color should mirror Address/FixedTime/coords, not independent per line. |
| 4 | `pattern_discovered` | Subset-membership tests on stochastic output are a recurring false-green pattern; assert **specific expected values** (e.g. `0.5` present), not just `value ∈ allowlist` | SPEC-006 `meta.yaml` | `testing`, `stop-generator`, `regression-proofing` | Current SPEC-011 tests only check `row[symbol_idx] in SHAPE_VALUES` per row — they would pass if each line differed. SPEC-015 needs within-group equality assertions on consolidation groups (and inequality across customers optional). |
| 5 | `pattern_discovered` | `rng.choice()` silently narrowing the achievable set is a known failure mode; strict-subset cases must reject or be explicit | SPEC-006 `meta.yaml` | `validation`, `silent-failure`, `stop-generator` | Less central than grouping, but reinforces: per-stop Symbol/Color should be chosen once outside the line loop, not re-drawn per line. |
| 6 | `decision_made` | Density thinning at **customer** level before consolidation expansion; consolidation = N rows with unique ID2, shared location/time-window fields | SPEC-002 `meta.yaml` / `spec.md` | `directroute-file-formats` | Defines consolidation semantics: one physical stop → N line items. SPEC-015 extends “shared fields” to Symbol/Color without changing row count or thinning. |
| 7 | `constraint_found` | (Historical) No in-repo DirectRoute enum; proceeded with placeholder then swapped allowlists | SPEC-011 `meta.yaml` | `research-gap` | Superseded by rank-1 raw finding; keep for context that allowlist location is `stop_config.py`, not wizard/UI. |
| 8 | `gap_found` | Pre-existing tests can encode wrong behavior as expected output; integration tests must cover the exact reproduction scope | SPEC-007 `meta.yaml` | `self-review`, `testing` | When adding consolidation + shapes/colors tests, cover `consolidation.enabled` + `generate_shapes`/`generate_colors` together at `build_rows` level, not allowlist-only per-row checks. |

**Lower relevance (not carry-forward unless scope expands):** SPEC-008 shared-code-path split (`_volume_cells`), SPEC-009 distribution testing, SPEC-010 ID2/ID3 aliasing UX, environment/frontend ledger entries.

**No prior learnings for:** SPEC-014 (draft, not `done`); exact “match Symbol/Color per customer across consolidation lines” — this is new behavior atop SPEC-011.

---

## Carry-forward candidates (for user curation)

1. **[raw] SPEC-011 allowlists** — Use `SHAPE_VALUES` / `COLOR_VALUES`; no new enum research.
2. **[raw] SPEC-011 bool toggles + `build_rows` `if` blocks** — Minimal change surface; no new `StopConfig` wrapper.
3. **[raw] SPEC-002/005 consolidation shared-field precedent** — Hoist Symbol/Color to per-stop scope like Address/FixedTime/coords.
4. **[raw] SPEC-006 testing philosophy** — Add consolidation-group equality tests; per-row allowlist checks are insufficient.
5. **[ledger] `build_rows` / `row_by_col` passthrough pattern** — Fix belongs in the inner loop structure, not header/schema.
6. **[ledger] Store # = ID1 = customer identity** — Group by outer `stop`, not `ID2`.

---

## Suggested implementation hint (from learnings, not synthesis)

```python
# Per stop (before line loop):
symbol = rng.choice(SHAPE_VALUES) if config.generate_shapes else None
color = rng.choice(COLOR_VALUES) if config.generate_colors else None
# Per line (inside loop):
if symbol is not None: row_by_col["Symbol"] = symbol
if color is not None: row_by_col["Color"] = color
```

Consolidation off (`lines_per_customer == 1`): behavior unchanged vs SPEC-011. SPEC-014 (Size) can stay independent unless product ties Size to Symbol/Color.

[REDACTED]