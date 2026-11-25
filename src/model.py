"""Full atomic state domain with exact Cell and Pairwise encodings."""
from dataclasses import dataclass
from collections import defaultdict
import time, ctypes, os
from itertools import combinations
from ortools.sat.python import cp_model

@dataclass(frozen=True, slots=True)
class State:
    sid: int
    owner: int
    kind: str
    delta: int
    f0: int
    f1: int
    times: tuple
    cost: tuple

def domains(payload, h, metric='D10'):
    ss = []
    groups = []
    H = payload['horizon']
    for i, p in enumerate(payload['plans']):
        assert all((type(p[k]) is int for k in ['f0', 'f1', 't0', 't1', 'gap', 'count']))
        assert p['category'] in ('A', 'B', 'C') and p['f1'] > p['f0'] and (p['t1'] > p['t0']) and (p['count'] >= 1)
        choices = [('KEEP', 0), ('CANCEL', 0)] + [('FREQ', d) for d in range(-10, 11) if d] + [('TIME', d) for d in range(-5, 6) if d] + ([('INTERVAL', d) for d in range(-h, h + 1) if d] if p['category'] == 'C' else [])
        g = []
        for kind, d in choices:
            f0 = p['f0'] + (d if kind == 'FREQ' else 0)
            f1 = p['f1'] + (d if kind == 'FREQ' else 0)
            t = p['t0'] + (d if kind == 'TIME' else 0)
            gap = p['gap'] + (d if kind == 'INTERVAL' else 0)
            dur = p['t1'] - p['t0']
            if kind != 'CANCEL' and (not (0 <= f0 < f1 <= 100 and t >= 0 and (gap >= 0) and (t + (p['count'] - 1) * (dur + gap) + dur <= H))):
                continue
            times = () if kind == 'CANCEL' else tuple(((t + k * (dur + gap), t + k * (dur + gap) + dur) for k in range(p['count'])))
            v = abs(d) * (2 if kind == 'TIME' else 1) if kind not in ('KEEP', 'CANCEL') else 0
            if metric == 'SUM_TIME':
                v = p['count'] * abs(d) if kind == 'TIME' else p['count'] * (p['count'] - 1) * abs(d) // 2 if kind == 'INTERVAL' else 0
            if metric == 'MAX_TIME':
                v = abs(d) if kind == 'TIME' else (p['count'] - 1) * abs(d) if kind == 'INTERVAL' else 0
            cost = (int(kind == 'CANCEL'), int(kind not in ('KEEP', 'CANCEL')), int(kind != 'KEEP' and p['category'] == 'A'), int(kind != 'KEEP' and p['category'] == 'B'), v)
            s = State(len(ss), i, kind, d, f0, f1, times, cost)
            ss.append(s)
            g.append(s)
        groups.append(g)
    assert len({p['equipment_id'] for p in payload['plans']}) == len(groups)
    return (groups, ss)

def weights(U):
    W = [1] * 5
    for j in range(3, -1, -1):
        W[j] = 1 + sum((W[k] * U[k] for k in range(j + 1, 5)))
    assert max(W) <= 2 ** 63 - 1 and sum((w * u for w, u in zip(W, U))) <= 2 ** 63 - 1
    return W

def build_cell(payload, h, metric, order, deadline):
    t = time.perf_counter()
    groups, ss = domains(payload, h, metric)
    state_s = time.perf_counter() - t
    t = time.perf_counter()
    H = payload['horizon']
    index = {}
    owners = [sum((1 << s.sid for s in g)) for g in groups]
    for s in ss:
        bit = 1 << s.sid
        for f in range(s.f0, s.f1):
            for a, b in s.times:
                for v in range(a, b):
                    cell = f * H + v
                    index[cell] = index.get(cell, 0) | bit
        if s.sid % 128 == 0 and time.perf_counter() > deadline - 0.05:
            raise TimeoutError('cell_index_budget')
    masks = set()
    raw = 0
    for mask in index.values():
        if mask & ~owners[ss[(mask & -mask).bit_length() - 1].owner]:
            masks.add(mask)
            raw += 1
    pre_s = time.perf_counter() - t
    t = time.perf_counter()
    m = cp_model.CpModel()
    x = [m.new_bool_var('s' + str(s.sid)) for s in ss]
    for g in groups:
        m.add_exactly_one((x[s.sid] for s in g))
    for k, mask in enumerate(sorted(masks)):
        row = []
        while mask:
            bit = mask & -mask
            row.append(x[bit.bit_length() - 1])
            mask -= bit
        m.add_at_most_one(row)
        if k % 256 == 0 and time.perf_counter() > deadline - 0.05:
            raise TimeoutError('constraint_build_budget')
    expr, scalar, U, W, upper, box = objectives(m, x, groups, ss, metric, order)
    stats = {'state_generation_s': state_s, 'preprocessing_s': pre_s, 'model_build_s': time.perf_counter() - t, 'states': len(ss), 'deleted_states': 0, 'raw_cell_constraints': raw, 'exact_unique_cell_constraints': len(masks), 'indexed_cells': len(index), 'U_canonical': U, 'order': order, 'W_ordered': W, 'feasible_scalar_upper': upper, 'raw_boolean_box_activity_upper': box, 'model_validated': True}
    return (m, x, expr, scalar, groups, ss, stats)

