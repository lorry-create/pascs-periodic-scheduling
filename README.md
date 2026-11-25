# Exact State-Compatibility Modeling and Evidence-Aware Lexicographic Optimization for Periodic Resource Scheduling

This repository accompanies the PASCS manuscript prepared for *Axioms*. PASCS maps permitted atomic interventions to full periodic occupation and objective contributions. Pairwise exclusions and Cell cardinality constraints encode the same feasible state selections. The B0 solver closes lexicographic objectives sequentially. B1 uses strictly equivalent bounded integer weights.

## Setup

The tested interpreter is Python 3.12.14. OR-Tools, NumPy, pandas, Matplotlib and the other imported packages are pinned in requirements.txt.

```shell
python -m venv .venv
```

Activate the environment in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, activate it with `source .venv/bin/activate`. Then install the pinned dependencies:

```shell
python -m pip install -r requirements.txt
```

## Verify and reproduce

Run the commands below from the repository root. Keep Python assertions enabled.

```shell
python tests/test_smoke.py
python scripts/generate_figures.py
python tests/verify_release.py
```

The smoke test builds a new two-entity synthetic instance. It compares both encodings and both methods with an independent exhaustive optimum and checks V0, V1 and V2 using native evidence from the local B0 run. The figure script generates Figures 3, 4, 5, 7 and 8 from the derived CSV files. It saves PDF, SVG and 600 dpi PNG versions and a numeric audit in figures/. The combined verification script reruns both stages and scans the release for disallowed files and local-path tokens.

| Path | Contents |
|---|---|
| src/model.py, src/worker.py | Atomic domains, exact Pairwise and Cell models, sequential B0, scalar B1, checked incumbents and native run evidence |
| src/synthetic.py | Seeded adjustable, clustered and forced families used in the policy study |
| src/independent_check.py | Independent analytic reconstruction, geometry check and small-domain enumeration |
| src/evidence_modes.py | V0 forwarding, V1 independent verification and V2 consistency checks against native B0 stage evidence |
| data/derived/ | Archived derived tables with figure inputs, policy and fifth-metric outcomes, and aggregate/per-record gate results |
| data/raw/ | Local placement instructions for the official workbook |
| scripts/generate_figures.py | Figure generation from repository-relative CSV paths |
| tests/ | Fast solver smoke test and combined release verification |
| figures/ | Generated exports, ignored by Git |

## Data and evidence scope

The derived tables reproduce the plotted observations. PAIRED_COMPLETE_VECTORS.csv retains all 48 archived rows. The Figure 8 routine selects the 36 FORMAL_PANEL matched pairs. The checkpoint input retains the early-finish cell at N=500 and 600 s as missing. BUILD_MEMORY_SCALING_DATA.csv gives the archived build and peak working-set medians for Figure 7.

The solver examples are fresh synthetic runs. The published figures use frozen outcomes and remain reproducible across solver timing differences. Positive V2 findings describe consistency with the linked native B0 run, solver bounds and eligibility records. Independent feasibility reconstruction also supports B1 incumbents. B1's scalar-certificate inference has a separate scope and the archived derived prefixes are represented in the figure data.

## Run a synthetic example

Create runs/ locally and generate an instance:

```shell
mkdir runs
python -m src.synthetic --n 20 --family adjustable --seed 71011 > runs/input.json
```

Save this job as runs/job.json. This illustrative budget is separate from the manuscript's frozen experiments.

```json
{
  "run_id": "demo_b0",
  "label": "example",
  "input": "runs/input.json",
  "output": "runs/demo_b0",
  "encoding": "cell",
  "method": "B0",
  "h": 10,
  "metric": "D10",
  "order": [0, 1, 2, 3, 4],
  "seed": 73001,
  "workers": 1,
  "budget_s": 15
}
```

```shell
python -m src.worker --job runs/job.json
python -m src.evidence_modes --mode V2 --result runs/demo_b0/result.json
```

Use a fresh output name for each run. The run directory includes the result, action assignment and available native responses. Pairwise uses "pairwise" for encoding. Equivalent scalar solving uses "B1" for method. V0 and V1 are also available through the verifier. See data/raw/README.md for the official competition attachment.

## Official canonical benchmark

Open the competition release and extract Problem D Attachment 1 to your private data/raw/ directory. The local workbook is outside the release payload and all figure commands use archived derived inputs. [Official 2026 competition problem release](https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html)

```shell
python -m webbrowser "https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html"
```

## License and citation

The included PASCS release is prepared under the MIT License. The authors should fill the copyright holder and author names before publication. License terms for separately obtained competition materials come from their publisher. Use CITATION.cff to cite the software, and add the manuscript reference and release identifier after publication.
