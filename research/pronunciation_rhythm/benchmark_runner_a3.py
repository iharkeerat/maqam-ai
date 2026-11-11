"""Track A3 frozen, multi-baseline formal benchmark. No musical validity or novelty claims."""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,random,statistics,sys,time,tracemalloc
from pathlib import Path
from .benchmark_a3 import as_case,canonical,PROTOCOL
from .core import composed_dp,verify_solution
from .incremental_a2 import IncrementalLockDP
from .lpa_baseline_a3 import DynamicSSSPBaseline

def total_bytes(obj,seen=None):
    if seen is None:seen=set()
    if id(obj) in seen:return 0
    seen.add(id(obj)); size=sys.getsizeof(obj)
    if isinstance(obj,dict):
        for k,v in obj.items():size+=total_bytes(k,seen)+total_bytes(v,seen)
    elif isinstance(obj,(list,tuple,set,frozenset)):
        for x in obj:size+=total_bytes(x,seen)
    return size

def analyze(path:Path,output:Path,seed:int=7731, reps:int=1):
    if reps<1:raise ValueError('reps must be positive')
    raw=path.read_bytes(); data=json.loads(raw)
    if data['protocol']!=PROTOCOL or data['provenance']!='CONSTRUCTED_FORMAL_ONLY':
        raise ValueError('Unfrozen or improperly sourced benchmark')
    grouped=collections.defaultdict(list)
    for e in data['edits']:grouped[e['case_id']].append(e)
    out=[]; memory=[]
    for rep in range(reps):
        for j,entry in enumerate(data['cases']):
            case=as_case(entry)
            a=IncrementalLockDP(case)
            b=DynamicSSSPBaseline(case)
            assert a.graph.nodes==b.graph.nodes and a.graph.edges==b.graph.edges
            if (a.result().status,a.result().solution)!=(b.result().status,b.result().solution):
                raise AssertionError('Initial-state baseline mismatch')
            # Track structures separately, including multiple g/rhs queues for dynamic SSSP.
            if rep==0 and j%8==0:
                memory.append({'case_id':case.key,'family':entry['family'],
                               'a2_cache_bytes_approx':total_bytes(a.values),
                               'dynamic_cache_bytes_approx':total_bytes((b.g,b.rhs,b._heap,b._pending)),
                               'a2_static_nodes':a.graph.static_states,'dynamic_static_nodes':b.graph.static_states,
                               'a2_graph_bytes_approx':total_bytes((a.graph.nodes,a.graph.edges,a.graph.parents,a.graph.affected)),
                               'dynamic_graph_bytes_approx':total_bytes((b.graph.nodes,b.graph.edges,b.graph.parents,b.graph.affected))})
            for e in grouped[case.key]:
                locks=tuple((int(i),str(s)) for i,s in e['locks'])
                order=['a2','dyn','full']
                random.Random(seed+rep*1237+j*107+e['step']).shuffle(order)
                timings={}; results={}; stats={}
                for name in order:
                    started=time.perf_counter_ns()
                    if name=='a2': result,st=a.update(locks)
                    elif name=='dyn': result,st=b.update(locks)
                    else: result,ns=a.graph.full_recompute(locks);st=ns
                    timings[name]=time.perf_counter_ns()-started
                    results[name]=result
                    stats[name]=st
                reference=composed_dp(a.graph._with_locks(locks))
                checks={(r.status,r.solution) for r in (*results.values(),reference)}
                if len(checks)!=1:
                    raise AssertionError('Mismatch on '+case.key+' step '+str(e['step'])+' '+str(checks))
                winner=results['a2']
                if winner.solution and not verify_solution(a.graph._with_locks(locks),winner.solution):
                    raise AssertionError('Independent witness failure')
                ast=stats['a2'];dst=stats['dyn']
                out.append({'repeat':rep,'case_id':case.key,'case_family':entry['family'],
                            'step':e['step'],'edit_family':e['family'],
                            'n_events':len(case.rhythm.events),'n_candidates':len(case.candidates),
                            'status':winner.status,'cost':winner.solution.cost if winner.solution else '',
                            'solution':winner.solution.candidate_key if winner.solution else '',
                            'exact_agreement':True,'a2_ns':timings['a2'],'dyn_ns':timings['dyn'],
                            'full_ns':timings['full'],'a2_states':ast.recomputed_states,
                            'a2_edges':ast.edges_scanned,'dyn_vertices_settled':dst.settled_vertices,
                            'dyn_rhs_evaluations':dst.rhs_evaluations,'dyn_edges':dst.scanned_edges,
                            'dyn_queue_pops':dst.queue_pops,'dyn_peak_heap':dst.peak_heap,
                            'full_states':stats['full'],'full_edges':results['full'].expansions})
    output.mkdir(parents=True,exist_ok=True)
    with (output/'CASE_LEVEL_RESULTS.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    with (output/'MEMORY_SAMPLES.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(memory[0]));w.writeheader();w.writerows(memory)
    deterministic=[{k:v for k,v in row.items() if not k.endswith('_ns')} for row in out]
    (output/'DETERMINISTIC_RESULTS.json').write_bytes(canonical(deterministic))
    families={}
    for fam in ('single','multi','wide','clear'):
        subset=[r for r in out if r['edit_family']==fam]
        families[fam]={
            'operations':len(subset),
            'a2_median_ms':round(statistics.median(r['a2_ns'] for r in subset)/1e6,4),
            'dyn_median_ms':round(statistics.median(r['dyn_ns'] for r in subset)/1e6,4),
            'full_median_ms':round(statistics.median(r['full_ns'] for r in subset)/1e6,4),
            'a2_state_ratio':round(sum(r['a2_states'] for r in subset)/sum(r['full_states'] for r in subset),4),
            'dyn_settled_ratio':round(sum(r['dyn_vertices_settled'] for r in subset)/sum(r['full_states'] for r in subset),4),
            'a2_edges_ratio':round(sum(r['a2_edges'] for r in subset)/sum(r['full_edges'] for r in subset),4),
            'dyn_edges_ratio':round(sum(r['dyn_edges'] for r in subset)/sum(r['full_edges'] for r in subset),4),
            'sum_ms':{key:round(sum(r[key+'_ns'] for r in subset)/1e6,3) for key in ('a2','dyn','full')},
        }
    summary={
        'protocol':data['protocol'],'frozen_sha256':hashlib.sha256(raw).hexdigest(),
        'prospective_formal_cases':len(data['cases']),'edit_operations_per_repeat':len(data['edits']),
        'timing_repeats':reps,'total_comparisons':len(out),
        'deterministic_results_sha256':hashlib.sha256(canonical(deterministic)).hexdigest(),
        'all_methods_and_independent_dp_agree':True,
        'algorithm_comparison':'optimized static DAG DP vs A2 path-value invalidation vs independent g/rhs dynamic-SSSP (LPA-style full consistency)',
        'families':families,
        'memory_samples':len(memory),
        'approx_cache_memory_median_kib':{
          'a2':round(statistics.median(x['a2_cache_bytes_approx'] for x in memory)/1024,2),
          'dynamic':round(statistics.median(x['dynamic_cache_bytes_approx'] for x in memory)/1024,2)},
        'memory_methods_limitations':'Approximate Python in-process object sizes, not peak RSS; graph shared structural costs shown separately.',
        'no_real_pronunciation_or_music_data':True,'no_novelty_claim':True,
        'timings_environment_dependent':True,'full_published_LPA_source_not_reimplemented':True,
        'prior_art_caveat':'LPA-inspired specialization is not claimed bit-for-bit identical to paper implementation',
    }
    (output/'SUMMARY.json').write_bytes(canonical(summary))
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--frozen',type=Path,default=Path('reports/research/track_a3/FROZEN_CASES_AND_EDITS.json'))
    p.add_argument('--output',type=Path,default=Path('reports/research/track_a3'))
    p.add_argument('--repeats',type=int,default=1)
    a=p.parse_args();print(json.dumps(analyze(a.frozen,a.output,reps=a.repeats),indent=2))
if __name__=='__main__':main()
