"""A single solid in mm. Execute only after inspecting/trusting this source."""
from build123d import Box


def build():
    return Box(20, 20, 20)
