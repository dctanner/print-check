---
name: print-check
description: Run Nurb's 13 exact-solid printability checks before reviewing or exporting 3D-printable CAD parts. Use for STEP/BREP or build123d solids, overhangs, thin walls, bed fit, floating regions, pins, first-layer grip, and print-readiness review. STL and triangle meshes are unsupported.
license: FSL-1.1-MIT
compatibility: Python 3.11+ with print-check-toolkit installed; build123d/OCCT wheels required.
---

# Standalone Print Check

Use the existing Nurb checks, not a new mesh approximation. This is a preflight,
not a slicer, mechanical safety test, or guarantee of print success.

## Workflow

1. Identify the **individual printable part**, its intended build orientation,
   millimetre units, printer bed size/profile, and material. Read existing project
   print/manufacturing instructions. Do not check an assembled scene as one part.
2. Require analytic **STEP (`.step`, `.stp`), BREP (`.brep`, `.brp`), or build123d
   `Shape`** input. STL/OBJ/PLY and other meshes are unsupported. If the project
   currently exports only meshes, report that blocker; do not silently substitute
   a mesh check or convert triangles into a faceted BREP to claim equivalent results.
   Do not alter the export pipeline unless the task authorizes it.
3. Use the CLI path under “Local installation” if present; otherwise `print-check`.
   Run `print-check printers` to inspect known profiles if needed.
4. Run all 13 rules by default:

   ```sh
   print-check check part.step --printer bambu_a1_mini --material pla --format json
   ```

   The A1 mini is an example, not a universal default. Supply `--bed X Y Z` if the
   printer is not listed, and `--up X Y Z` if the model's +Z is not the build direction.
   The upstream fallback bed is 256 × 256 × 256 mm; state assumptions explicitly.
   Tidybot's existing printing documentation is the authority for its real setup.

5. Read **all findings and limitations**, not just the process exit code:
   - `0`: below the failure threshold (warnings can still exist).
   - `1`: a finding reached the threshold.
   - `2`: input/config/runtime error; checking did not complete successfully.
   Use `--fail-on warn` for a strict warning gate. Never suppress execution errors.
6. Report rule identifier, severity, measured value, location when available, and
   the effective orientation/profile. Explain which checks ran; a selected-rule
   run is not a full pass. A `solids` finding suppresses other findings upstream:
   fix disconnected bodies before interpreting the part.
7. If geometry changes are authorized, fix the cause and rerun on the new solid.
   Do not lower thresholds, accept more slivers, change printer, or change material
   just to silence a result. Document legitimate exceptions next to the design.
8. Retain existing project tests and slicer review. “No findings” means only that
   these heuristics found none; curved surfaces and wall thickness use sampling.

## Trusted Python and direct API

Python inputs execute arbitrary code. Read and trust their contents before:

```sh
print-check check trusted_part.py --allow-python --printer bambu_a1_mini
```

The file must expose `build()` returning a build123d shape, or a shape named `part`.
For an existing Python CAD pipeline, avoid an intermediate format:

```python
from print_check import check
from print_check.checks import Context
findings = check(shape, Context(bed=(180, 180, 180), up=(0, 0, 1)))
```

## Configuration and boundaries

`--config path.toml` is explicit. Top-level `printer` names a profile and `[context]`
sets upstream `Context` fields, such as `min_wall`, `bridge_limit`, `forward`, or
`warp_area`. CLI context flags win. `--only rule1,rule2` is diagnostic, not a full
preflight. Known rules:

`solids`, `overhang`, `floating`, `hole_ceiling`, `min_wall`, `sliver`,
`concave_cosmetic`, `bed_bevel`, `warp_risk`, `pin`, `stability`,
`projection_ratio`, `build_volume`.

Build-volume search can find an alternate orientation; it does not reorient the
part for the other checks. Lowest-point contact is assumed, not absolute Z=0.
`projection_ratio` requires a `forward` vector to opt in. Nurb's original card/
variant loading, globals, assembly simulation, and slicer are not included.

Source: https://github.com/Shpigford/nurb at
`39452e686f6b3825de836f69b9752a0a262ab555`. Preserve FSL-1.1-MIT attribution; this
is not unrestricted MIT-licensed software today.
