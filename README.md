# Print Check

Nurb's **13 existing printability checks**, extracted into a standalone Python CLI,
Python API, and portable AI skill. No CAD app, AI provider, server, or account required.

**Exact CAD solids only. No STL/OBJ/mesh fallback.** Export STEP/BREP from your CAD
pipeline, or supply a build123d `Shape` directly. Coordinates and thresholds are mm.
Do not turn a triangle mesh into a faceted BREP and treat that as equivalent to the
original analytic CAD solid.

## Install

Python 3.11–3.13 recommended; OCCT/build123d wheels must exist for your platform.

```sh
git clone https://github.com/dctanner/print-check.git
cd print-check
uv tool install --python 3.12 .
# Or: python -m pip install .
print-check --version
```

If your tool directory is not on PATH, use `~/.local/bin/print-check` (typical uv
Linux installation), or add that directory to your shell's PATH.

## CLI

```sh
print-check printers
print-check rules
print-check check bracket.step --printer bambu_a1_mini
print-check check part.brep --bed 180 180 180 --material petg --min-wall 1.2
print-check check a.step b.step --format json --output report.json --fail-on warn
print-check check bracket.step --up 0 0 -1 --only overhang,stability
print-check check examples/box.py --allow-python
```

Python input **executes arbitrary code** and is never sandboxed. Inspect/trust the
file before using `--allow-python`. It must define `build()` returning a build123d
`Shape`, or a `Shape` named `part`; no parameters are passed automatically.
Model stdout goes to stderr to keep JSON stdout parseable.

Exit codes: **0** = below the requested finding threshold, **1** = threshold reached,
**2** = input/configuration/runtime error. Default threshold is `fail`; use
`--fail-on warn` for warnings too. `--fail-on never` never hides execution errors.
A zero exit does not necessarily mean zero findings. JSON reports include the
effective context, requested rule coverage, findings, positions, and limitations.
Multiple inputs are processed independently, including after an input error.

### Configuration

Configuration is explicit, not auto-discovered. Nurb's global/project config and
part cards are not read or modified.

```toml
# print-check.toml
printer = "bambu_a1_mini"

[context]
material = "petg"
min_wall = 1.2
up = [0, 0, 1]
bridge_limit = 30
```

```sh
print-check check bracket.step --config print-check.toml
```

Precedence: upstream defaults → selected printer profile → `[context]` → CLI
context flags. `--printer` overrides the named profile, not explicit context
overrides. With no profile/bed supplied, the upstream **256 × 256 × 256 mm** default
applies. Confirm the real printer instead of assuming that default is appropriate.
`[context.accepted] sliver = N` retains upstream's accepted-sliver baseline; only
use it with a documented justification, not to make a report green.

## Python API

```python
from build123d import Box
from print_check import check
from print_check.checks import Context

findings = check(Box(20, 20, 20), Context(bed=(180, 180, 180)))
for finding in findings:
    print(finding)
```

`check()` validates context/shape and returns upstream `Finding` objects.
`print_check.checks.run()` is also retained for upstream-compatible low-level use.
The CLI/API wrapper rejects unknown rule names; the low-level runner retains
upstream selection behavior.

## AI skill / Jelly / Pi

```sh
print-check install-skill --project /path/to/project
```

This writes `.pi/skills/print-check/SKILL.md` and adds an idempotent, marked section
to `AGENTS.md`, preserving other instructions. The skill contains the installed
CLI's path, so agents need not depend on shell PATH.

Pi discovers the skill on startup in a trusted project; its description is loaded
by default and its full instructions are read when relevant. `AGENTS.md` additionally
requires agents to read it before CAD/printing work. Start a new Jelly agent session
in that project (or `/reload` in Pi) after installation; this does not hot-patch
already-running agents. It does not force print checks during unrelated work.

For another Agent Skills-compatible tool, copy `skills/print-check/` to its skill
directory and install the CLI separately. This repository also has a Pi package
manifest for `pi install --local /path/to/print-check`; that installs skill discovery
only, not Python dependencies or the default `AGENTS.md` instruction.

## Preserved checks

| Rule | Checks |
|---|---|
| `solids` | Missing solid or disconnected bodies |
| `overhang` | Unsupported slopes, excluding supported short bridges/ledges |
| `floating` | Regions starting in air |
| `hole_ceiling` | Pierced ceilings over downward-facing pockets |
| `min_wall` | Sampled local wall sections |
| `sliver` | Tiny faces beyond an accepted count |
| `concave_cosmetic` | Cosmetic chamfers inside concave junctions |
| `bed_bevel` | Chamfers compromising first-layer contact |
| `warp_risk` | Large sharp-cornered first layers and material shrink |
| `pin` | Thin free-standing vertical pins |
| `stability` | Bed footprint/centre of mass and narrow-facet leverage |
| `projection_ratio` | Cantilever reach/height (requires `forward`) |
| `build_volume` | Printer fit, including upstream orientation search |

The rules, severities, thresholds, messages, and geometric heuristics are preserved.
This is **not a slicer or a print-success guarantee**. Curved faces/wall thickness are
sampled. A clear report means *no problems found by the selected rules*. Bed contact
is relative to the part's lowest point. Build-volume search may find a different
orientation than the supplied `up`; other checks still use that `up`. Check individual
print parts, not an assembled scene. No collision/motion engine is included.

## Development

```sh
uv sync --extra dev --python 3.12
uv run pytest -q
uv build
```

Includes standalone upstream rule/convexity regression tests and CLI integration
tests. Upstream cases requiring Nurb's out-of-scope CAD authoring helpers are listed
in `tests/upstream-excluded.txt`; they are not claimed as tested here.

`ci/github-actions.yml` is an optional Python 3.11/3.12/3.13 GitHub Actions template.
It is not active: copy it to `.github/workflows/tests.yml` using a credential with
workflow-write permission to enable CI. Local tests do not imply hosted CI ran.

## Origin and license

Extracted from [Shpigford/nurb](https://github.com/Shpigford/nurb), commit
`39452e686f6b3825de836f69b9752a0a262ab555`.
Copyright 2026 Ordinary Systems LLC. Not affiliated with or endorsed by Nurb.

**FSL-1.1-MIT, not MIT-only and not currently OSI open source.** Redistribution
must retain the license; competing commercial products/services are restricted.
The upstream future MIT grant takes effect on the second anniversary of the
relevant upstream version's availability, not when this extraction is published.
See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md) for provenance and modifications.