def objectives(m, x, groups, ss, metric, order):
    expr = [sum((s.cost[j] * x[s.sid] for s in ss if s.cost[j])) for j in range(5)]
    U = [sum((max((s.cost[j] for s in g)) for g in groups)) for j in range(5)]
    if metric == 'MAX_TIME':
        U[4] = max((s.cost[4] for s in ss))
        z = m.new_int_var(0, U[4], 'peak_time_shift')
        m.add_max_equality(z, [s.cost[4] * x[s.sid] for s in ss])
        expr[4] = z
    orderedU = [U[j] for j in order]
    W = weights(orderedU)
    coeff = [sum((W[k] * s.cost[j] for k, j in enumerate(order) if not (metric == 'MAX_TIME' and j == 4))) for s in ss]
    box = sum(coeff) + (W[order.index(4)] * U[4] if metric == 'MAX_TIME' else 0)
    upper = sum((u * w for u, w in zip(orderedU, W)))
    assert box <= 2 ** 63 - 1 and max(coeff) <= 2 ** 63 - 1 and (upper < 2 ** 53), 'integer activity or exact-float certificate limit'
    scalar = sum((W[k] * expr[j] for k, j in enumerate(order)))
    assert not m.validate(), m.validate()
    return (expr, scalar, U, W, upper, box)

def build_pairwise(payload, h, metric, order, deadline):
    state_start = time.perf_counter()
    groups, states = domains(payload, h, metric)
    state_s = time.perf_counter() - state_start
    started = time.perf_counter()
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f's{state.sid}') for state in states]
    for group in groups:
        model.add_exactly_one((variables[state.sid] for state in group))
    checked = 0
    exclusions = 0
    for left, right in combinations(groups, 2):
        for first in left:
            for second in right:
                if conflict(first, second):
                    model.add_bool_or([~variables[first.sid], ~variables[second.sid]])
                    exclusions += 1
                checked += 1
                if checked % 256 == 0 and time.perf_counter() > deadline - 0.05:
                    raise TimeoutError('pairwise_constraint_build_budget')
    expr, scalar, bounds, weight, upper, box = objectives(model, variables, groups, states, metric, order)
    stats = {'state_generation_s': state_s, 'preprocessing_s': 0, 'model_build_s': time.perf_counter() - started, 'states': len(states), 'deleted_states': 0, 'pairwise_exclusions': exclusions, 'U_canonical': bounds, 'order': order, 'W_ordered': weight, 'feasible_scalar_upper': upper, 'raw_boolean_box_activity_upper': box, 'model_validated': True}
    return (model, variables, expr, scalar, groups, states, stats)

def build(payload, h, metric, order, deadline, encoding='cell'):
    if encoding not in ('pairwise', 'cell'):
        raise ValueError(f'Unknown encoding: {encoding}')
    if metric not in ('D10', 'SUM_TIME', 'MAX_TIME'):
        raise ValueError(f'Unknown disturbance metric: {metric}')
    if sorted(order) != [0, 1, 2, 3, 4]:
        raise ValueError('order must permute the five canonical coordinate indices')
    if h < 0 or not payload['plans']:
        raise ValueError('A nonnegative flexibility limit and at least one plan are required.')
    constructor = build_cell if encoding == 'cell' else build_pairwise
    return constructor(payload, h, metric, order, deadline)

def conflict(a, b):
    return bool(a.times and b.times and (a.f0 < b.f1) and (b.f0 < a.f1) and any((u < y and v < x for u, x in a.times for v, y in b.times)))

def peak_rss():
    if os.name != 'nt':
        return None

    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('pf', ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in ['peak', 'rss', 'qpp', 'qpp2', 'qnp', 'qnp2', 'pg', 'peakpg']]
    p = PMC()
    p.cb = ctypes.sizeof(p)
    f = ctypes.windll.kernel32.GetCurrentProcess
    f.restype = ctypes.c_void_p
    g = ctypes.windll.psapi.GetProcessMemoryInfo
    g.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
    return p.peak / 1048576 if g(f(), ctypes.byref(p), p.cb) else None
