"""Sparrow constructs the seed; GOKWORKS refines that same verified plan."""
from datetime import datetime, timezone
import time

from . import ENGINE_VERSION
from .layout_score import layout_score
from .models import Result
from .search_budget import for_project
from .validation import validate_result

ENGINE = 'Sparrow + GOKWORKS'


def nest(project, *, stop=None, progress=None):
    project.validate()
    from . import sparrow, engine
    started = time.monotonic(); budget = for_project(project,started)
    seed = None; iterations = 0

    def report(phase, offset, span):
        def update(percent, text):
            if progress: progress(offset+span*min(100,max(0,percent))/100,phase+' · '+text)
        return update

    if stop is not None and stop.is_set():
        final = Result(project.fingerprint(),[],[p.id for p in project.parts for _ in range(p.quantity)],
                       ENGINE,'İptal · native arama başlatılmadı',0.,0,datetime.now(timezone.utc).isoformat(),True)
    else:
        # Both stages share the original project/hash and one project-wide budget.
        # Reserve contour refinement time even when strip optimization is difficult.
        cap = {'Hızlı':3.,'Dengeli':12.,'Yüksek':30.}[project.options.quality]
        first_deadline = min(budget.hard_deadline,started+min(cap,.7*(budget.deadline-started)))
        seed = sparrow.nest(project,stop=stop,progress=report('İlk yerleşim',0,40),
                            deadline=first_deadline,allow_disconnected=True)
        validate_result(project,seed,complete=False)
        iterations = seed.iterations
        if stop is not None and stop.is_set():
            final = seed
        else:
            final = engine.nest(project,stop=stop,initial=seed,budget=budget,
                                progress=report('Kontur ve levha iyileştirme',40,59))
            validate_result(project,final,complete=False)
            iterations += final.iterations
            if layout_score(project,final) > layout_score(project,seed): final = seed
        final.engine = ENGINE
        final.engine_version = (f'{sparrow.VERSION}; GOKWORKS NFP {ENGINE_VERSION}; '
                                f'Sparrow denemeleri {seed.iterations}')
    final.iterations = iterations
    final.elapsed = time.monotonic()-started
    final.stopped = stop is not None and stop.is_set()
    if final.stopped: final.timed_out = False
    validate_result(project,final,complete=False)
    if progress: progress(100,f'Kontrol tamamlandı · {len(final.placements)} yerleşti · {len(final.unplaced)} yerleşmedi')
    return final
