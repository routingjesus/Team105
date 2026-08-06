## Prior-art lane result — SPEC-015

**Status:** `USEFUL`

**Summary:** External precedent consistently treats symbol/color as **entity-level (group-key) attributes** copied to child line-item rows, using entity pools, hash-bucket assignment, or parent-then-child propagation — with **no requirement for global uniqueness** across customers on maps.

---

### Findings

#### 1. Assign at parent/entity level, propagate to children (not per-row)

1. **Entity pools with sticky attributes**
   - **Source:** [Smelt Data Generation — Entity pools](https://smeltsql.com/guide/datagen/)
   - **Relevance:** Canonical synthetic-data pattern: create a fixed pool of entities; each event/row that references an entity inherits the same attribute values every time. Direct analogue to “pick symbol/color once per Customer ID, reuse on every consolidation line.”

2. **FK dereference / pure recomputation from parent key**
   - **Source:** [SeedFaker multi-table docs](https://github.com/opendsr-std/seedfaker/blob/main/docs/multi-table.md)
   - **Relevance:** Child rows derive parent attributes from `(seed, parent_row_index)` without a runtime lookup table. Same idea: given a customer key, recompute or look up the same symbol/color deterministically for every child row.

3. **Parent key stamped once, children inherit via normalization**
   - **Source:** [Informatica — Key Generation for Output Groups](https://docs.informatica.com/data-engineering/common-content-for-data-engineering/10-5-10/developer-transformation-guide/normalizer-transformation/key-generation-for-output-groups.html)
   - **Relevance:** ETL precedent for 1→N expansion: one source record produces multiple output rows that share a linking key. Consolidation line items should inherit visual markers the same way they inherit location/time-window fields.

4. **Subject table vs linked (child) table**
   - **Source:** [MOSTLY AI — synthetic subject/linked tables](https://mostly.ai/blog/how-to-generate-synthetic-data)
   - **Relevance:** Static per-entity attributes live on the subject; dynamic/repeated rows reference the subject ID. Symbol/color are static per customer — entity-level, not line-item-level.

5. **Relational integrity via dependency-ordered generation**
   - **Source:** [RelationalFaker](https://github.com/mstfdmrsln/relational-faker)
   - **Relevance:** Multi-table generators resolve parent-before-child order so FK-linked rows stay consistent. Supports “generate customer visuals once, then expand to N line items.”

---

#### 2. Group-keyed RNG assignment patterns

1. **Hash(group_key + salt) → bucket → pick from list** (A/B bucketing / “hashing trick”)
   - **Sources:** [Convert bucketing algorithm](https://docs.developers.convert.com/docs/bucketing-algorithm), [Bruin — deterministic A/B bucketing](https://getbruin.com/blog/deterministic-ab-test-bucketing/), [Depop engineering blog](https://engineering.depop.com/a-b-test-bucketing-using-hashing-475c4ce5d07), [arXiv 2212.08771](https://ar5iv.labs.arxiv.org/html/2212.08771)
   - **Relevance:** Industry-standard way to assign a stable pseudo-random choice per ID without storing state: `hash(customer_id + ":" + "symbol") % len(SHAPE_VALUES)`. Order-independent, no per-row RNG stream, reproducible across runs. Use **different salts** for symbol vs color so channels stay independent.

2. **In-memory Map: first encounter assigns, later rows copy**
   - **Source:** [Smelt entity pools](https://smeltsql.com/guide/datagen/) (implicit); common in procedural generators
   - **Relevance:** During `build_rows`, on first line for customer X assign and cache `{customerId → {symbol, color}}`; subsequent lines copy. Simple and readable when generation is single-threaded and sequential.

3. **Sticky fields in linked/correlated pools**
   - **Source:** [Smelt — linked_pools with `sticky`](https://smeltsql.com/guide/datagen/)
   - **Relevance:** When one logical unit emits multiple rows (`emit: 2`, `sticky: [device_id]`), shared fields stay constant across emitted rows. Same semantics as consolidation line items sharing a customer key.

4. **Per-field seed isolation**
   - **Source:** [SeedFaker determinism — `(seed, record_number, field_name)`](https://github.com/opendsr-std/seedfaker)
   - **Relevance:** Deriving values from `(global_seed, customer_key, field_name)` prevents adding/removing unrelated fields or rows from perturbing symbol/color for unrelated customers.

---

#### 3. Common pitfalls

1. **Per-row RNG / global stream consumption**
   - **Sources:** [Stack Overflow — row-level seed pitfalls](https://stackoverflow.com/questions/74759674/python-reproducible-random-number-using-a-row-level-seed), [fraiseql-seed #33 — PYTHONHASHSEED](https://github.com/fraiseql/fraiseql-seed/issues/33)
   - **Relevance:** Calling `random()` once per row without keying to customer ID guarantees mismatched symbols across consolidation lines. Global RNG + iteration-order sensitivity (dict/set order, parallel scheduling) can make “same seed, different output” even when logic looks correct.

2. **Group operations that depend on iteration order**
   - **Source:** [Polars #27307 — `.over()` ignores global seed](https://github.com/pola-rs/polars/issues/27307)
   - **Relevance:** “Pick once per group” implemented via stream-based group ops can be non-deterministic if group processing order varies. Hash-per-key or explicit cache keyed by customer ID avoids this.

3. **Off-by-one / wrong mode when consolidation is off**
   - **Relevance (external + SPEC-015 AC3):** With consolidation off there is effectively one row per customer; group-keyed and per-row assignment coincide. Pitfall is branching that still uses line-item index or row counter as the RNG input — harmless when N=1 but fragile if the code path is shared with N>1.

4. **Accidental coupling of independent visual channels**
   - **Sources:** [Cartography — visual variables](https://colorado.pressbooks.pub/makingmaps/chapter/chapter-4-visual-variables/), [ACM — separability of color × shape in symbol maps](https://doi.org/10.1145/3772318.3790287)
   - **Relevance:** Shape and color are **separable channels** (color×shape is among the best pairings). Pitfall: one combined draw (`hash(key) % (shapes×colors)`) or shared RNG draw ties them together. SPEC-014 (size) should stay independent if added later.

5. **Assuming global uniqueness**
   - **Relevance:** With 48 colors and 35 shapes, collisions across customers are expected at modest stop counts (birthday paradox). Treating uniqueness as a requirement leads to unnecessary dedup logic, exhaustion, or biased distributions. SPEC-015 correctly waives this.

6. **Confusing “same location” collision with “same color” collision**
   - **Source:** [Google Maps — marker collision behavior](https://developers.google.com/maps/documentation/javascript/advanced-markers/collision-behavior)
   - **Relevance:** Map SDKs manage **spatial overlap** (hide/show markers), not semantic uniqueness of color/symbol. Two customers at different coordinates with the same color is normal and acceptable.

---

#### 4. Is uniqueness across customers required for map markers?

**Generally no — external precedent treats it as optional, not required.**

1. **Categorical symbology allows duplicate classes**
   - **Sources:** [Esri — group unique values / unique types renderer](https://support.esri.com/en-us/knowledge-base/how-to-group-unique-values-from-multiple-attribute-fiel-000029178), [Esri Community — multivariate unique types](https://community.esri.com/t5/arcgis-online-questions/set-symbology-based-on-attributes-from-multiple/td-p/658785)
   - **Relevance:** GIS tools assign symbols per **category value**, not per unique (customer, symbol) pair globally. Many features can share a category/color; grouping is by attribute, not enforced distinctness.

2. **Spatial collision ≠ attribute collision**
   - **Source:** [Google Maps collision behavior](https://developers.google.com/maps/documentation/javascript/advanced-markers/collision-behavior)
   - **Relevance:** Overlap handling is about z-index and visibility at the same screen location, not enforcing unique colors per entity.

3. **Grouped-symbol tools expect duplicate colors within groups**
   - **Source:** [Datawrapper — group nearby symbols](https://www.datawrapper.de/academy/working-with-iteration-and-tolerance-feature-in-symbol-maps)
   - **Relevance:** When clustering, color is taken from “first symbol” or “most common value” — duplicate colors across entities are expected; the goal is **within-group consistency**, not global distinctness.

4. **Demo/test-data goal is within-entity consistency**
   - **Relevance:** For consolidation testing, the user story is “all lines for Customer A look alike” — not “every customer has a unique marker.” SPEC-015 AC2 aligns with industry practice.

---

### Trade-offs / caveats

| Approach | Pros | Cons |
|----------|------|------|
| **Hash(key + salt) % list** | Order-independent, no mutable state, easy to test | Must use stable string key; salt discipline for each channel |
| **Map cache on first row** | Simple in procedural Python/TS generators | Must key on correct identity; cache scope = single run |
| **Pre-pass: assign per customer, then expand** | Clear separation of “thin customers” vs “expand lines” | Two-phase logic; must not re-roll on expansion |
| **Global uniqueness enforcement** | Easier to tell customers apart visually | Biased sampling, complexity, not required for maps or SPEC-015 |

**Context-sensitive notes:**
- If the app later supports **re-generation of a subset of rows**, hash-per-key is more robust than row-order-dependent caches.
- If **run-level seed** must reproduce entire files byte-for-byte, avoid ambient global RNG; prefer keyed derivation (SeedFaker / hash-bucket style).
- **Customer identity key** must match whatever consolidation already uses (SPEC-015 scope: Store # / ID1) — mixing ID1 vs ID2 will break grouping.

---

### Recommendations for SPEC-015 (external precedent, not repo design)

1. **Treat symbol and color as entity-level attributes** on the consolidation group key; copy unchanged to every line-item row for that customer.
2. **Prefer group-keyed assignment** (hash-bucket or first-row cache) over per-row `random.choice`, especially when N > 1.
3. **Use independent salts per channel** (`"symbol"` vs `"color"`) so shape and color remain independently drawn when both are enabled.
4. **Do not require global uniqueness** across customers; uniform random from supported lists is sufficient.
5. **Guard the consolidation-off path explicitly** so SPEC-011 per-customer (effectively per-row) behavior is preserved without shared multi-row logic leaking in.
6. **Test matrix (industry-aligned):** same customer → identical symbol/color across N lines; different customers → may collide; consolidation off → unchanged from SPEC-011; shapes-only / colors-only / both / neither.

---

### Fallback note

Repo-specific implementation (e.g., exact `build_rows` structure, customer key field) was intentionally out of scope for this lane. External signal is strong and consistent across synthetic-data tooling, ETL 1→N patterns, hash-bucketing, and GIS symbology — no contradictory industry guidance found on uniqueness requirements.

[REDACTED]