"""Adaptive sample ordering shared by bending and translated tool phases."""


def sample_interval(sample, a, b, *, maximum, minimum):
    """sample(value) -> (payload, near); no dependency on playback frames.

    Endpoints alone are never sufficient: every interval is at most maximum.
    If either endpoint is near another solid, subdivision reaches minimum.
    This is deliberately a discrete search, not a swept-volume certificate.
    """
    fa, na = sample(a); fb, nb = sample(b)
    width = abs(b-a)
    if width > maximum+1e-7 or ((na or nb) and width > minimum+1e-7):
        mid = (a+b)/2
        return (sample_interval(sample, a, mid, maximum=maximum, minimum=minimum)[:-1]
                + sample_interval(sample, mid, b, maximum=maximum, minimum=minimum))
    return [fa, fb]
