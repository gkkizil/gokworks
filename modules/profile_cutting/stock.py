"""Profile stock on hand: full bars and offcuts per section + material.

The stock list lives in the settings (one list for every project) so it is entered
once. A cut plan takes offcuts first, then stock bars, and only then bars to buy at
the project's purchase length. After cutting, ``apply_plan`` removes the bars used
and returns the useful leftovers to stock as offcuts.
"""
from dataclasses import asdict, dataclass
import re
import uuid

from .models import canonical, number, quantity

FULL, OFFCUT = 'Tam boy', 'Artık'
SETTINGS_KEY = 'profile_cutting_stock'


@dataclass
class Stock:
    id: str
    profile: str
    material: str
    length: str
    count: int = 1
    kind: str = FULL

    @classmethod
    def new(cls, profile, material, length, count=1, kind=FULL):
        item = cls(uuid.uuid4().hex, str(profile).strip(), str(material).strip(), str(length).strip(), count, kind)
        item.validate()
        return item

    def validate(self):
        if not self.profile.strip():
            raise ValueError('Stok için profil kesiti girin (ör. 40x40x2).')
        if not self.material.strip():
            raise ValueError('Stok için malzeme girin (ör. S235JR).')
        number(self.length, 'Çubuk boyu', positive=True)
        self.count = quantity(self.count)
        if self.kind not in (FULL, OFFCUT):
            raise ValueError('Stok türü tam boy veya artık olmalı.')

    @property
    def key(self):
        return match_key(self.profile, self.material)


def match_key(profile, material):
    """Same section and material, whatever the spacing, case or × / x spelling."""
    section = re.sub(r'\s*X\s*', 'X', canonical(profile)).replace('⌀', 'Ø')
    return section, canonical(material)


def group_key(group):
    """Key of an optimizer group (section, thickness, material, standard, stock code)."""
    return group[0], group[2]


def load(settings):
    items = []
    for raw in settings.get(SETTINGS_KEY, []) or []:
        try:
            item = Stock(**raw); item.validate(); items.append(item)
        except (TypeError, ValueError):
            continue                    # a damaged entry is dropped, never the whole list
    return items


def save(settings, items):
    for item in items:
        item.validate()
    settings.set(SETTINGS_KEY, [asdict(item) for item in items])


def for_group(items, group):
    key = group_key(group)
    return [item for item in items if item.key == key]


def apply_plan(items, plan, *, keep_from=None):
    """Remove the stock bars a plan used; add leftovers ≥ ``keep_from`` mm as offcuts.

    Returns (used, added): number of stock bars taken and offcuts returned.
    """
    by_id = {item.id: item for item in items}
    used = added = 0
    for bar in plan.bars:
        source = getattr(bar, 'stock_id', '')
        if source and source in by_id:
            item = by_id[source]
            item.count -= 1; used += 1
    items[:] = [item for item in items if item.count > 0]
    if keep_from is not None:
        threshold = number(keep_from, 'Artık sınırı')
        for bar in plan.bars:
            leftover = number(bar.remaining)
            if leftover >= threshold and leftover > 0:
                profile, material = bar.label_profile, bar.label_material
                same = next((i for i in items if i.kind == OFFCUT and i.key == match_key(profile, material)
                             and number(i.length) == leftover), None)
                if same is not None:
                    same.count += 1
                else:
                    items.append(Stock.new(profile, material, format(leftover.normalize(), 'f'), 1, OFFCUT))
                added += 1
    return used, added
