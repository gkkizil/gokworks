"""Offline nominal channel presets, transcribed from published supplier tables.

Sources and limits are documented in README.md. These are nominal CAD dimensions,
not a tolerance/load certification. No interpolation for external retaining rings.
"""

from dataclasses import dataclass
import math


DIN_471_SOURCE = 'https://www.beneri.com/en/prodotto/din-471'
DIN_6885_SOURCE = 'https://www.somp.com.lb/engineering/Keyways.shtml'
KEYWAY_CHECK_SOURCE = 'https://www.elesa-ganter.com/static/technicaldata/files/DIN6885_Keyways_EN.pdf'
KEY_LENGTH_SOURCE = 'https://eshop.boellhoff.de/out/media/pdf/DIN_6885_Stahl___en.pdf'
ISO_773_STATUS = 'https://www.iso.org/standard/5056.html'
CHECKED_ON = '2026-10-26'


@dataclass(frozen=True)
class GrooveSize:
    diameter: float
    groove_diameter: float
    width: float
    ring_thickness: float
    edge_margin: float

    @property
    def depth(self):
        return (self.diameter - self.groove_diameter) / 2


@dataclass(frozen=True)
class KeywaySize:
    diameter_over: float
    diameter_to: float
    width: float
    key_height: float
    depth: float
    hub_depth: float
    length_min: float | None
    length_max: float | None


# BENERI DIN 471, normal type. Columns d1, d2, m, S, n (mm).
# Deliberate catalogue subset 3..100 mm; missing nominal sizes are not guessed.
GROOVE_SIZES = (
    GrooveSize(3, 2.8, 0.5, 0.4, 0.3),
    GrooveSize(4, 3.8, 0.5, 0.4, 0.3),
    GrooveSize(5, 4.8, 0.7, 0.6, 0.3),
    GrooveSize(6, 5.7, 0.8, 0.7, 0.5),
    GrooveSize(7, 6.7, 0.9, 0.8, 0.5),
    GrooveSize(8, 7.6, 0.9, 0.8, 0.6),
    GrooveSize(9, 8.6, 1.1, 1, 0.6),
    GrooveSize(10, 9.6, 1.1, 1, 0.6),
    GrooveSize(11, 10.5, 1.1, 1, 0.8),
    GrooveSize(12, 11.5, 1.1, 1, 0.8),
    GrooveSize(13, 12.4, 1.1, 1, 0.9),
    GrooveSize(14, 13.4, 1.1, 1, 0.9),
    GrooveSize(15, 14.3, 1.1, 1, 1.1),
    GrooveSize(16, 15.2, 1.1, 1, 1.2),
    GrooveSize(17, 16.2, 1.1, 1, 1.2),
    GrooveSize(18, 17, 1.3, 1.2, 1.5),
    GrooveSize(19, 18, 1.3, 1.2, 1.5),
    GrooveSize(20, 19, 1.3, 1.2, 1.5),
    GrooveSize(21, 20, 1.3, 1.2, 1.5),
    GrooveSize(22, 21, 1.3, 1.2, 1.5),
    GrooveSize(23, 22, 1.3, 1.2, 1.7),
    GrooveSize(24, 22.9, 1.3, 1.2, 1.7),
    GrooveSize(25, 23.9, 1.3, 1.2, 1.7),
    GrooveSize(26, 24.9, 1.3, 1.2, 1.7),
    GrooveSize(27, 25.6, 1.3, 1.2, 1.7),
    GrooveSize(28, 26.6, 1.6, 1.5, 2.1),
    GrooveSize(29, 27.6, 1.6, 1.5, 2.1),
    GrooveSize(30, 28.6, 1.6, 1.5, 2.1),
    GrooveSize(31, 29.3, 1.6, 1.5, 2.6),
    GrooveSize(32, 30.3, 1.6, 1.5, 2.6),
    GrooveSize(33, 31.3, 1.6, 1.5, 2.6),
    GrooveSize(34, 32.3, 1.6, 1.5, 2.6),
    GrooveSize(35, 33, 1.6, 1.5, 3),
    GrooveSize(36, 34, 1.85, 1.75, 3),
    GrooveSize(37, 35, 1.85, 1.75, 3),
    GrooveSize(38, 36, 1.85, 1.75, 3),
    GrooveSize(39, 37, 1.85, 1.75, 3.8),
    GrooveSize(40, 37.5, 1.85, 1.75, 3.8),
    GrooveSize(41, 38.5, 1.85, 1.75, 3.8),
    GrooveSize(42, 39.5, 1.85, 1.75, 3.8),
    GrooveSize(43, 40.5, 1.85, 1.75, 3.8),
    GrooveSize(44, 41.5, 1.85, 1.75, 3.8),
    GrooveSize(45, 42.5, 1.85, 1.75, 3.8),
    GrooveSize(46, 43.5, 1.85, 1.75, 3.8),
    GrooveSize(47, 44.5, 1.85, 1.75, 3.8),
    GrooveSize(48, 45.5, 1.85, 1.75, 3.8),
    GrooveSize(50, 47, 2.15, 2, 4.5),
    GrooveSize(51, 48, 2.15, 2, 4.5),
    GrooveSize(52, 49, 2.15, 2, 4.5),
    GrooveSize(54, 51, 2.15, 2, 4.5),
    GrooveSize(55, 52, 2.15, 2, 4.5),
    GrooveSize(56, 53, 2.15, 2, 4.5),
    GrooveSize(57, 54, 2.15, 2, 4.5),
    GrooveSize(58, 55, 2.15, 2, 4.5),
    GrooveSize(60, 57, 2.15, 2, 4.5),
    GrooveSize(62, 59, 2.15, 2, 4.5),
    GrooveSize(63, 60, 2.15, 2, 4.5),
    GrooveSize(65, 62, 2.65, 2.5, 4.5),
    GrooveSize(67, 64, 2.65, 2.5, 4.5),
    GrooveSize(68, 65, 2.65, 2.5, 4.5),
    GrooveSize(70, 67, 2.65, 2.5, 4.5),
    GrooveSize(72, 69, 2.65, 2.5, 4.5),
    GrooveSize(75, 72, 2.65, 2.5, 4.5),
    GrooveSize(77, 74, 2.65, 2.5, 4.5),
    GrooveSize(78, 75, 2.65, 2.5, 4.5),
    GrooveSize(80, 76.5, 2.65, 2.5, 5.3),
    GrooveSize(82, 78.5, 2.65, 2.5, 5.3),
    GrooveSize(85, 81.5, 3.15, 3, 5.3),
    GrooveSize(87, 83.5, 3.15, 3, 5.3),
    GrooveSize(88, 84.5, 3.15, 3, 5.3),
    GrooveSize(90, 86.5, 3.15, 3, 5.3),
    GrooveSize(92, 88.5, 3.15, 3, 5.3),
    GrooveSize(95, 91.5, 3.15, 3, 5.3),
    GrooveSize(97, 93.5, 3.15, 3, 5.3),
    GrooveSize(98, 94.5, 3.15, 3, 5.3),
    GrooveSize(100, 96.5, 3.15, 3, 5.3),
)

