"""Independent slice integration for live/native capsule-volume assertions."""

import math


def rounded_keyway_volume(diameter, length, width, depth):
    # Integrate along X, rather than the production C# integral across Z.
    # Each axial slice has a circular-segment area above a flat floor.
    r, a = diameter / 2, width / 2

    def area(half_width):
        return (half_width * math.sqrt(r*r-half_width*half_width)
                + r*r*math.asin(half_width/r) - 2*half_width*(r-depth))

    count = 20000
    step = a / count
    ends = math.fsum(area(math.sqrt(a*a-(a-(i+.5)*step)**2)) for i in range(count))
    return (length-width)*area(a) + 2*step*ends
