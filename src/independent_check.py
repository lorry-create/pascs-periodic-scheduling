"""Independent PASCS checker: action reconstruction plus a time sweep; no state/CP imports."""
import itertools, math, time
KINDS = ('KEEP', 'FREQ', 'TIME', 'INTERVAL', 'CANCEL')

def reconstruct(p, choice, H, h):
    kind, delta = choice
    assert kind in KINDS and type(delta) is int
    assert p['category'] in ('A', 'B', 'C') and p['count'] >= 1
    width = p['f1'] - p['f0']
    duration = p['t1'] - p['t0']
    assert width > 0 and duration > 0
    f = p['f0']
    start = p['t0']
    gap = p['gap']
    if kind in ('KEEP', 'CANCEL'):
        assert delta == 0
    if kind == 'FREQ':
        assert 0 < abs(delta) <= 10
        f += delta
    if kind == 'TIME':
        assert 0 < abs(delta) <= 5
        start += delta
    if kind == 'INTERVAL':
        assert p['category'] == 'C' and 0 < abs(delta) <= h
        gap += delta
    rectangles = []
    if kind != 'CANCEL':
        assert 0 <= f and f + width <= 100 and (start >= 0) and (gap >= 0)
        for k in range(p['count']):
            a = start + k * (duration + gap)
            b = a + duration
            assert b <= H
            rectangles.append((a, b, f, f + width))
    changed = kind != 'KEEP'
    adjust = kind not in ('KEEP', 'CANCEL')
    cost = (int(kind == 'CANCEL'), int(adjust), int(changed and p['category'] == 'A'), int(changed and p['category'] == 'B'), abs(delta) * (2 if kind == 'TIME' else 1) if adjust else 0)
    time_sum = p['count'] * abs(delta) if kind == 'TIME' else p['count'] * (p['count'] - 1) * abs(delta) // 2 if kind == 'INTERVAL' else 0
    time_max = abs(delta) if kind == 'TIME' else (p['count'] - 1) * abs(delta) if kind == 'INTERVAL' else 0
    return {'equipment_id': p['equipment_id'], 'action': kind, 'delta': delta, 'category': p['category'], 'resulting_parameters': {'f0': f, 'f1': f + width, 't0': start, 'duration': duration, 'gap': gap, 'count': p['count']} if kind != 'CANCEL' else None, 'rectangles': rectangles, 'contribution': cost, 'time_sum': time_sum, 'time_max': time_max}

def verify(payload, h, actions, detail=False, metric='D10'):
    ids = [p['equipment_id'] for p in payload['plans']]
    assert len(ids) == len(set(ids)) and set(actions) == set(ids)
    rows = [reconstruct(p, actions[p['equipment_id']], payload['horizon'], h) for p in payload['plans']]
    rectangles = sorted(((a, b, f, g, r['equipment_id']) for r in rows for a, b, f, g in r['rectangles']))
    active = []
    conflicts = []
    for a, b, f, g, eid in rectangles:
        active = [r for r in active if r[1] > a]
        for c, d, u, v, other in active:
            if eid != other and f < v and (u < g):
                conflicts.append([eid, other, [a, min(b, d), max(f, u), min(g, v)]])
        active.append((a, b, f, g, eid))
    assert not conflicts, conflicts[:5]
    vector = [sum((r['contribution'][j] for r in rows)) for j in range(5)]
    if metric == 'SUM_TIME':
        vector[4] = sum((r['time_sum'] for r in rows))
    elif metric == 'MAX_TIME':
        vector[4] = max((r['time_max'] for r in rows), default=0)
    else:
        assert metric == 'D10'
    result = {'status': 'PASS', 'vector': vector, 'D': vector[4] / 10 if metric == 'D10' else None, 'metric': metric, 'entity_count': len(rows), 'expanded_rectangles': len(rectangles), 'conflicts': conflicts, 'rows': rows}
    return result if detail else tuple(vector)

def legal_actions(p, H, h):
    choices = [('KEEP', 0), ('CANCEL', 0)] + [('FREQ', d) for d in range(-10, 11) if d] + [('TIME', d) for d in range(-5, 6) if d]
    if p['category'] == 'C':
        choices += [('INTERVAL', d) for d in range(-h, h + 1) if d]
    result = []
    for c in choices:
        try:
            reconstruct(p, c, H, h)
            result.append(c)
        except AssertionError:
            pass
    return result

def exhaustive(payload, h):
    started = time.perf_counter()
    ds = [legal_actions(p, payload['horizon'], h) for p in payload['plans']]
    total = math.prod(map(len, ds))
    assert total <= 500000, total
    best = None
    feasible = 0
    actions = None
    vectors = set()
    for choices in itertools.product(*ds):
        a = {p['equipment_id']: c for p, c in zip(payload['plans'], choices)}
        try:
            v = verify(payload, h, a)
        except AssertionError:
            continue
        feasible += 1
        vectors.add(v)
        if best is None or v < best:
            best = v
            actions = a
    return {'vector': best, 'actions': actions, 'cartesian_examined': total, 'feasible': feasible, 'vectors': sorted(vectors), 'seconds': time.perf_counter() - started, 'method': 'unpruned full Cartesian action enumeration with independent sweep geometry'}
