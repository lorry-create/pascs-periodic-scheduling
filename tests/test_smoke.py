"""Run from the release root using python tests/test_smoke.py."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evidence_modes import evaluate, record_from_result
from src.independent_check import exhaustive, verify
from src.model import domains
from src.synthetic import make
from src.worker import run


def test_core_and_evidence():
    synthetic = make(20, "adjustable", 71011, "confirm")
    assert synthetic == make(20, "adjustable", 71011, "confirm")
    assert len(synthetic["plans"]) == 20
    payload = {
        "instance_id": "two_entity_smoke",
        "horizon": 6,
        "plans": [
            {"equipment_id": "A000", "category": "A", "f0": 0, "f1": 100,
             "t0": 0, "t1": 1, "gap": 1, "count": 2},
            {"equipment_id": "C001", "category": "C", "f0": 0, "f1": 100,
             "t0": 0, "t1": 1, "gap": 1, "count": 2},
        ],
    }
    groups, flat = domains(payload, 2)
    assert len(groups) == 2 and len(flat) == sum(map(len, groups))
    assert all(sum(s.kind == "CANCEL" for s in group) == 1 for group in groups)
    assert not any(s.kind == "INTERVAL" for s in groups[0])
    assert any(s.kind == "INTERVAL" for s in groups[1])
    assert [s.sid for s in flat] == list(range(len(flat)))
    oracle = exhaustive(payload, 2)
    assert oracle["vector"] == (0, 1, 0, 0, 2)

    # The worker uses repository-relative run paths. Clean the synthetic traces after replay.
    runs = ROOT / "runs"
    created = not runs.exists()
    runs.mkdir(exist_ok=True)
    try:
        with TemporaryDirectory(prefix="smoke_", dir=runs) as tmp:
            out = Path(tmp)
            input_path = out / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            for encoding in ("pairwise", "cell"):
                for method in ("B0", "B1"):
                    label = f"{encoding}_{method}"
                    path = out / label
                    result = run({
                        "run_id": label, "label": "public_smoke",
                        "input": input_path.relative_to(ROOT).as_posix(),
                        "output": path.relative_to(ROOT).as_posix(),
                        "encoding": encoding, "method": method,
                        "h": 2, "metric": "D10", "seed": 32001, "workers": 1,
                        "budget_s": 8, "checkpoints": [],
                    })
                    assert result["protocol_stop"] == "OPTIMAL_FULL_LEX", result
                    assert result["closed_prefix"] == 5
                    candidate = result["candidate"]
                    assert tuple(candidate["vector"]) == oracle["vector"]
                    assert verify(payload, 2, candidate["actions"]) == oracle["vector"]

            record = record_from_result(out / "cell_B0" / "result.json")
            assert evaluate(record, "V0")["evidence_result"] == "FORWARDED_UNVERIFIED"
            assert evaluate(record, "V1")["assignment_gate"] == "PASS"
            assert evaluate(record, "V1")["evidence_result"] == "FORWARDED_UNVERIFIED"
            assert evaluate(record, "V2")["evidence_result"] == "VALID_FULL"

            invalid = deepcopy(record)
            invalid["actions"]["A000"] = ["FREQ", 11]
            assert evaluate(invalid, "V0")["assignment_gate"] == "DELIVERED_UNVERIFIED"
            assert evaluate(invalid, "V1")["assignment_gate"] == "REJECT"
            assert evaluate(invalid, "V2")["evidence_result"] == "NOT_EVALUATED_INVALID"

            contradicted = deepcopy(record)
            contradicted["stage_evidence"][0]["upper"] += 1
            assert evaluate(contradicted, "V2")["evidence_result"] == "CONTRADICTED"
            missing = deepcopy(record)
            missing["stage_evidence"][0]["lower"] = None
            assert evaluate(missing, "V2")["evidence_result"] == "UNKNOWN_MISSING_EVIDENCE"
            wrong_scope = deepcopy(record)
            wrong_scope["evidence_input_sha256"] = "0" * 64
            assert evaluate(wrong_scope, "V2")["evidence_result"] == "SCOPE_MISMATCH"
    finally:
        if created:
            runs.rmdir()
    print("PASS: state construction, four solver/encoding combinations, independent enumeration and V0/V1/V2 replays")


if __name__ == "__main__":
    assert sys.flags.optimize == 0
    os.chdir(ROOT)
    test_core_and_evidence()
