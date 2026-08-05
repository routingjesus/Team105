---
id: SPEC-009
title: "Time window generation under-weights realistic business hours"
category: bug
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

Generated stop time windows have decent variance in absolute terms, but the
distribution across that variance isn't realistic: too many stops end up
with windows open after 1700, when in reality few real-world stops are open
that late. The generator should bias the distribution so most stops fall
within 0500–1600, with a small tail after 1700.

## Acceptance criteria

1. Across a representative generated batch, the majority (target
   percentage to be confirmed during research, e.g. ~80-90%) of stop time
   windows fall within 0500–1600.
2. Only a small minority of generated stop time windows extend past 1700.
3. A test generates a large batch of stops and asserts the proportion of
   windows within 0500–1600 versus after 1700 meets the target distribution.

## Reproduction

- **Input:** Generate a stop file with default/typical time-window settings.
- **Actual output:** A disproportionate share of stops have windows open
  after 1700.
- **Expected output:** Most stops have windows between 0500 and 1600; few
  extend past 1700.
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

- The random-window branch of `build_time_window()`
  (`backend/generators/stop.py`) draws `open_minutes` uniformly across
  almost the entire day (`rng.randint(0, latest_open_minutes)`, where
  `latest_open_minutes` is close to `23:59 - fixed_time`). A uniform draw
  over the full day puts roughly half of all opens in the afternoon or
  evening, which is why so many generated windows end up closing after
  1700 — there is no bias toward realistic business hours anywhere in the
  function (repo-analyst).
- `close_minutes` is then `open_minutes + fixed_time + rng.randint(0, 180)`
  (capped at day end). This up-to-3-hour jitter on top of an already
  late-skewed open compounds the problem: even opens drawn near midday can
  jitter well past 1700 (repo-analyst).
- `fixed_time_minutes` (`FixedTime`, from `StopConfig`) is a required,
  caller-supplied, unbounded-above `float` (`backend/schemas/stop_config.py`).
  Test fixtures use small values (15 min), but the fix must not assume a
  small fixed time — the business-hours bound has to shrink gracefully as
  `fixed_time` grows, matching the existing pattern of clamping against
  `latest_open_minutes` (repo-analyst).
- `validate_time_window()` is the only invariant asserted today (width
  `>= fixed_time_minutes`, `0 <= open1 <= close1 <= 2359`); it says
  nothing about *where in the day* the window falls, so a distribution fix
  is additive and can't violate this existing assertion in
  `build_time_window()` (repo-analyst).
- `mode="randomized"` (not `"random"`) is the config value that reaches
  the `else` branch of `build_time_window()`; the `mode="fixed"` branch is
  untouched by this bug and must keep returning exactly the caller's
  `open1`/`close1` (existing test:
  `test_fixed_mode_returns_configured_window_for_every_call`) (repo-analyst).
- No prior spec or ledger entry addresses time-window distribution;
  SPEC-001/002/005's learnings are about column passthrough, not
  randomization shape, so there is no existing pattern to reuse beyond
  `build_time_window()`'s own minute-based arithmetic (learnings-curator:
  no directly relevant prior learnings found).
- Chosen approach: keep the existing minutes-based arithmetic but split
  the random branch into two weighted paths — a "business hours" path
  (high probability) that draws `open_minutes` within a 0500–1600 band
  (clamped by `latest_open_minutes` and by `fixed_time` so the window
  still satisfies `validate_time_window`) with a jitter cap that mostly
  keeps `close_minutes` inside the same band, and a small-probability
  "evening tail" path that draws `open_minutes` later in the day, which is
  what's allowed to close past 1700. This is a targeted redistribution of
  the same `rng` calls already in use, not a new randomization framework
  (prior-art: business-hours generators typically use a bounded "core
  hours" band plus a low-probability long-tail rather than a normal/Gaussian
  distribution, which avoids pulling in a new dependency for this repo's
  stdlib-`random`-only generator).

## Scope boundaries

- Does not change the user-facing time-window inputs in the wizard, only
  the underlying generation distribution for `mode="randomized"`.
