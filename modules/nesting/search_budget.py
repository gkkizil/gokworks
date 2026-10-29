"""Adaptive search scheduling; geometry and placement acceptance stay exact."""

from dataclasses import dataclass
import math

from .geometry import polygons


@dataclass
class SearchBudget:
    started: float
    deadline: float
    hard_deadline: float
    max_attempts: int
    minimum_attempts: int = 0
    patience: int = 0
    completed: int = 0
    stale: int = 0
    reported_percent: int = 0

    @property
    def automatic(self):
        return self.patience > 0

    def exhausted(self, now):
        return now >= self.deadline

    def allow_work(self, now):
        if not self.exhausted(now):
            return True
        if (self.automatic and now < self.hard_deadline
                and (self.completed < self.minimum_attempts or self.stale == 0)):
            # Bootstrap a complete plan and its first detailed passes even when
            # the initial estimate was too small for this machine/geometry.
            window = max(.25,self.deadline-self.started)
            self.deadline = min(self.hard_deadline,max(now+.25,self.started+window*1.5))
            return True
        return False

    def percent(self, now):
        value = int(100*(now-self.started)/max(.001,self.deadline-self.started))
        self.reported_percent = max(self.reported_percent,min(99,value))
        return self.reported_percent

    def continue_after_trial(self, now, duration, improved):
        """Allow useful work, but stop repeated non-improving complete passes."""
        self.completed += 1
        if not self.automatic:
            return True
        self.stale = 0 if improved else self.stale+1
        if (now >= self.hard_deadline or self.completed >= self.max_attempts
                or (self.completed >= self.minimum_attempts and self.stale >= self.patience)):
            return False
        # Measured pass cost adapts the next allowance to the actual machine.
        # A fast initial pass is always followed by detailed contour passes.
        allowance = max(.25,duration*(1.5 if improved else 1.15))
        self.deadline = min(self.hard_deadline,max(self.deadline,now+allowance))
        return True


def meaningful_improvement(score, previous):
    if previous is None or score[:3] < previous[:3]:
        return True
    if score[:3] != previous[:3]:
        return False
    # Tiny floating-point changes in packed height must not prolong a plateau.
    return previous[3]-score[3] > max(1e-6,abs(previous[3])*1e-4)


def uniform_stock_floor(project):
    """An admissible count/area bound only for unambiguous equal-area stocks."""
    groups = {}
    for part in project.parts:
        key = (part.material,part.thickness)
        area,count = groups.get(key,(0.,0))
        groups[key] = (area+part.area*part.quantity,count+part.quantity)
    count = 0; area = 0.
    for (material,thickness),(net,quantity) in groups.items():
        # Nearly equal but distinct thickness groups can share a stock under
        # the engine's tolerance; decline the shortcut in that ambiguous case.
        if any(m==material and t!=thickness and abs(t-thickness)<=2e-7 for m,t in groups):
            return None
        choices = [s for s in project.sheets if s.stock>0 and s.material==material
                   and abs(s.thickness-thickness)<=1e-7]
        areas = {s.width*s.height for s in choices}
        if len(areas)!=1:return None
        sheet_area = next(iter(areas))
        minimum = max(1,math.ceil((net-quantity*1e-6)/sheet_area))
        count += minimum;area += minimum*sheet_area
    return count,area


def for_project(project, started):
    options = project.options
    attempts = {'Hızlı':4,'Dengeli':13,'Yüksek':41}[options.quality]
    if options.seconds is not None:
        # Existing numeric project/API budgets retain their original behavior.
        deadline = started+float(options.seconds)
        return SearchBudget(started,deadline,deadline,attempts)
    floor,ceiling,minimum,patience = {
        'Hızlı':(2.,15.,3,2),
        'Dengeli':(3.,45.,4,3),
        'Yüksek':(5.,90.,6,5),
    }[options.quality]
    work = 0.; unique_vertices = 0
    for part in project.parts:
        vertices = sum(len(p.exterior.coords)+sum(len(r.coords) for r in p.interiors)
                       for p in polygons(part.polygon))
        unique_vertices += vertices
        angles = [0] if not options.rotation else options.angles
        if options.grain_locked or part.grain_locked:
            angles = [a for a in angles if abs(a % 180) < 1e-7]
        work += part.quantity*math.sqrt(max(1,len(set(angles))))*(1+math.log2(1+vertices/8))
    initial = min(ceiling,floor+.025*work+.0008*unique_vertices)
    return SearchBudget(started,started+initial,started+ceiling,attempts,minimum,patience)
