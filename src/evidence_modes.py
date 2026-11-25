"""V0 transmission, V1 independent reconstruction, and V2 native B0 evidence checks."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from .independent_check import verify

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parent

def sha(p):
    return sha256(Path(p).read_bytes()).hexdigest()

def candidate_check(r, root=ROOT):
    try:
        payload = json.loads((root / Path(r['input_path'])).read_text(encoding='utf-8-sig'))
        out = verify(payload, r['h'], r['actions'], detail=True, metric=r.get('metric', 'D10'))
        rects = {e['equipment_id']: [list(x) for x in e['rectangles']] for e in out['rows']}
        costs = {e['equipment_id']: list(e['contribution']) for e in out['rows']}
        if rects != r['reported_schedule']:
            return ('REJECT', 'BAD_SCHEDULE')
        if costs != r['reported_contributions']:
            return ('REJECT', 'BAD_CONTRIBUTION')
        if out['vector'] != r['reported_vector']:
            return ('REJECT', 'BAD_VECTOR')
        return ('PASS', 'VALID')
    except (AssertionError, KeyError, ValueError, TypeError) as e:
        return ('REJECT', 'INVALID_ACTION_OR_GEOMETRY')
    except Exception as e:
        return ('UNKNOWN', 'CHECK_ERROR:' + repr(e))

def evidence_check(r, root=ROOT):
    try:
        source = root / Path(r['source_result'])
        input_path = root / Path(r['input_path'])
        raw = json.loads(source.read_text(encoding='utf-8'))
        digest = sha(input_path)
        if r['observed_elapsed_s'] > r['budget_s']:
            return 'TIME_INELIGIBLE'
        if r['input_sha256'] != digest or r['evidence_input_sha256'] != digest or raw['input_sha256'] != digest or (sha(source) != r['source_result_sha256']):
            return 'SCOPE_MISMATCH'
        if r['evidence_access'] != 'AVAILABLE':
            return 'UNKNOWN_MISSING_EVIDENCE'
        if raw['method'] != 'B0':
            return 'SCOPE_MISMATCH'
        if r['metric'] != raw['metric'] or r['policy_order'] != raw['order'] or r['h'] != raw['h'] or (r['horizon_H'] != raw['H']):
            return 'SCOPE_MISMATCH'
        if any(Path(name).name != name or sha(SOURCE / name) != expected
               for name, expected in raw['code_sha256'].items()):
            return 'SCOPE_MISMATCH'
        if r['reported_status'] != raw['native_status'] or r['reported_prefix'] > raw['closed_prefix'] or r['reported_elapsed_s'] != raw['candidate']['elapsed_s'] or (r['actions'] != raw['candidate']['actions']):
            return 'CONTRADICTED'
        p = r['reported_prefix']
        stages = r['stage_evidence']
        if len(stages) < p or any((s['lower'] is None or s['upper'] is None for s in stages[:p])):
            return 'UNKNOWN_MISSING_EVIDENCE'
        for i in range(p):
            s = stages[i]
            c = raw['calls'][i]
            if s['lower'] > s['upper']:
                return 'CONTRADICTED'
            if not (s['lower'] == c['integer_bound'] == s['upper'] == c['objective_value_exact'] and s['closed'] and s['eligible'] and (c['native_status'] == 'OPTIMAL') and (c['elapsed_end_s'] <= r['budget_s']) and (s['objective'] == c['objective'])):
                return 'CONTRADICTED'
            response = (source.parent / f'{i}_response.pbtxt').read_text(encoding='utf-8')
            status = re.search('^status:\\s*(\\w+)', response, re.M)
            if status is None or status.group(1) != 'OPTIMAL':
                return 'CONTRADICTED'
            bound = re.search('^best_objective_bound:\\s*([^\\s]+)', response, re.M)
            native_bound = float(bound.group(1)) if bound else 0.0
            if abs(native_bound) >= 2 ** 53 or native_bound != c['raw_bound']:
                return 'CONTRADICTED'
        if not p and r['reported_status'] != 'OPTIMAL':
            return 'VALID_NO_CERTIFICATE'
        if p == 5:
            return 'VALID_FULL'
        return 'VALID_PREFIX'
    except (OSError, KeyError, ValueError, TypeError, IndexError) as e:
        return 'UNKNOWN_MISSING_EVIDENCE'

def evaluate(record, mode, root=ROOT):
    """Apply one verification mode to a decision record."""
    if mode not in ("V0", "V1", "V2"):
        raise ValueError("Choose V0, V1 or V2.")
    claim = record["reported_prefix"] > 0 or record["reported_status"] == "OPTIMAL"
    if mode == "V0":
        gate, reason = "DELIVERED_UNVERIFIED", "NOT_CHECKED"
        result = "FORWARDED_UNVERIFIED" if claim else "NO_CLAIM"
    else:
        gate, reason = candidate_check(record, root)
        if gate != "PASS":
            result = "NOT_EVALUATED_INVALID" if gate == "REJECT" else "UNKNOWN"
        elif mode == "V1":
            result = "FORWARDED_UNVERIFIED" if claim else "NO_CLAIM"
        else:
            result = evidence_check(record, root)
    return {"mode": mode, "assignment_gate": gate,
            "assignment_reason": reason, "evidence_result": result,
            "has_presented_claim": claim}


def record_from_result(result, root=ROOT):
    """Build a replayable record from a local B0 run and its native response files."""
    source = (root / result).resolve()
    native = json.loads(source.read_text(encoding="utf-8"))
    if native["method"] != "B0":
        raise ValueError("V2 expects a sequential B0 result.")
    candidate = native["candidate"]
    path = root / native["job"]["input"]
    inputs = json.loads(path.read_text(encoding="utf-8-sig"))
    reconstructed = verify(inputs, native["h"], candidate["actions"],
                           detail=True, metric=native["metric"])
    stages = [{"objective": c["objective"], "lower": c["integer_bound"],
               "upper": c["objective_value_exact"], "closed": c["closed"],
               "eligible": c["eligible_native_return"]} for c in native["calls"]]
    return {
        "input_path": path.resolve().relative_to(root.resolve()).as_posix(),
        "source_result": source.relative_to(root.resolve()).as_posix(),
        "source_result_sha256": sha(source),
        "input_sha256": native["input_sha256"],
        "evidence_input_sha256": native["input_sha256"],
        "horizon_H": native["H"],
        "h": native["h"],
        "metric": native["metric"],
        "policy_order": native["order"],
        "reported_status": native["native_status"],
        "reported_prefix": native["closed_prefix"],
        "reported_elapsed_s": candidate["elapsed_s"],
        "observed_elapsed_s": candidate["elapsed_s"],
        "budget_s": native["budget_s"],
        "evidence_access": "AVAILABLE",
        "actions": candidate["actions"],
        "stage_evidence": stages,
        "reported_schedule": {r["equipment_id"]: [list(x) for x in r["rectangles"]]
                              for r in reconstructed["rows"]},
        "reported_contributions": {r["equipment_id"]: list(r["contribution"])
                                   for r in reconstructed["rows"]},
        "reported_vector": candidate["vector"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("V0", "V1", "V2"), required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--result", type=Path, help="Path to a local B0 result.json")
    source.add_argument("--record", type=Path, help="Path to a JSON decision record")
    args = parser.parse_args()
    record = (record_from_result(args.result) if args.result else
              json.loads(args.record.read_text(encoding="utf-8-sig")))
    print(json.dumps(evaluate(record, args.mode), indent=2))


if __name__ == "__main__":
    main()
