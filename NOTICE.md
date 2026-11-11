# Attribution and extraction record

Source: https://github.com/Shpigford/nurb

Pinned source commit: `39452e686f6b3825de836f69b9752a0a262ab555`
(upstream commit timestamp: 2026-11-09T13:29:10-06:00).

Original copyright: **Copyright 2026 Ordinary Systems LLC**.
The original **Functional Source License, Version 1.1, MIT Future License**
is reproduced unmodified in `LICENSE` and applies to this derivative.
New toolkit glue is distributed under the same terms.

## Copied/adapted source

- `engine/src/nurb/checks.py` → `src/print_check/checks.py`
- `engine/src/nurb/printers.toml` → `src/print_check/printers.toml`
- `engine/tests/test_rules.py` → `tests/test_upstream_rules.py` (standalone cases)
- `engine/tests/test_convexity.py` → `tests/test_upstream_convexity.py`

All 13 decorated rule implementations are unchanged from the pinned source.
Their geometry helpers are retained except the mesh adapter described below.
`Context`, `Finding`, severity labels, constants, defaults, and accepted-sliver
behavior are preserved.

## Extraction changes

- Nurb's assembly sweep dispatch is replaced by an explicit unsupported-assembly
  error. Individual print parts remain the unit of checking.
- The rotated-bed-fit helper uses build123d's native tessellation at the same
  0.1 mm tolerance rather than Nurb's application builder/render mesh pipeline.
- Removed Nurb's global printer preference writers, project/card resolution,
  and card-variant machinery. Added explicit standalone TOML/CLI configuration.
- Added validated Python API, STEP/BREP/trusted-Python input adapters, JSON/text
  reports, exit policies, local skill installer, packaging, and an optional CI template.
- Adapted upstream test imports. Tests requiring Nurb's `stand`, polish, holes,
  and related CAD authoring helpers are omitted; exact names are recorded in
  `tests/upstream-excluded.txt`.

This distribution does not include Nurb's application, agent/server integrations,
CAD authoring toolkit, viewer, slicer, or motion engine. It contains no mesh-input
approximation of the original checks. Brand/profile names identify compatible
machines; they do not imply affiliation.
