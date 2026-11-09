"""Private, Qt-free native worker. Rust panics cannot terminate the application."""

from collections import Counter
import json
from pathlib import Path
from threading import Thread


def run_worker(request_path):
    path = Path(request_path)
    output = path.with_name('result.json')

    def write(data):
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, allow_nan=False), encoding='utf-8')
        temporary.replace(output)

    try:
        import spyrrow
        request = json.loads(path.read_text(encoding='utf-8'))
        items = [spyrrow.Item(i['id'], [tuple(p) for p in i['shape']], i['demand'], i['angles']) for i in request['items']]
        instance = spyrrow.StripPackingInstance('GOKWORKS', request['height'], items)
        config = spyrrow.StripPackingConfig(total_computation_time=request['seconds'],
                    seed=request['seed'], num_workers=1, min_items_separation=request['separation'])
        expected = Counter({i['id']: i['demand'] for i in request['items']})

        def save(solution):
            rows = [dict(id=i.id, x=i.translation[0], y=i.translation[1], angle=i.rotation)
                    for i in solution.placed_items]
            if Counter(i['id'] for i in rows) == expected:
                write(dict(ok=True, placements=rows))

        queue = spyrrow.ProgressQueue()
        outcome = []

        def solve():
            try:
                outcome.append(instance.solve(config, progress=queue))
            except BaseException as error:  # Includes PyO3 PanicException; child boundary only.
                outcome.append(error)

        thread = Thread(target=solve, daemon=True)
        thread.start()
        while thread.is_alive():
            thread.join(.05)
            for phase, solution in queue.drain():
                if phase in (spyrrow.ReportType.ExplFeas, spyrrow.ReportType.CmprFeas, spyrrow.ReportType.Final):
                    save(solution)
        if isinstance(outcome[0], BaseException): raise outcome[0]
        save(outcome[0])
        return 0
    except BaseException as error:
        write(dict(ok=False, error=f'{type(error).__name__}: {error}'[:2000]))
        return 1
