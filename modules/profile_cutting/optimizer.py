"""Fixed-length, independent stock pools; exact Decimal conservation checks."""

from dataclasses import dataclass, field
from bisect import bisect_left, insort
from decimal import Decimal, ROUND_CEILING
import time

from .models import number, quantity, checkpoint


@dataclass
class Cut:
    demand_id: str
    label: str
    length: str
    allowance: str
    consumption: str
    angle1: str = ''
    angle2: str = ''
    note: str = ''


@dataclass
class Bar:
    group: tuple
    cuts: list[Cut] = field(default_factory=list)
    remaining: str = ''
    stock_length: str = ''      # this bar's length; '' = the plan's purchase length
    stock_id: str = ''          # the stock entry it came from; '' = a bar to buy
    source: str = ''            # 'Artık' / 'Stok' / 'Satın alınacak'
    label_profile: str = ''
    label_material: str = ''

    @property
    def length(self):
        return self.stock_length


@dataclass
class Plan:
    bars: list[Bar]
    optimal: bool
    stock_length: str
    kerf: str
    trim: str
    method: str


BUY, STOCK = 'Satın alınacak', 'Stok'


def _with_stock(group, pieces, items, stock, kerf, trim, stop):
    """Best-fit decreasing over bars of different lengths: offcuts, then stock, then bars to buy.

    A new bar is opened only when no open bar fits the piece; it is the shortest
    available bar that fits (offcuts before full stock bars), else a bar to buy.
    """
    from .stock import OFFCUT
    available = []                      # [length, kind order, item, remaining count]
    for item in items:
        available.append([number(item.length), 0 if item.kind == OFFCUT else 1, item, item.count])
    available.sort(key=lambda entry: (entry[1], entry[0]))
    bins = []                           # [space, capacity, item or None, contents]
    for size, row in pieces:
        checkpoint(stop)
        fitting = [b for b in bins if b[0] >= size]
        if fitting:
            target = min(fitting, key=lambda b: b[0])
        else:
            choice = None
            for entry in available:
                if entry[3] > 0 and entry[0]-2*trim >= size:
                    if choice is None or (entry[1], entry[0]) < (choice[1], choice[0]):
                        choice = entry
            if choice is not None:
                choice[3] -= 1
                target = [choice[0]-2*trim, choice[0], choice[2], []]
            else:
                if stock-2*trim < size:
                    raise ValueError(f'{row.profile} / {row.length} mm: stoktaki çubuklara ve satın alma boyuna sığmıyor.')
                target = [stock-2*trim, stock, None, []]
            bins.append(target)
        target[0] -= size; target[3].append((size, row))
    bars = []
    for space, length, item, contents in bins:
        first = contents[0][1]
        bars.append(Bar(group, [Cut(row.id, row.profile, row.length, row.allowance, str(size), row.angle1, row.angle2, row.note)
                                for size, row in contents], str(space), str(length), item.id if item else '',
                        (item.kind if item.kind != 'Tam boy' else STOCK) if item else BUY, first.profile, first.material))
    return bars


