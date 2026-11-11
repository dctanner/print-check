"""Nurb's printability checks on CAD solids, extracted for standalone use."""

__version__ = "0.1.0"


def check(shape, context=None, only=None):
    """Check a build123d shape in millimetres. Returns Finding objects."""
    from .checks import Context, RULES, run
    from .config import validate

    context = context or Context()
    validate(context)
    if only is not None:
        only = set(only)
        unknown = only - RULES.keys()
        if unknown:
            raise ValueError(f"Unknown rules: {', '.join(sorted(unknown))}")
    if not shape.is_valid:
        raise ValueError("Invalid B-rep; repair the source solid before checking")
    return run(shape, context, only=only)