# SOMP DIN 6885: (over d, to d], b, h, shaft t1, hub t2, min/max l (mm).
# The first range includes 6 mm, as confirmed by Elesa+Ganter's table.
KEYWAY_SIZES = (
    KeywaySize(6, 8, 2, 2, 1.2, 1, 6, 20),
    KeywaySize(8, 10, 3, 3, 1.8, 1.4, 6, 36),
    KeywaySize(10, 12, 4, 4, 2.5, 1.8, 8, 45),
    KeywaySize(12, 17, 5, 5, 3, 2.3, 10, 56),
    KeywaySize(17, 22, 6, 6, 3.5, 2.8, 14, 70),
    KeywaySize(22, 30, 8, 7, 4, 3.3, 18, 90),
    KeywaySize(30, 38, 10, 8, 5, 3.3, 20, 100),
    KeywaySize(38, 44, 12, 8, 5, 3.3, 28, 140),
    KeywaySize(44, 50, 14, 9, 5.5, 3.8, 36, 160),
    KeywaySize(50, 58, 16, 10, 6, 4.3, 45, 180),
    KeywaySize(58, 65, 18, 11, 7, 4.4, 50, 200),
    KeywaySize(65, 75, 20, 12, 7.5, 4.9, 56, 220),
    KeywaySize(75, 85, 22, 14, 9, 5.4, 63, 250),
    KeywaySize(85, 95, 25, 14, 9, 5.4, 70, 280),
    KeywaySize(95, 110, 28, 16, 10, 6.4, 80, 320),
    KeywaySize(110, 130, 32, 18, 11, 7.4, 90, 360),
    KeywaySize(130, 150, 36, 20, 12, 8.4, None, None),
    KeywaySize(150, 170, 40, 22, 13, 9.4, None, None),
    KeywaySize(170, 200, 45, 25, 15, 10.4, None, None),
    KeywaySize(200, 230, 50, 28, 17, 11.4, None, None),
    KeywaySize(230, 260, 56, 32, 20, 12.4, None, None),
    KeywaySize(260, 290, 63, 32, 20, 12.4, None, None),
    KeywaySize(290, 330, 70, 36, 22, 14.4, None, None),
    KeywaySize(330, 380, 80, 40, 25, 15.4, None, None),
    KeywaySize(380, 440, 90, 45, 28, 17.4, None, None),
    KeywaySize(440, 500, 100, 50, 31, 19.5, None, None),
)

# Nominal length suggestions from the Böllhoff catalogue, plus the 6 mm
# lower endpoint explicitly listed by SOMP. Not a stock/availability promise.
# Each cross-section is further limited by SOMP's min/max and available space.
KEY_LENGTHS = (6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 36, 40,
               45, 50, 56, 60, 63, 70, 80, 90, 100, 110, 120, 125, 140, 160, 180)


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def groove_size(diameter):
    """Exact nominal diameter only: 30.2 mm must not silently become DIN 471-30."""
    if not _positive(diameter):
        return None
    return next((row for row in GROOVE_SIZES if row.diameter == diameter), None)


def keyway_size(diameter):
    if not _positive(diameter):
        return None
    return next((row for i, row in enumerate(KEYWAY_SIZES)
                 if (row.diameter_over < diameter or i == 0 and diameter == row.diameter_over)
                 and diameter <= row.diameter_to), None)


def keyway_lengths(size, available):
    """A verified length-series subset; never round a length up beyond the stage."""
    if size is None or not _positive(available) or size.length_min is None:
        return ()
    return tuple(length for length in KEY_LENGTHS
                 if size.length_min <= length <= size.length_max
                 and length > size.width and length <= available)


def same_dimension(a, b):
    return type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, rel_tol=0, abs_tol=1e-8)

