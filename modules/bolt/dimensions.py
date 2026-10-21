"""Nominal ISO 4017 hexagon-head geometry, in millimetres.

These dimensions illustrate a fully threaded hexagon-head screw. For fine
threads the head is schematic, not an ISO 8676 dimensional specification.
They do not define tolerances, screw length, a nut, or tightening torque.
"""

from dataclasses import dataclass

from modules.bolt.rules import thread_geometry


# Diameter: (nominal head height k, across-flats s). ISO 4017, not DIN 933.
HEADS = {
    3: (2., 5.5), 4: (2.8, 7.), 5: (3.5, 8.), 6: (4., 10.),
    8: (5.3, 13.), 10: (6.4, 16.), 12: (7.5, 18.), 14: (8.8, 21.),
    16: (10., 24.), 18: (11.5, 27.), 20: (12.5, 30.), 22: (14., 34.),
    24: (15., 36.), 27: (17., 41.), 30: (18.7, 46.), 33: (21., 50.),
    36: (22.5, 55.), 39: (25., 60.),
}


@dataclass(frozen=True)
class Dimensions:
    diameter: float
    pitch: float
    head_height: float
    across_flats: float
    tapping_hole: float


def dimensions(metric, thread_series='Kaba diş', pitch=None):
    diameter, pitch = thread_geometry(metric, thread_series, pitch)
    height, flats = HEADS[diameter]
    return Dimensions(diameter, pitch, height, flats, diameter-pitch)
