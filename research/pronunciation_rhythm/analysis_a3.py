"""Case-cluster paired bootstrap and approximate memory audit of Stage A3 outcomes."""
from __future__ import annotations
import argparse,collections,csv,gc,json,random,statistics,tracemalloc
from pathlib import Path
from .benchmark_a3 import as_case,canonical
from .incremental_a2 import IncrementalLockDP
from .lpa_baseline_a3 import DynamicSSSPBaseline

def profile_build(ctor,case):
    gc.collect()
    tracemalloc.start()
    instance=ctor(case)
    current,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (current,peak),instance

def compute(base:Path,output:Path, iterations:int=4000,seed:int=20261024):
    with (base/'CASE_LEVEL_RESULTS.csv').open() as f:rows=list(csv.DictReader(f))
    with (base/'FROZEN_CASES_AND_EDITS.json').open() as f:frozen=json.load(f)
    rng=random.Random(seed)
    intervals={}
    for fam in ('single','multi','wide','clear'):
        sub=[r for r in rows if r['edit_family']==fam]
        by_case=collections.defaultdict(list)
        for r in sub:by_case[r['case_id']].append(r)
        labels=sorted(by_case)
        # Work with case-level paired total time, not independent repeated edits.
        case_times={c:{m:sum(int(r[f'{m}_ns']) for r in by_case[c]) for m in ('a2','dyn','full')} for c in labels}
        obs={m:sum(x[m] for x in case_times.values()) for m in ('a2','dyn','full')}
        boots={'a2_full':[],'a2_dyn':[],'dyn_full':[]}
        for _ in range(iterations):
            sampled=[case_times[labels[rng.randrange(len(labels))]] for _ in labels]
            tot={m:sum(x[m] for x in sampled) for m in ('a2','dyn','full')}
            boots['a2_full'].append(tot['a2']/tot['full'])
            boots['a2_dyn'].append(tot['a2']/tot['dyn'])
            boots['dyn_full'].append(tot['dyn']/tot['full'])
        def interval(a):
            s=sorted(a);return [round(s[int(.025*(len(s)-1))],3),round(s[int(.975*(len(s)-1))],3)]
        intervals[fam]={'cases':len(labels),'edits_observed':len(sub),
            'paired_total_time_ratio_a2_to_full':round(obs['a2']/obs['full'],3),
            'ci95_a2_to_full':interval(boots['a2_full']),
            'paired_total_time_ratio_a2_to_dyn':round(obs['a2']/obs['dyn'],3),
            'ci95_a2_to_dyn':interval(boots['a2_dyn']),
            'paired_total_time_ratio_dyn_to_full':round(obs['dyn']/obs['full'],3),
            'ci95_dyn_to_full':interval(boots['dyn_full'])}
    mem=[]
    for entry in frozen['cases'][::8]:
        case=as_case(entry)
        (ac,ap),a=profile_build(IncrementalLockDP,case)
        del a
        (bc,bp),b=profile_build(DynamicSSSPBaseline,case)
        del b
        mem.append({'case_id':case.key,'a2_build_current_kib':round(ac/1024,2),
                    'a2_build_peak_kib':round(ap/1024,2),
                    'dyn_build_current_kib':round(bc/1024,2),
                    'dyn_build_peak_kib':round(bp/1024,2)})
    result={'bootstrap_method':'Paired cluster resampling of cases, all edit/repeat observations for sampled cases retained',
            'bootstrap_iterations':iterations,'random_seed':seed,'timings':'host-specific Python wall clock microbenchmarks, not cross-machine performance',
            'intervals':intervals,'tracemalloc_samples':mem,
            'median_build_current_kib':{'a2':round(statistics.median(r['a2_build_current_kib'] for r in mem),2),
                                        'dyn':round(statistics.median(r['dyn_build_current_kib'] for r in mem),2)},
            'median_build_peak_kib':{'a2':round(statistics.median(r['a2_build_peak_kib'] for r in mem),2),
                                     'dyn':round(statistics.median(r['dyn_build_peak_kib'] for r in mem),2)},
            'no_statistical_novelty_claim':True}
    output.write_bytes(canonical(result));return result

def main():
    a=argparse.ArgumentParser();a.add_argument('--directory',type=Path,default=Path('reports/research/track_a3'))
    args=a.parse_args();print(json.dumps(compute(args.directory,args.directory/'UNCERTAINTY_AND_MEMORY.json'),indent=2))
if __name__=='__main__':main()
