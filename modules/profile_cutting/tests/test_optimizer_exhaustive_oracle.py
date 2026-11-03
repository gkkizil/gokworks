"""Seeded random cutting lists: the stock count equals an exhaustive minimum.

The oracle is a plain branch-and-bound bin packing written independently of
optimizer.py; it shares only the documented consumption rule
(length + allowance + kerf per piece, capacity = stock - 2 * trim).
"""

import random

import pytest

from modules.profile_cutting.models import Demand, Project
from modules.profile_cutting.optimizer import optimize


def exhaustive_minimum(sizes, capacity):
    sizes = sorted(sizes, reverse=True)
    best = [len(sizes)]

    def place(index, bins):
        if len(bins) >= best[0]:
            return
        if index == len(sizes):
            best[0] = len(bins)
            return
        size, tried = sizes[index], set()
        for slot, used in enumerate(bins):
            if used + size <= capacity and used not in tried:
                tried.add(used)
                bins[slot] += size
                place(index + 1, bins)
                bins[slot] -= size
        bins.append(size)
        place(index + 1, bins)
        bins.pop()

    place(0, [])
    return best[0]


@pytest.mark.parametrize('seed', range(6))
def test_plan_stock_count_matches_exhaustive_minimum(seed):
    rng = random.Random(20261103 + seed)
    for _ in range(25):
        stock, kerf, trim = rng.choice([1000, 2000, 6000]), rng.choice([0, 3, 5]), rng.choice([0, 0, 10])
        demands, sizes = [], []
        for index in range(rng.randint(1, 4)):
            length, count = rng.randint(50, stock - 2 * trim - kerf), rng.randint(1, 4)
            demands.append(Demand(id=f'd{index}', profile='40x40x2', material='S235JR',
                                  length=str(length), count=count))
            sizes += [length + kerf] * count
        plan = optimize(Project(demands, str(stock), str(kerf), str(trim)), seconds=5)
        assert plan.optimal
        assert len(plan.bars) == exhaustive_minimum(sizes, stock - 2 * trim), (stock, kerf, trim, sizes)
