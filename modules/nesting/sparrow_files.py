"""Bounded handling of Windows sharing locks on our private worker files only."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import time


def filesystem_call(operation):
    """Retry sharing/access-denied errors; all other errors remain failures.

    A completed child can leave a file briefly locked by Windows file-system
    consumers. This also covers removal of its private TemporaryDirectory.
    This never reruns the native solver or retries invalid JSON/placements.
    """
    delays = (.01, .02, .04, .08, .1)
    for attempt in range(len(delays)+1):
        try:
            return operation()
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == len(delays):
                raise
            time.sleep(delays[attempt])


@contextmanager
def workspace():
    temporary = TemporaryDirectory(prefix='gokworks-sparrow-')
    try:
        yield Path(temporary.name)
    finally:
        filesystem_call(temporary.cleanup)