- Does not change `mode="fixed"` behavior — callers supplying explicit
  `open1`/`close1` are unaffected.
- Target split: at least ~80% of generated randomized windows open and
  close within 0500–1600, and no more than ~15% close after 1700. Exact
  bucketing (e.g. "within 0500-1600" defined as `open1 >= 500 and
  close1 <= 1600`) is decided by the fix, not user-configurable.
- Does not introduce a new probability distribution dependency (e.g.
  numpy) — implemented with stdlib `random.Random`, consistent with the
  rest of the generator.

## Error evidence

Not applicable — this is a distributional/statistical defect, not a crash
or exception. No stack trace; the defect is only visible by aggregating
many generated rows and observing the skew.

## Root cause analysis

`build_time_window()`'s randomized branch draws `open_minutes` uniformly
across nearly the full day (`rng.randint(0, latest_open_minutes)`) with no
bias toward typical business hours, then adds up to 180 minutes of close
jitter on top. Because a uniform draw over ~24 hours puts about half of
all opens after noon, and the jitter can push close another 3 hours later,
a large share of generated windows close after 1700 even though real-world
stops are rarely open that late. The fix should replace the single
full-day uniform draw with a weighted choice between a bounded
"business-hours" band (majority of cases) and a bounded "evening tail"
band (minority of cases), so the aggregate distribution matches realistic
stop hours.

## Blast radius

- `build_time_window()` is called only from `build_rows()`
  (`backend/generators/stop.py`), which is called only from
  `generate_stop_file()`. No other generator (e.g.
  `backend/generators/truck.py`) shares this function.
- Changing the randomized branch changes generated output for any caller
  using `mode="randomized"` with a fixed `seed` — existing golden/snapshot
  tests that pin exact `open1`/`close1` values under `mode="randomized"`
  with a specific seed would need updating; a scan of
  `tests/test_stop_generator.py` shows the only randomized-mode assertion
  today (`test_randomized_mode_always_satisfies_fixed_time_constraint`)
  checks the `validate_time_window` invariant generically rather than
  pinning exact values, so no existing test is expected to break.
- Blast radius classification: **isolated** — single function, single
  file, no shared state, no API/schema shape change (`TimeWindowConfig`
  itself is untouched).

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — rewrite the randomized branch of
    `build_time_window()` to weight `open_minutes` toward a 0500–1600
    band with a small-probability late tail, keeping the existing
    `validate_time_window` assertion and the `mode="fixed"` branch
    untouched.
  - `tests/test_stop_generator.py` — add a statistical regression test
    generating a large batch (e.g. 2000+ draws) of randomized windows and
    asserting the majority fall within 0500–1600 and only a small
    minority close after 1700.
- **Files NOT to modify:**
  - `backend/schemas/stop_config.py` — `TimeWindowConfig` and
    `validate_time_window()` stay as-is; this is a generation-distribution
    fix, not a schema change.
  - `backend/generators/truck.py` — unrelated generator, no time-window
    logic.
- **Patterns to follow:**
  - Keep the minutes-of-day integer arithmetic and HHMM conversion
    (`(minutes // 60) * 100 + minutes % 60`) already used in
    `build_time_window()` — do not introduce `datetime`/`time` objects.
  - Continue deriving all randomness from the passed-in `rng: random.Random`
    (never module-level `random`), matching every other generator function
    in this file.
  - Keep the final `assert validate_time_window(...)` in place as a
    correctness backstop for the new branch, exactly as it guards the
    current implementation.
- **Test expectations:**
  - Existing tests (`test_randomized_mode_always_satisfies_fixed_time_constraint`,
    `test_fixed_mode_returns_configured_window_for_every_call`,
    `test_midnight_open1_renders_zero_padded_not_falsy_blank`) must keep
    passing unmodified.
  - New test asserts, over a large seeded batch, that the proportion of
    `mode="randomized"` windows with `open1 >= 500 and close1 <= 1600` is
    a clear majority (e.g. `>= 0.75`) and the proportion with
    `close1 > 1700` is a small minority (e.g. `<= 0.20`), giving margin
    around the ~80/15 target so the test isn't flaky against a single
    seed's sampling noise.
