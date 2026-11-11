"""Explicit configuration only: never reads or writes Nurb's global settings."""

from dataclasses import fields
from importlib.resources import files
import math
from pathlib import Path
import tomllib

from .checks import Context, SHRINK


def profiles():
    return tomllib.loads(files("print_check").joinpath("printers.toml").read_text())


def validate(ctx):
    for name in ("bed", "up", "forward"):
        value = getattr(ctx, name)
        if name == "forward" and value is None:
            continue
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError(f"{name} must have three numbers")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
            raise ValueError(f"{name} must contain finite numbers")
        if name == "bed" and min(value) <= 0:
            raise ValueError("bed dimensions must be positive")
        if name != "bed" and math.hypot(*value) == 0:
            raise ValueError(f"{name} must be nonzero")
        setattr(ctx, name, tuple(value))
    for name in ("overhang_limit", "bridge_limit", "overhang_reach", "projection_limit",
                 "cosmetic_chamfer", "min_wall", "sliver_area", "warp_area", "warp_radius"):
        value = getattr(ctx, name)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite nonnegative number")
    if ctx.overhang_limit > 90:
        raise ValueError("overhang_limit must be between 0 and 90 degrees")
    if ctx.material is not None:
        if not isinstance(ctx.material, str) or ctx.material.lower() not in SHRINK:
            raise ValueError(f"material must be one of: {', '.join(SHRINK)}")
        ctx.material = ctx.material.lower()
    if not isinstance(ctx.accepted, dict) or set(ctx.accepted) - {"sliver"}:
        raise ValueError("accepted supports only the upstream sliver count")
    if any(type(v) is not int or v < 0 for v in ctx.accepted.values()):
        raise ValueError("accepted counts must be nonnegative integers")
    return ctx


def context(config=None, printer=None, overrides=None):
    block = tomllib.loads(Path(config).read_text()) if config else {}
    if set(block) - {"printer", "context"}:
        raise ValueError("Configuration supports only printer and [context]")
    selected = printer or block.get("printer")
    values = {}
    if selected:
        known = profiles()
        if selected not in known:
            raise ValueError(f"Unknown printer {selected!r}; run print-check printers")
        values.update({k: v for k, v in known[selected].items()
                       if k in {f.name for f in fields(Context)}})
    custom = block.get("context", {})
    if not isinstance(custom, dict):
        raise ValueError("context must be a TOML table")
    values.update(custom)
    values.update({k: v for k, v in (overrides or {}).items() if v is not None})
    unknown = values.keys() - {f.name for f in fields(Context)}
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
    return validate(Context(**values))
