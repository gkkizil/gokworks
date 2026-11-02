"""Worker event batching must not hold status text during a long CAD call."""

import threading
import time

from gui_qt.workers import EventSink


def _collector():
    batches, arrived = [], threading.Event()

    def emit(values):
        batches.append(list(values))
        arrived.set()
    return batches, arrived, emit


def test_partial_batch_is_delivered_while_engine_blocks():
    batches, arrived, emit = _collector()
    sink = EventSink(emit)
    sink.put(('log', 'Adet kaynağı'))
    sink.put(('current', 'BRAKET.SLDPRT'))
    # The engine now blocks (for example in a COM export) without another put.
    assert arrived.wait(1.0), 'Bekleyen olaylar uzun işlem boyunca iletilmedi.'
    sink.close()
    assert [event for batch in batches for event in batch] == [
        ('log', 'Adet kaynağı'), ('current', 'BRAKET.SLDPRT')]


def test_events_keep_order_and_are_delivered_once():
    batches, _, emit = _collector()
    sink = EventSink(emit)
    for index in range(500):
        sink.put(('progress', index))
        if index % 97 == 0:
            time.sleep(.03)
    sink.close()
    flattened = [event for batch in batches for event in batch]
    assert flattened == [('progress', index) for index in range(500)]
    assert all(len(batch) <= 64 for batch in batches)


def test_close_flushes_and_stops_timed_delivery():
    batches, _, emit = _collector()
    sink = EventSink(emit)
    sink.put(('log', 'son'))
    sink.close()
    count = len(batches)
    time.sleep(sink.interval * 3)
    assert [event for batch in batches for event in batch] == [('log', 'son')]
    assert len(batches) == count
