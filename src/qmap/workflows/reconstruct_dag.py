"""Reconstruct observed QELF execution DAGs from QMAP JSONL traces.

Standard library plus Graphviz `dot` for image rendering. Uses observed events,
not the reference QELF labels. Unknown provider timing is never estimated.

Usage:
  python src/qmap/workflows/reconstruct_dag.py TRACE.jsonl --outdir outputs
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

PHASES = {"transpilation_completed": "transpilation_ms",
          "job_submission_completed": "submission_ms",
          "result_wait_completed": "result_wait_ms",
          "result_decoding_completed": "decode_ms"}


def load_events(path: Path) -> list[dict[str, Any]]:
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not events:
        raise ValueError('Empty trace')
    ids = {e.get('run_id') for e in events}
    if len(ids) != 1:
        raise ValueError('Trace contains multiple run IDs')
    offsets = [e['monotonic_offset_ns'] for e in events]
    if any(b < a for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Events are not ordered by monotonic offset')
    return events


def infer_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    run_id = events[0].get('run_id')
    nodes: dict[str, dict[str, Any]] = {}
    edges: set[tuple[str, str, str]] = set()
    submissions = []
    active: dict[str, Any] | None = None
    semantic_structure: dict[str, Any] = {}
    energy_by_task = {}

    def ensure_node(tid: str, kind: str='task') -> dict[str, Any]:
        return nodes.setdefault(tid, {'id':tid, 'type':kind, 'dependencies':[], 'ready_ms':None,
                                      'start_ms':None,'end_ms':None, 'metadata':{}})

    for e in events:
        event=e['event']; data=e.get('data') or {}; tid=e.get('task_id')
        ms=e['monotonic_offset_ns']/1e6
        if event == 'semantic_event':
            name=data.get('semantic_name'); attrs=data.get('attributes') or {}
            if name=='workflow_structure': semantic_structure=attrs
            if name in ('task_dependency','optimizer_objective_ready'):
                t=attrs.get('task_id') or attrs.get('objective_evaluation_id')
                if t:
                    nd=ensure_node(t, attrs.get('kind') or ('objective' if name=='optimizer_objective_ready' else 'task'))
                    nd['metadata'].update({k:v for k,v in attrs.items() if k not in ('task_id','dependency_ids')})
                    nd['dependencies']=list(attrs.get('dependency_ids') or [])
                    for dep in nd['dependencies']:edges.add((dep,t,'depends_on'))
            if name=='objective_result_consumed':
                t=attrs.get('objective_evaluation_id')
                if t: energy_by_task[t]=attrs.get('measured_energy')
        if event=='task_ready' and tid:
            nd=ensure_node(tid,data.get('kind','task'));nd['ready_ms']=ms
            for dep in data.get('dependency_ids',[]):
                if dep not in nd['dependencies']:nd['dependencies'].append(dep)
                edges.add((dep,tid,'depends_on'))
        if event=='task_started' and tid:
            nd=ensure_node(tid,data.get('kind','task'));nd['start_ms']=ms
        if event=='task_completed' and tid:
            nd=ensure_node(tid, data.get('kind','task'));nd['end_ms']=ms
            if e.get('job_id'): nd['job_id']=e['job_id']
            if data.get('measured_energy') is not None: energy_by_task[tid]=data['measured_energy']
            if data.get('elapsed_ms') is not None:nd['measured_classical_duration_ms']=data['elapsed_ms']
        if event=='submission_started':
            if active:raise ValueError('Nested submissions not supported by this v0.1 reconstruction')
            active={'id':f"dispatch_{len(submissions)}", 'task_ids':list(data.get('task_ids') or []),
                    'circuit_count':data.get('circuit_count'), 'start_ms':ms,'phases_ms':{},
                    'provider_queue_ms':None,'provider_execution_ms':None,'job_id':None}
        if active:
            if event in PHASES:
                active['phases_ms'][PHASES[event]]=data.get('elapsed_ms')
            if e.get('job_id'):
                active['job_id']=e['job_id']
            if event=='submission_completed':
                active['end_ms']=ms
                active['elapsed_client_ms']=data.get('elapsed_client_ms')
                active['provider_queue_ms']=data.get('provider_queue_ms')
                active['provider_execution_ms']=data.get('provider_execution_ms')
                active['raw_provider_metadata']=data.get('provider_metadata',{})
                if not active['task_ids']:active['task_ids']=list(data.get('task_ids') or [])
                for t in active['task_ids']:
                    ensure_node(t)
                    edges.add((t,active['id'],'bundled_into'))
                submissions.append(active);active=None
    if active:raise ValueError('Trace ended with unfinished submission')
    for t in nodes.values():
        if t['id'] in energy_by_task:t['metadata']['measured_energy']=energy_by_task[t['id']]
        if t['type']=='task':
            if t['id'].startswith('q'): t['type']='quantum_circuit'
            elif t['id'].startswith('objective_'):t['type']='objective'
            elif t['id']=='reduce':t['type']='classical_reduction'
    # Use task-level dependencies; never connect a dispatch to an optimizer successor
    # without observed dependency evidence.
    for nd in nodes.values():
        for dep in nd['dependencies']:edges.add((dep,nd['id'],'depends_on'))
    completed = [e for e in events if e['event']=='workflow_completed']
    graph={'schema':'qmap-observed-dag-0.1', 'run_id':run_id,
           'workflow':events[0].get('workflow'), 'policy':events[0].get('policy'),
           'backend':events[0].get('backend'), 'execution_mode':events[0].get('execution_mode'),
           'workflow_makespan_ms':(completed[-1]['data'].get('makespan_ms') if completed else None),
           'semantic_structure':semantic_structure,
           'nodes':sorted(nodes.values(),key=lambda x:(int(re.search(r'\d+$',x['id']).group()) if re.search(r'\d+$',x['id']) else 1e6,x['id'])),
           'dispatches':submissions,
           'edges':[{'source':s,'target':t,'type':k} for s,t,k in sorted(edges)],
           'timing_provenance':{'transpilation_ms':'client-measured', 'submission_ms':'client-measured',
                               'result_wait_ms':'client-measured, includes queue/execution/transport',
                               'provider_queue_ms':'not available unless explicitly measured',
                               'provider_execution_ms':'not available unless explicitly measured'},
           'limitations':['Quantum circuits sharing one job share job-level timing; no per-circuit QPU service time is inferred.',
                          'Classical optimizer calculation time is not separated unless emitted as its own task/span.',
                          'The DAG reflects declared/logged dependencies, not an inferred physical scheduler DAG.']}
    return graph


def esc(s: Any) -> str:
    return str(s).replace('"','\\"').replace('\n','\\n')


def fmt_ms(value: Any) -> str:
    if value is None:return 'unknown'
    return f'{value/1000:.2f} s' if value>=1000 else f'{value:.1f} ms'


def to_dot(graph:dict[str,Any], *, expand:bool=True)->str:
    nodes={x['id']:x for x in graph['nodes']}
    ds=graph['dispatches']; lines=['digraph Workflow {',
        'graph [rankdir=LR, bgcolor="white", pad="0.22", nodesep="0.40", ranksep="0.65", fontname="Helvetica", labelloc=t];',
        'node [fontname="Helvetica", fontsize=11, shape=box, style="rounded,filled", color="#A7B8BD", fillcolor="#F2F7F7", margin="0.16,0.12"];',
        'edge [color="#6D7E82", arrowsize=0.7, penwidth=1.25];']
    label=f"{graph['workflow']} | {graph['policy']} | {graph['backend']} | makespan {fmt_ms(graph['workflow_makespan_ms'])}"
    lines.append(f'label="{esc(label)}";')
    if any(x['id'].startswith('objective_') for x in graph['nodes']):
        lines.append('graph [rankdir=TB, nodesep="0.18", ranksep="0.26"];')
    # The QOOL DAG is naturally a chain of objective nodes. Job timing shown in each objective.
    is_qool=any(x['id'].startswith('objective_') for x in graph['nodes'])
    if is_qool:
        by_tid={t: d for d in ds for t in d['task_ids']}
        for nd in graph['nodes']:
            tid=nd['id']; d=by_tid.get(tid)
            energy=nd['metadata'].get('measured_energy'); en=f' | E={energy:.3f}' if isinstance(energy,(int,float)) else ''
            if d:
                p=d['phases_ms']; text=(f'{tid}{en}\\n2 measurement bases | 1 job\\n'
                      f"compile {fmt_ms(p.get('transpilation_ms'))}  |  submit {fmt_ms(p.get('submission_ms'))}\\n"
                      f"wait {fmt_ms(p.get('result_wait_ms'))}  |  QPU time unknown")
            else:text=tid
            lines.append(f'"{esc(tid)}" [label="{esc(text)}", fillcolor="#E7F3EF", color="#428D70"];')
        for ed in graph['edges']:
            if ed['type']=='depends_on' and ed['source'] in nodes and ed['target'] in nodes:
                lines.append(f'"{esc(ed["source"])}" -> "{esc(ed["target"])}" [label="feedback dependency", fontsize=8];')
    else:
        for nd in graph['nodes']:
            tid=nd['id']; typ=nd['type']
            text=tid
            if typ=='classical_reduction':
                dur=nd.get('measured_classical_duration_ms');text+=f'\\nclassical reduction: {fmt_ms(dur)}'
            else:text+='\\nquantum circuit'
            fill='#EEF1F3' if typ=='classical_reduction' else '#E7F3EF'
            lines.append(f'"{esc(tid)}" [label="{esc(text)}", fillcolor="{fill}"];')
        for d in ds:
            p=d['phases_ms'];job=d.get('job_id') or '(unknown)'
            text=(f"Job {d['id']} | {len(d['task_ids'])} circuits\\n"
                  f"compile {fmt_ms(p.get('transpilation_ms'))} | submit {fmt_ms(p.get('submission_ms'))}\\n"
                  f"wait {fmt_ms(p.get('result_wait_ms'))} | QPU time unknown\\n"
                  f"job ID {job[:12]}…")
            lines.append(f'"{esc(d["id"])}" [label="{esc(text)}", fillcolor="#E6F0FA", color="#6185A4"];')
        drawn_dependencies=set()
        for ed in graph['edges']:
            if ed['type']=='bundled_into':
                lines.append(f'"{esc(ed["source"])}" -> "{esc(ed["target"])}" [color="#6A9EBE"];')
            elif ed['type']=='depends_on':
                # If target has prerequisite quantum tasks, show dependency from the job(s)
                # carrying that work; otherwise use direct dependency.
                src=ed['source']; trg=ed['target']
                dsrc=[d['id'] for d in ds if src in d['task_ids']]
                for s in dsrc or [src]:
                    if (s,trg) not in drawn_dependencies:
                        lines.append(f'"{esc(s)}" -> "{esc(trg)}";')
                        drawn_dependencies.add((s,trg))
    lines.append('}')
    return '\n'.join(lines)



# v0.2: Detailed execution view. Leave infer_graph and its scientific model
# backward compatible with v0.1. A phase interval is *client observed*.
PHASE_EVENT_PAIRS = (
    ('transpilation', 'transpilation_started', 'transpilation_completed'),
    ('submission', 'job_submission_started', 'job_submission_completed'),
    ('result_wait', 'result_wait_started', 'result_wait_completed'),
    ('decoding', 'result_decoding_started', 'result_decoding_completed'),
)


def execution_view(events: list[dict[str, Any]], graph: dict[str, Any]) -> dict[str, Any]:
    """Construct a per-job phase graph from actual event pairs (no fabricated times).

    Provider queue and QPU execution are modeled as *unknown components within*
    result_wait, not as extra serial durations added to makespan.
    """
    result = {'schema': 'qmap-execution-dag-0.2', 'run_id': graph['run_id'],
              'workflow': graph['workflow'], 'backend': graph['backend'],
              'policy': graph['policy'], 'workflow_makespan_ms': graph['workflow_makespan_ms'],
              'nodes': [], 'edges': [], 'dispatches': [],
              'timing_note': 'Client durations only. Provider queue/QPU times are unknown and lie within the unresolved result-wait interval.',
              'limitations': graph['limitations']}
    active = None
    dispatch_idx = 0
    for e in events:
        name = e.get('event'); data = e.get('data') or {}
        offset = e['monotonic_offset_ns'] / 1e6
        if name == 'submission_started':
            if active is not None: raise ValueError('Overlapping submissions not supported')
            active = {'id': f'dispatch_{dispatch_idx}', 'task_ids': data.get('task_ids', []),
                      'circuit_count': data.get('circuit_count'), 'job_id': None,
                      'phase_starts': {}, 'stages': [], 'start_ms': offset}
            dispatch_idx += 1
        if active is None: continue
        for phase, start, end in PHASE_EVENT_PAIRS:
            if name == start: active['phase_starts'][phase] = offset
            if name == end:
                started = active['phase_starts'].pop(phase, None)
                if started is None: raise ValueError(f'Missing start event for {phase}')
                elapsed = offset - started
                reported = data.get('elapsed_ms')
                stage = {'id':f"{active['id']}:{phase}", 'kind':'runtime_stage',
                         'stage':phase, 'start_offset_ms':started, 'end_offset_ms':offset,
                         'duration_ms':float(reported) if isinstance(reported,(int,float)) else elapsed,
                         'provenance':'client_measured', 'clock_domain':'client_monotonic'}
                active['stages'].append(stage)
        if name == 'submission_completed':
            if active['phase_starts']:raise ValueError('Unfinished phase events')
            active['job_id'] = e.get('job_id')
            active['end_ms'] = offset
            stages = active['stages']; prefix = active['id']
            result['nodes'].extend(stages)
            for left,right in zip(stages,stages[1:]):
                result['edges'].append({'source':left['id'],'target':right['id'],'kind':'observed_order'})
            # Unknown components are *nested explanatory placeholders*, not
            # schedulable nodes or independently timed phases.
            wait = next((x for x in stages if x['stage']=='result_wait'), None)
            active['provider_breakdown'] = {
                'container_stage_id':wait['id'] if wait else None,
                'queue_duration_ms':None, 'qpu_execution_duration_ms':None,
                'result_transport_duration_ms':None,
                'status':'unresolved_within_client_result_wait'}
            active.pop('phase_starts')
            result['dispatches'].append(active)
            active = None
    if active is not None:raise ValueError('Incomplete dispatch')
    # Preserve the high-level semantic/task dependency graph independently.
    result['scientific_nodes'] = graph['nodes']
    result['scientific_edges'] = [x for x in graph['edges'] if x['type']=='depends_on']
    return result


def execution_dot(graph: dict[str, Any]) -> str:
    """Two levels: scientific task dependency and observed runtime stages."""
    lines = ['digraph Workflow {',
             'graph [rankdir=TB, bgcolor="white", pad="0.30", nodesep="0.22", ranksep="0.30", fontname="Helvetica", labelloc=t];',
             'node [fontname="Helvetica", fontsize=11, shape=box, style="rounded,filled", color="#9AACB0", fillcolor="#F3F7F7", margin="0.15,0.10"];',
             'edge [color="#62777A", arrowsize=0.65];']
    label=f"SYSTEMS EXECUTION | {graph['workflow']} | {graph['policy']} | {fmt_ms(graph['workflow_makespan_ms'])}"
    lines.append(f'label="{esc(label)}";')
    objs = {n['id']: n for n in graph['scientific_nodes']}
    is_qool = any(t.startswith('objective_') for t in objs)
    # For multiple QOOL evaluations make a clear serial feedback chain of
    # compact subgraphs; cluster stage nodes per job.
    for d in graph['dispatches']:
        i = d['id'].split('_')[-1]
        tasks = ', '.join(d.get('task_ids') or [])
        job = (d.get('job_id') or 'unknown')[:12]
        header = f"{tasks or d['id']} | {d.get('circuit_count') or '?'} circuit(s) | job {job}…"
        lines.append(f'subgraph "cluster_{i}" {{')
        lines.append(f'label="{esc(header)}"; fontsize=10; fontname="Helvetica"; color="#B8CBCD"; style="rounded";')
        task_id = f"{d['id']}:prep"
        prep = 'Prepare parameters / construct circuits' if is_qool else 'Circuit preparation (not separately timed)'
        lines.append(f'"{task_id}" [label="{esc(prep)}\\nDuration unavailable", fillcolor="#EDF0F2", style="rounded,filled,dashed"];')
        stages=d['stages'];prev=task_id
        for n in stages:
            st=n['stage']; desc={'transpilation':'Compile / transpile', 'submission':'Submit (client call)',
                'result_wait':'Await result (composite)', 'decoding':'Decode measurement counts'}[st]
            c='#E3F0FA' if st in ('transpilation','submission') else ('#FFF4DC' if st=='result_wait' else '#F0F2F4')
            note = '\\nIncludes queue, QPU, polling, transport' if st=='result_wait' else ''
            msg=f"{desc}\\n{fmt_ms(n['duration_ms'])} (client){note}"
            lines.append(f'"{n["id"]}" [label="{esc(msg)}", fillcolor="{c}"];')
            lines.append(f'"{prev}" -> "{n["id"]}";');prev=n['id']
        post=f"{d['id']}:post"
        postlabel='Energy estimate + optimizer update' if is_qool else 'Classical reduction / result consumption'
        lines.append(f'"{post}" [label="{postlabel}\\nNot separately timed here", fillcolor="#EDF0F2", style="rounded,filled,dashed"];')
        lines.append(f'"{prev}" -> "{post}";')
        lines.append('}')
    # Only draw inter-job dependencies when declared in scientific graph.
    task_dispatch = {t: d['id'] for d in graph['dispatches'] for t in d['task_ids']}
    drawn=set()
    for e in graph['scientific_edges']:
        a=task_dispatch.get(e['source']);b=task_dispatch.get(e['target'])
        if a and b and a!=b and (a,b) not in drawn:
            lines.append(f'"{a}:post" -> "{b}:prep" [color="#008A70", penwidth=2, label="feedback dependency", fontsize=9];')
            drawn.add((a,b))
    # Explicit note: there is no measured queue/QPU split.
    lines.append('"unknown" [label="Provider queue time: unavailable\\nPhysical QPU service time: unavailable\\nBoth unresolved within result-wait", shape=note, style="filled", fillcolor="#FFF8E9", color="#C9A35A", fontsize=10];')
    if graph['dispatches']:
        lines.append(f'"{graph["dispatches"][0]["id"]}:result_wait" -> "unknown" [style=dotted, arrowhead=none, constraint=false];')
    lines.append('}')
    return '\n'.join(lines)


def produce(trace:Path, outdir:Path, view:str='both')->list[Path]:
    events=load_events(trace); scientific=infer_graph(events)
    execution=execution_view(events,scientific)
    outdir.mkdir(parents=True,exist_ok=True); results=[]
    for kind in (('scientific','systems') if view=='both' else (view,)):
        graph=scientific if kind=='scientific' else execution
        prefix=outdir / f'{trace.stem}.{kind}'
        js=outdir / f'{trace.stem}.{kind}.dag.json'
        js.write_text(json.dumps(graph,indent=2)+'\n', encoding='utf-8')
        dot=outdir / f'{trace.stem}.{kind}.dot'
        dot.write_text((to_dot(scientific) if kind=='scientific' else execution_dot(execution))+'\n', encoding='utf-8')
        results.extend([js,dot])
        if shutil.which('dot'):
            for ext in ('png','svg'):
                target=outdir / f'{trace.stem}.{kind}.{ext}'
                subprocess.run(['dot',f'-T{ext}',str(dot),'-o',str(target)],check=True)
                results.append(target)
        else: print('Graphviz not found; JSON and DOT available.',flush=True)
    return results


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces',type=Path,nargs='+')
    parser.add_argument('--outdir',type=Path,default=Path('results/qelf_dags'))
    parser.add_argument('--view',choices=['scientific','systems','both'],default='both')
    args=parser.parse_args()
    for trace in args.traces:
        for result in produce(trace,args.outdir,args.view):print(result)

if __name__=='__main__':main()
