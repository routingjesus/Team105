# DRProject.config golden fixture

Owner-supplied DirectRoute project configuration template, sanitized for
bundling in the repo. Used by SPEC-012's generator parity tests and as the
base template the backend substitutes wizard answers into.

## Provenance

Sourced from a working DirectRoute 26.x project config (owner-supplied,
2026-08-05). Sanitized before commit:

- Machine-specific paths (`RecentFilesList`, `RecentProjectsList`,
  `DistanceFile`, `MergeDirectoryAndFileSettings`) cleared to empty elements
- `DRTrack` credentials cleared
- `Configuration/Stop` identity fields reset to stop-file generator defaults
  (`Store #`, `ID2`, `ID3`, `Name`, `Address2`, etc.)
- `Quantities` reset to a single `Cube` entry (minimum DirectRoute volume)

## Structure (high level)

```
AppSettings
├── Configuration          ← wizard-driven field mappings (SPEC-012 substitutes here)
│   ├── Stop               ← ID1/ID2/ID3/Name/Address aliases, Quantities
│   └── Truck              ← truck user fields (passthrough)
├── Preferences            ← DirectRoute prefs (passthrough; paths sanitized)
├── CMP / TerritoryPro / ResourcePro / RouteAssist  (passthrough)
```

## Generator substitution map

The backend generator (`backend/generators/drproject_config.py`) loads this
file and overrides only the elements listed below; everything else is passed
through verbatim from the template.

| XML path | Wizard source | Default (no alias) |
|----------|---------------|-------------------|
| `Configuration/Stop/ID1` | `aliases.id1` | `Store #` |
| `Configuration/Stop/ID2` | `aliases.id2` | `ID2` |
| `Configuration/Stop/ID3` | `aliases.id3` | `ID3` |
| `Configuration/Stop/Name` | `aliases.name` | `Name` |
| `Configuration/Stop/Address2` | `aliases.address_2` | `Address2` |
| `Configuration/Stop/Contact` | `aliases.contact` | `Contact` |
| `Configuration/Stop/Phone` | `aliases.phone` | `Phone` |
| `Configuration/Stop/Address` | fixed | `Address` |
| `Configuration/Stop/Quantities` | `volumes[].name` | one `Cube` quantity |

Path elements under `Preferences` that held local filesystem paths are
always emitted empty regardless of wizard input.

## Testing

- Structural parity: generated XML element tree matches this template for all
  non-substituted nodes
- Substitution: alias and volume names from a `StopConfig` request appear in
  the corresponding `Configuration/Stop` elements
- Compare as parsed XML trees (not raw bytes) — DirectRoute may normalize
  whitespace; byte parity is not required for preference blobs
