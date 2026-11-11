"""Stage A3: prospectively frozen constructed formal alignment benchmark.

This is not an independent natural-language or musician-validated corpus.
Case generation is not conditioned on downstream algorithm results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict
from pathlib import Path
from .core import AlignmentCase, Candidate, RhythmSpec

SEED = 20261024
PROTOCOL = 'MAQAM_A3_FORMAL_PROSPECTIVE_FREEZE_2026_10_24_V1'

def canonical(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',', ':'))+'\n').encode('utf-8')

def generate():
    rng = random.Random(SEED)
    cases, edits = [], []
    for ix in range(96):
        family = ('short','medium','long')[ix % 3]
        n = {'short': rng.randrange(8,14), 'medium':rng.randrange(14,22), 'long':rng.randrange(22,33)}[family]
        events = tuple(rng.choice((1,1,2,2,3)) for _ in range(n))
        pref = [0]
        for d in events: pref.append(pref[-1]+d)
        # Structural diversity without outcome-conditioned filtering.
        bounds = ()
        if ix % 4 in (1,2):
            opts = pref[1:-1]
            if opts:
                bounds = tuple(sorted(rng.sample(opts,min(ix % 3 + 1,len(opts)))))
        num_candidates = rng.randrange(2,7)
        cs = []
        for ci in range(num_candidates):
            k = max(2,min(n,n//2+rng.randint(-2,3)))
            cs.append(Candidate(f'A3_{ix:03d}_C{ci}',tuple(rng.choice('abcde') for _ in range(k)),
                                prior=rng.randint(0,3),ideal_ticks=tuple(rng.randint(1,5) for _ in range(k))))
        spec = RhythmSpec(events,sum(events),min_syllable_ticks=1,
                          max_syllable_ticks=5 if ix%2 else 8,
                          max_events_per_syllable=3 if ix%2 else 5,
                          boundaries=bounds)
        case = AlignmentCase(f'A3_{ix:03d}',tuple(cs),spec)
        cases.append({'case':asdict(case),'family':family})
        current={}
        for j in range(8):
            if j <= 3:
                fam='single'
                evt=rng.randrange(n)
                if evt in current and j%2: current.pop(evt)
                else: current[evt]=rng.choice('abcde')
            elif j <= 5:
                fam='multi'
                for evt in rng.sample(range(n),min(4,n)):
                    if evt in current and rng.random()<.3:current.pop(evt)
                    else: current[evt]=rng.choice('abcde')
            elif j == 6:
                fam='wide'
                current={evt:rng.choice('abcde') for evt in range(n)}
            else:
                fam='clear'
                current.clear()
            edits.append({'case_id':case.key,'step':j,'family':fam,'locks':[[i,v] for i,v in sorted(current.items())]})
    return {'protocol':PROTOCOL,'seed':SEED,'provenance':'CONSTRUCTED_FORMAL_ONLY',
            'generation_independent_of_algorithm_results':True,
            'cases':cases,'edits':edits}

def as_case(entry):
    d=entry['case']
    cand = tuple(Candidate(c['key'],tuple(c['syllables']),c['prior'],tuple(c['ideal_ticks']),c['evidence']) for c in d['candidates'])
    r=d['rhythm']
    spec=RhythmSpec(tuple(r['events']),r['cycle_ticks'],r['min_syllable_ticks'],r['max_syllable_ticks'],r['max_events_per_syllable'],tuple(r['boundaries']),tuple((int(i),v) for i,v in r['locked_events']))
    return AlignmentCase(d['key'],cand,spec,d['provenance'])

def freeze(path:Path):
    if path.exists():raise FileExistsError('Frozen benchmark cannot be overwritten')
    data=canonical(generate())
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print('FROZEN_SHA256',freeze(a.output))
if __name__=='__main__':main()
