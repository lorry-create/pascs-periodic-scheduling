"""Seeded Phase 7 instance families. The generator uses synthetic inputs only."""
import argparse
import hashlib
import json
import random

def make(N, family, seed, tag):
    ratio = {'adjustable': (1, 1, 2), 'clustered': (2, 1, 1), 'forced': (1, 2, 1)}[family]
    config = {'version': 'PHASE7_INDEPENDENT_INPUT_V1', 'N': N, 'family': family, 'data_seed': seed, 'ratio': ratio}
    derived = int.from_bytes(hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).digest()[:8], 'big')
    rng = random.Random(derived)
    classes = sum(([c] * (N * v // 4) for c, v in zip('ABC', ratio)), [])
    rng.shuffle(classes)
    plans = []
    H = 24 if family == 'forced' else 120
    for i, c in enumerate(classes):
        if family == 'adjustable':
            pair = i // 2
            f0 = pair % 5 * 20
            f1 = f0 + 20
            t = 6 + pair // 5 * 14
            dur = 1
            gap = 2
            m = 2 + pair % 3
        elif family == 'forced':
            f0 = 0
            f1 = 100
            t = rng.choice([4, 5, 6])
            dur = 2
            gap = rng.choice([0, 1])
            m = rng.choice([2, 3])
        else:
            width = rng.choice([8, 16])
            dur = rng.choice([1, 2])
            gap = rng.choice([1, 3, 5])
            m = rng.choice([2, 3, 4])
            span = m * dur + (m - 1) * gap
            if rng.random() < 0.75:
                f0 = min(100 - width, max(0, round((100 - width) / 2) + rng.randint(-3, 3)))
                t = min(H - span, max(0, round((H - span) / 2) + rng.randint(-3, 3)))
            else:
                f0 = rng.randint(0, 100 - width)
                t = rng.randint(0, H - span)
            f1 = f0 + width
        plans.append(dict(equipment_id=c + str(i).zfill(3), category=c, f0=f0, f1=f1, t0=t, t1=t + dur, gap=gap, count=m))
    return {'instance_id': f'{tag}_N{N}_{family}_d{seed}', 'horizon': H, 'plans': plans, 'generation': config}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", choices=(20, 40, 80), type=int, required=True)
    parser.add_argument("--family", choices=("adjustable", "clustered", "forced"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(make(args.n, args.family, args.seed, "confirm"), indent=2))


if __name__ == "__main__":
    main()
