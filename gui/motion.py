"""Small colour transitions; page content stays immediately interactive."""


def blend(start, end, fraction):
    channels = []
    for offset in (1, 3, 5):
        left, right = int(start[offset:offset+2], 16), int(end[offset:offset+2], 16)
        channels.append(round(left+(right-left)*fraction))
    return '#'+''.join(f'{channel:02X}' for channel in channels)


def pair(value, background):
    if value == 'transparent':
        return background
    return (value, value) if isinstance(value, str) else tuple(value)