def optimize(project, *, seconds=2, stop=None, stock_items=()):
    project.validate(require_current=True)
    if not project.demands: raise ValueError('Önce kesim listesine profil ekleyin.')
    if not 0 < float(seconds) <= 30: raise ValueError('Çözüm süresi 0–30 saniye arasında olmalı.')
    stock, kerf, trim = (number(project.stock_length), number(project.kerf), number(project.trim))
    capacity = stock - 2*trim
    groups = {}
    count = sum(quantity(d.count) for d in project.demands)
    if count > 20000: raise ValueError('Bir planda en fazla 20000 profil desteklenir.')
    from .stock import for_group
    for row in project.demands:
        checkpoint(stop)
        need = number(row.length) + number(row.allowance) + kerf
        longest = max([number(i.length) for i in for_group(stock_items, row.group)] + [stock]) - 2*trim
        if need > longest:
            raise ValueError(f'{row.profile} / {row.length} mm: ek boy ve kesim payıyla stok boyuna sığmıyor.')
        groups.setdefault(row.group, []).extend((need, row) for _ in range(row.count))
    deadline = time.monotonic()+float(seconds)
    result, all_optimal = [], True
    used_stock = False
    for group, pieces in groups.items():
        checkpoint(stop)
        pieces.sort(key=lambda entry: entry[0], reverse=True)
        items = for_group(stock_items, group)
        if items:
            used_stock = True
            result.extend(_with_stock(group, pieces, items, stock, kerf, trim, stop))
            all_optimal = False
            continue
        bins, free = [], []
        for size, row in pieces:
            checkpoint(stop)
            # Preserve best-fit and index tie-breaking without a Python scan of
            # every opened stock for every piece. Decimal ordering stays exact.
            position = bisect_left(free, (size, -1))
            if position == len(free):
                target, space = len(bins), capacity
                bins.append([])
            else:
                space, target = free.pop(position)
            bins[target].append((size, row))
            insort(free, (space-size, target))
        lower = int((sum((p[0] for p in pieces), Decimal(0))/capacity).to_integral_value(rounding=ROUND_CEILING))
        proven = len(bins) == lower
        if not proven and len(pieces) <= 22:
            def search(target):
                spaces, allocation = [capacity]*target, [[] for _ in range(target)]
                def place(index):
                    checkpoint(stop)
                    if time.monotonic() >= deadline: raise TimeoutError()
                    if index == len(pieces): return True
                    size, row = pieces[index]
                    tried = set()
                    for b in sorted(range(target), key=lambda i: spaces[i]):
                        if spaces[b] < size or spaces[b] in tried: continue
                        tried.add(spaces[b]); spaces[b] -= size; allocation[b].append((size,row))
                        if place(index+1): return True
                        spaces[b] += size; allocation[b].pop()
                    return False
                return allocation if place(0) else None
            try:
                for target in range(lower, len(bins)):
                    allocation = search(target)
                    if allocation is not None: bins = allocation; break
                proven = True  # Every smaller count was exhausted, or lower bound attained.
            except TimeoutError: proven = False
        all_optimal &= proven
        for contents in bins:
            used = sum((item[0] for item in contents), Decimal(0))
            first = contents[0][1]
            result.append(Bar(group, [Cut(row.id, row.profile, row.length, row.allowance, str(size), row.angle1, row.angle2, row.note)
                                     for size, row in contents], str(capacity-used), source=BUY,
                              label_profile=first.profile, label_material=first.material))
    plan = Plan(result, all_optimal, str(stock), str(kerf), str(trim),
                'Önce elinizdeki artık ve stok çubukları kullanıldı; minimum garanti edilmez' if used_stock else
                'Stok adedi minimumu doğrulandı' if all_optimal else 'Best-fit + sınırlı tam arama; minimum garanti edilmez')
    validate_plan(project, plan)
    return plan


def validate_plan(project, plan):
    """Reject omitted, extra, cross-material, altered-length or overfull cuts."""
    project.validate(require_current=True)
    rows = {row.id: row for row in project.demands}
    actual = {key: 0 for key in rows}
    stock, kerf, trim = (number(plan.stock_length), number(plan.kerf), number(plan.trim))
    if (stock, kerf, trim) != (number(project.stock_length), number(project.kerf), number(project.trim)):
        raise ValueError('Plan stok/kesim ayarları değişmiş; yeniden hesaplayın.')
    for bar in plan.bars:
        used = 2*trim
        length = number(bar.stock_length) if bar.stock_length else stock
        if not bar.cuts: raise ValueError('Boş stok planı geçersiz.')
        for cut in bar.cuts:
            row = rows.get(cut.demand_id)
            if row is None or row.group != bar.group:
                raise ValueError('Kesim planında kaynak veya malzeme grubu uyuşmuyor.')
            if number(cut.length) != number(row.length) or number(cut.allowance) != number(row.allowance):
                raise ValueError('Plan boyu değişmiş; yeniden hesaplayın.')
            need = number(row.length)+number(row.allowance)+kerf
            if number(cut.consumption) != need: raise ValueError('Plan kesim payı tutarsız.')
            used += need; actual[row.id] += 1
        if used > length or number(bar.remaining) != length-used:
            raise ValueError('Stok sınırı veya kalan boy hesabı hatalı.')
    if actual != {key: row.count for key, row in rows.items()}:
        raise ValueError('Plan miktarları kesim listesiyle eşleşmiyor.')
