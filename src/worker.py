"""Isolated per-run process; complete raw events, native logs, independent candidates."""
from pathlib import Path
import argparse, json, time, math, hashlib, gzip, io, sys
sys.dont_write_bytecode = True
from .model import build, peak_rss
from .independent_check import verify
from ortools.sat.python import cp_model
import ortools
OUT = Path(__file__).resolve().parents[1]

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')

def run(job):
    if job['method'] not in ('B0', 'B1'):
        raise ValueError('This release supports B0 and B1.')
    job = dict(job)
    for field in ('input', 'output'):
        path = (OUT / job[field]).resolve()
        if not path.is_relative_to(OUT):
            raise ValueError(f'{field} must be inside the repository.')
        job[field] = path.relative_to(OUT).as_posix()
    if not (OUT / job['output']).resolve().is_relative_to((OUT / 'runs').resolve()):
        raise ValueError('Write run outputs under runs/.')
    start = time.perf_counter()
    dest = Path(job['output'])
    assert dest.resolve().is_relative_to(OUT)
    dest.mkdir(parents=True, exist_ok=False)
    payload = json.loads(Path(job['input']).read_text(encoding='utf-8-sig'))
    h = job['h']
    metric = job.get('metric', 'D10')
    order = job.get('order', [0, 1, 2, 3, 4])
    deadline = start + job['budget_s']
    events = []
    bound_events = []
    calls = []
    check_s = 0.0
    best = None
    prefix = 0
    stats = {}
    stop = None

    def key(v):
        return tuple((v[j] for j in order))

    def accept(actions, source):
        nonlocal check_s, best
        t = time.perf_counter()
        v = verify(payload, h, actions, metric=metric)
        check_s += time.perf_counter() - t
        elapsed = time.perf_counter() - start
        if elapsed <= job['budget_s'] and (best is None or key(v) < key(best['vector'])):
            best = {'vector': list(v), 'actions': actions.copy(), 'elapsed_s': elapsed, 'source': source}
            events.append({'event': 'verified_candidate', 'elapsed_s': elapsed, 'vector': list(v), 'source': source})
            return True
        return False
    accept({p['equipment_id']: ['CANCEL', 0] for p in payload['plans']}, 'shared_all_CANCEL_no_hint')
    baseline = job['method']
    native_status = 'NOT_CALLED'
    scalar_optimal = False
    try:
        m, x, expr, scalar, groups, ss, stats = build(payload, h, metric, order, deadline, job.get('encoding', 'cell'))
        (dest / 'initial_model.pbtxt.gz').write_bytes(gzip.compress(str(m.proto).encode(), mtime=0))
        if baseline == 'B0':
            targets = [(['R', 'A', 'CA', 'CB', metric][j], expr[j]) for j in order]
        else:
            targets = [('strict_scalar', scalar)]
        for stage, (name, obj) in enumerate(targets):
            remaining = deadline - time.perf_counter() - 0.05
            if remaining <= 0.005:
                stop = 'TIMEOUT'
                break
            m.minimize(obj)
            error = m.validate()
            assert not error, error
            solver = cp_model.CpSolver()
            solver.parameters.num_search_workers = job.get('workers', 2)
            solver.parameters.random_seed = job['seed']
            solver.parameters.max_time_in_seconds = remaining
            solver.parameters.absolute_gap_limit = 0
            solver.parameters.relative_gap_limit = 0
            solver.parameters.log_search_progress = True
            solver.parameters.log_to_stdout = False
            log = io.StringIO()
            solver.log_callback = log.write

            def extract(value):
                a = {}
                for p, g in zip(payload['plans'], groups):
                    chosen = [s for s in g if value(x[s.sid])]
                    assert len(chosen) == 1
                    a[p['equipment_id']] = [chosen[0].kind, chosen[0].delta]
                accept(a, name)

            class CB(cp_model.CpSolverSolutionCallback):

                def on_solution_callback(self):
                    if time.perf_counter() >= deadline - 0.01:
                        self.stop_search()
                        return
                    extract(self.value)

            def newbound(v):
                elapsed = time.perf_counter() - start
                bound_events.append({'elapsed_s': elapsed, 'objective': name, 'fixed_prefix': prefix, 'raw_bound': v, 'eligible': elapsed <= job['budget_s']})
            solver.best_bound_callback = newbound
            t = time.perf_counter()
            code = solver.solve(m, CB())
            end = time.perf_counter()
            native_s = end - t
            native_status = solver.status_name(code)
            found = code in (cp_model.FEASIBLE, cp_model.OPTIMAL)
            if found and time.perf_counter() < deadline - 0.002:
                extract(solver.value)
            raw = float(solver.best_objective_bound) if code != cp_model.MODEL_INVALID else None
            lb = max(0, math.ceil(math.nextafter(raw, -math.inf) - 1e-06)) if raw is not None and math.isfinite(raw) else None
            exact_value = int(solver.value(obj)) if found else None
            eligible = end <= deadline
            closed = code == cp_model.OPTIMAL and eligible and (lb == exact_value)
            call = {'objective': name, 'native_status': native_status, 'native_s': native_s, 'solver_wall_s': solver.wall_time, 'objective_value_exact': exact_value, 'objective_value_float_diagnostic': float(solver.objective_value) if found else None, 'raw_bound': raw, 'integer_bound': lb, 'eligible_native_return': eligible, 'elapsed_end_s': end - start, 'closed': closed, 'parameters': str(solver.parameters), 'branches': solver.num_branches, 'conflicts': solver.num_conflicts}
            calls.append(call)
            (dest / f'{stage}_{name}.log').write_text(log.getvalue(), encoding='utf-8')
            (dest / f'{stage}_response.pbtxt').write_text(str(solver.response_proto), encoding='utf-8')
            if closed:
                if baseline == 'B0':
                    prefix += 1
                    m.add(obj == exact_value)
                elif baseline == 'B1':
                    prefix = 5
                else:
                    scalar_optimal = True
            else:
                stop = 'TIMEOUT' if not eligible or time.perf_counter() >= deadline - 0.1 else 'NATIVE_' + native_status
                break
        if prefix == 5:
            stop = 'OPTIMAL_FULL_LEX'
        elif scalar_optimal:
            stop = 'OPTIMAL_BALANCED_POLICY'
    except TimeoutError as e:
        stop = 'TIMEOUT_BUILD'
        stats['build_timeout_reason'] = str(e)
    except Exception as e:
        import traceback
        stop = 'ERROR'
        stats['error'] = repr(e)
        (dest / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
    t = time.perf_counter()
    assert best is not None
    assert verify(payload, h, best['actions'], metric=metric) == tuple(best['vector'])
    final_check = time.perf_counter() - t
    elapsed = time.perf_counter() - start
    if prefix == 5:
        assert best['source'] != 'shared_all_CANCEL_no_hint' or best['vector'] == [0, 0, 0, 0, 0]
    rbounds = [max(0, math.ceil(math.nextafter(e['raw_bound'], -math.inf) - 1e-06)) for e in bound_events if e['objective'] == 'R' and e['eligible']]
    if prefix and baseline == 'B0':
        rlb = best['vector'][0]
        rsource = 'CERTIFIED_PREFIX'
    elif prefix == 5 and baseline == 'B1' and (order[0] == 0):
        rlb = best['vector'][0]
        rsource = 'FULL_LEX_CERTIFICATE'
    else:
        rlb = max([0] + rbounds) if baseline == 'B0' and order[0] == 0 else 0
        rsource = 'R_NATIVE_BOUND' if rbounds and baseline == 'B0' else 'DOMAIN_BOUND'
    assert rlb <= best['vector'][0]
    checkpoints = []
    for cp in job.get('checkpoints', [5, 15, 30]):
        if elapsed >= cp:
            ev = [e for e in events if e['elapsed_s'] <= cp]
            checkpoints.append({'time_s': cp, 'vector': ev[-1]['vector'] if ev else None, 'source': 'recorded verified event at/before checkpoint', 'last_event_s': ev[-1]['elapsed_s'] if ev else None})
    code_sha = {p.name: digest(p) for p in Path(__file__).parent.glob('*.py')}
    result = {'run_id': job['run_id'], 'label': job['label'], 'job': job, 'instance_id': payload['instance_id'], 'N': len(payload['plans']), 'H': payload['horizon'], 'h': h, 'metric': metric, 'order': order, 'input_sha256': digest(job['input']), 'code_sha256': code_sha, 'method': baseline, 'seed': job['seed'], 'workers': job.get('workers', 2) if baseline != 'B2' else 1, 'budget_s': job['budget_s'], 'candidate': best, 'closed_prefix': prefix, 'full_lex_certified': prefix == 5, 'balanced_policy_certified': scalar_optimal, 'native_status': native_status, 'protocol_stop': stop or 'INCOMPLETE', 'R_UB': best['vector'][0], 'R_LB': rlb, 'R_LB_source': rsource, 'R_gap': best['vector'][0] - rlb, 'calls': calls, 'stats': stats, 'candidate_check_s_in_native_and_build': check_s, 'final_independent_check_s': final_check, 'native_call_wall_s': sum((c['native_s'] for c in calls)), 'computational_wall_s': elapsed, 'peak_rss_mb': peak_rss(), 'events': events, 'bound_events': bound_events, 'checkpoints': checkpoints, 'environment': {'python': sys.version, 'ortools': ortools.__version__}, 'warning': 'scalar bounds are not component bounds; prefix0 balanced optimum is a different policy; computational/native costs overlap, parent process wall reported separately'}
    save(dest / 'actions.json', best['actions'])
    save(dest / 'result.json', result)
    print(job['run_id'], result['protocol_stop'], best['vector'], 'prefix', prefix, 'native', round(result['native_call_wall_s'], 3), flush=True)
    return result
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    a = ap.parse_args()
    run(json.loads(Path(a.job).read_text(encoding='utf-8')))
