"""Atomic text/CSV publication for user-chosen report paths.

A report is written to a hidden temporary file in the destination folder and
moved over the target only when complete. A failed write (full disk, locked
file, encoding error) leaves the user's existing file untouched and no partial
file behind.
"""

import csv
import io
import os
from pathlib import Path
from tempfile import mkstemp

from shared.settings import _publish


def write_text_atomic(path, text, *, encoding='utf-8'):
    path = Path(path)
    data = text.encode(encoding)          # encoding errors fail before touching disk
    fd, name = mkstemp(prefix='.gokworks-', suffix=path.suffix or '.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _publish(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_csv_atomic(path, header, rows, *, delimiter=';'):
    """Excel-friendly UTF-8 (BOM) CSV, published atomically."""
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(header)
    writer.writerows(rows)
    return write_text_atomic(path, buffer.getvalue(), encoding='utf-8-sig')
