"""Independent subset DP oracle, distinct from the production bin search."""

import random
from modules.profile_cutting.models import Project,Demand
from modules.profile_cutting.optimizer import optimize


def test_small_integer_plans_match_independent_subset_dp():
    rng=random.Random(20261022)
    for case in range(100):
        n=rng.randint(1,10)
        kerf,trim=rng.randint(0,4),rng.randint(0,3)
        capacity=100-2*trim
        lengths=[rng.randint(1,80) for _ in range(n)]
        allowances=[rng.randint(0,4) for _ in range(n)]
        sizes=[a+b+kerf for a,b in zip(lengths,allowances)]
        # dp[subset] stores the best (number of stocks, load of last stock).
        dp=[(n+1,0)]*(1<<n);dp[0]=(1,0)
        for mask in range(1,1<<n):
            for bit,size in enumerate(sizes):
                if mask & (1<<bit):
                    bins,used=dp[mask^(1<<bit)]
                    candidate=(bins,used+size) if used+size<=capacity else (bins+1,size)
                    dp[mask]=min(dp[mask],candidate)
        project=Project([Demand(str(i),'40x40x2','S235JR',str(length),1,allowance=str(allowances[i]))
                         for i,length in enumerate(lengths)],stock_length='100',kerf=str(kerf),trim=str(trim))
        result=optimize(project,seconds=.2)
        assert len(result.bars)==dp[-1][0] and result.optimal,(case,sizes,len(result.bars),dp[-1])
