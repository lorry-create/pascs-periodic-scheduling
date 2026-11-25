"""Generate four PASCS figures from the archived CSVs.

Run with Python, NumPy and Matplotlib. File paths are relative to this script.
The archived data and exported figures are resolved from the repository root.
"""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.transforms import ScaledTranslation
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTPUT = ROOT / "figures"
CHECKPOINTS = DERIVED / "SUPPLEMENTARY_FIGURE_S1_DATA.csv"

TEAL = "#2B7A73"
SLATE = "#708BA4"
OCHRE = "#A6895B"
RUST = "#B85348"
GRAY = "#8F979E"
PALE = "#D9DEE3"
ICE = "#B5C7D3"
INK = "#1F2933"
BLACK = "#111111"
POLICIES = ("P0", "P1", "P2")
MODES = ("V0", "V1", "V2")
SIZES = (150, 300, 500)
POS = ("R", "A", "CA", "CB", "D10")
SOURCE_HASHES = {}

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "mathtext.fontset": "stixsans",
    "font.size": 10,
    "text.color": INK,
    "axes.labelsize": 10.5,
    "axes.titlesize": 11.5,
    "axes.edgecolor": BLACK,
    "axes.linewidth": 1.1,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.axisbelow": True,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "pascs-axioms-figures",
    "axes.grid": False,
})


def read_csv(path):
    source = path
    SOURCE_HASHES[path.relative_to(ROOT).as_posix()] = sha256(source.read_bytes()).hexdigest()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def true(value):
    assert value.lower() in ("true", "false"), value
    return value.lower() == "true"


def panels(size, tops, *, margins, ratios=None):
    left, right, bottom, top, wspace = margins
    fig, axes = plt.subplots(
        1, len(tops), figsize=size, squeeze=False,
        gridspec_kw={"width_ratios": ratios},
    )
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top, wspace=wspace)
    for ax, label, title in zip(axes[0], "abc", tops):
        ax.set_gid(label)
        ax.text(-0.12, 1.06, label, fontsize=12, fontweight="bold",
                transform=ax.transAxes, ha="left", va="baseline")
        ax.set_title(title, y=1.037, pad=0, fontweight="normal")
        ax.grid(False)
        ax.tick_params(direction="out", length=4, width=1.0, pad=5)
    return fig, axes[0]


def handles(colors, labels):
    return [Patch(facecolor=color, label=label) for color, label in zip(colors, labels)]


def legend(fig, items, *, x=0.5, y=0.036, ncol=None, loc="lower center", handlelength=1.45):
    return fig.legend(
        handles=items, loc=loc, bbox_to_anchor=(x, y), ncol=ncol or len(items),
        borderaxespad=0, handletextpad=0.45, handlelength=handlelength, columnspacing=1.0,
    )


def md_table(columns, rows):
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def stripes(ax, patch, color, spacing=5.0):
    """Draw finite 45-degree strokes inside a bar using physical point spacing."""
    x, y = patch.get_x(), patch.get_y()
    x1, y1 = x + patch.get_width(), y + patch.get_height()
    (left, bottom), (right, top) = ax.transData.transform([(x, y), (x1, y1)])
    px = ax.figure.dpi / 72
    inset = 0.65 * px
    left, bottom, right, top = left + inset, bottom + inset, right - inset, top - inset
    width, height = right - left, top - bottom
    if width <= 0 or height <= 0:
        return
    inverse = ax.transData.inverted()
    for offset in np.arange(-height + spacing * px / 2, width, spacing * px):
        y0, y1 = max(0, -offset), min(height, width - offset)
        if y1 > y0:
            points = inverse.transform([(left + offset + y0, bottom + y0),
                                        (left + offset + y1, bottom + y1)])
            ax.plot(*points.T, color=color, lw=0.8, solid_capstyle="butt", zorder=3)


def export(fig, stem, width_reason=None):
    width, height = fig.get_size_inches()
    # Keep the requested canvas after tight export when all elements fit.
    padding = 0.08
    frame = Rectangle(
        (padding / width, padding / height),
        1 - 2 * padding / width, 1 - 2 * padding / height,
        transform=fig.transFigure, facecolor="none", edgecolor="none",
    )
    fig.add_artist(frame)
    fig.canvas.draw()
    tight = fig.get_tightbbox(fig.canvas.get_renderer())
    assert abs(tight.width + 2 * padding - width) < 0.004, (stem, tight.width)
    assert abs(tight.height + 2 * padding - height) < 0.004, (stem, tight.height)
    boxes = [ax.get_window_extent() for ax in fig.axes]
    span_pt = 72 / fig.dpi
    assert np.ptp([b.y0 for b in boxes]) * span_pt <= 1.5
    assert np.ptp([b.y1 for b in boxes]) * span_pt <= 1.5
    if not width_reason:
        assert np.ptp([b.width for b in boxes]) * span_pt <= 1.5
    fig.savefig(OUTPUT / f"{stem}.pdf", bbox_inches="tight", pad_inches=padding, dpi=600,
                metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUTPUT / f"{stem}.svg", bbox_inches="tight", pad_inches=padding, dpi=600,
                metadata={"Date": None})
    fig.savefig(OUTPUT / f"{stem}.png", bbox_inches="tight", pad_inches=padding, dpi=600)
    plt.close(fig)


def policy_figure():
    cert = read_csv(DERIVED / "TABLE_POLICY_CERTIFICATION.csv")
    trade = read_csv(DERIVED / "TABLE_POLICY_TRADEOFF.csv")
    assert len(cert) == 27 and len(trade) == 108
    assert sum(true(r["complete_certified"]) for r in trade) == 82
    assert len({r["input_id"] for r in trade}) == 18
    key = lambda r: (int(r["N"]), r["family"], r["policy"])
    table = {key(r): r for r in cert}
    assert len(table) == 27 and all(int(r["input_domain_tasks"]) == 4 for r in cert)
    counts = Counter(key(r) for r in trade)
    closed = Counter(key(r) for r in trade if true(r["complete_certified"]))
    assert set(counts) == set(table)
    for k, r in table.items():
        assert counts[k] == 4 and closed[k] == int(r["complete_certified"])
    by_domain = {(r["input_id"], r["h"], r["policy"]): r for r in trade}
    assert len(by_domain) == 108

    def vector(row):
        return tuple(int(row[k]) for k in POS)

    selected = {
        r["policy"]: r for r in trade
        if (r["N"], r["family"], r["data_seed"], r["h"]) == ("20", "clustered", "71012", "0")
    }
    assert set(selected) == set(POLICIES)
    v = [vector(selected[p]) for p in POLICIES]
    assert v == [(1, 9, 6, 1, 57), (3, 4, 4, 0, 28), (1, 9, 6, 1, 57)]
    assert all(true(r["complete_certified"]) for r in selected.values())

    changes = {}
    for p in POLICIES[1:]:
        rows = [r for r in trade if r["policy"] == p and true(r["both_full_vs_P0"])]
        assert len(rows) == 27
        vals = []
        for r in rows:
            base = by_domain[r["input_id"], r["h"], "P0"]
            assert true(r["complete_certified"]) and true(base["complete_certified"])
            vals.append((int(r["changed_actions_vs_P0"]), vector(r) != vector(base)))
        changes[p] = vals
    totals = {p: (sum(d for _, d in vals), sum(n > 0 for n, _ in vals))
              for p, vals in changes.items()}
    assert totals == {"P1": (5, 12), "P2": (0, 8)}

    fig, (a, b, c) = panels(
        (11.8, 4.0), ["Complete certification", "Certified trade-off", "Action changes vs. P0"],
        margins=(0.140, 0.978, 0.24, 0.850, 0.38), ratios=(0.75, 1.0, 1.15),
    )
    groups = [(n, family) for n in sorted({int(r["N"]) for r in cert})
              for family in ("adjustable", "clustered", "forced")]
    values = np.array([[closed[n, family, p] for p in POLICIES] for n, family in groups])
    codes = {0: 0, 3: 1, 4: 2}
    shade_index = [[codes[value] for value in row] for row in values]
    shades = ListedColormap(["#F2F4F6", "#8EBAB4", TEAL])
    a.pcolormesh(np.arange(4) - 0.5, np.arange(10) - 0.5, shade_index,
                 cmap=shades, vmin=-0.5, vmax=2.5, edgecolors="white", linewidth=2.0)
    a.set(xticks=range(3), xticklabels=POLICIES, yticks=range(9),
          yticklabels=[f"N={n} · {family.capitalize()}" for n, family in groups])
    a.invert_yaxis()
    a.tick_params(length=0)
    a.set_xlabel("Priority policy")
    for y, row in enumerate(values):
        for x, value in enumerate(row):
            denominator = counts[groups[y] + (POLICIES[x],)]
            a.text(x, y, f"{value}/{denominator}", ha="center", va="center",
                   color="white" if value == 4 else BLACK)
    for edge in (2.5, 5.5):
        a.axhline(edge, color="white", lw=4.5)

    policy_colors = (SLATE, OCHRE, TEAL)
    bar_width = 0.25
    components = np.arange(4)
    b.set(xticks=components, xticklabels=["R", "A", "CA", "CB"], ylim=(0, 10.8),
          xlim=(-0.53, 3.53), yticks=(0, 2, 4, 6, 8, 10))
    b.set_ylabel("Entities")
    for i, (color, vec) in enumerate(zip(policy_colors, v)):
        bars = b.bar(components + (i - 1) * bar_width, vec[:4], width=bar_width - 0.026,
                     color=color, edgecolor="white", linewidth=0.75, zorder=2)
        b.bar_label(bars, padding=3.3, fmt="%d", fontsize=9.5)
        if i == 2:
            for bar in bars:
                stripes(b, bar, "white", spacing=6.0)
    b.legend(handles=handles(policy_colors, POLICIES), loc="lower center",
             bbox_to_anchor=(0.5, -0.30), ncols=3, handlelength=1.0,
             handletextpad=0.38, columnspacing=1.05, borderaxespad=0)
    b.text(0.965, 0.96, "D10 (P0/P1/P2)\n" + " / ".join(str(row[4]) for row in v),
           transform=b.transAxes, ha="right", va="top", fontsize=9.5,
           multialignment="center",
           bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": PALE, "lw": 0.8})

    for p, y in [("P1", 1), ("P2", 0)]:
        changed = [(n, different) for n, different in changes[p] if n > 0]
        tally = Counter(n for n, _ in changed)
        offsets = Counter()
        c.hlines(y, 2.5, 12.9, color=PALE, ls=(0, (3, 3)), lw=0.8, zorder=0)
        for n, different in sorted(changed):
            vertical = y + (offsets[n] - (tally[n] - 1) / 2) * 0.135
            offsets[n] += 1
            c.scatter(n, vertical, marker="D" if different else "o", s=58,
                      facecolors=RUST if different else SLATE, edgecolors="white",
                      linewidths=0.8, zorder=3)
        unchanged = len(changes[p]) - len(changed)
        c.annotate(f"{unchanged}\nunchanged", (0, y),
                   xytext=(-3, 0), textcoords="offset points", ha="center", va="center",
                   linespacing=1.0, fontsize=9.5,
                   bbox={"boxstyle": "round,pad=0.22", "fc": "#F2F4F6", "ec": "none"})
        nv, na = totals[p]
        c.text(0.995, y + 0.32, f"{nv} vector-changed, {na} action-changed",
               transform=c.get_yaxis_transform(), ha="right", va="bottom", fontsize=9.5)
    c.set(xlim=(-2.15, 13.1), ylim=(-0.46, 1.60), xticks=(0, 2, 4, 6, 8, 10, 12),
          yticks=(0, 1), yticklabels=("P2", "P1"))
    c.set_xlabel("Changed entities")
    c.legend(handles=[
        Line2D([], [], marker="D", ms=7.0, color=RUST, linestyle="none", label="Vector differs"),
        Line2D([], [], marker="o", ms=7.0, color=SLATE, linestyle="none", label="Vector equals"),
    ], loc="lower center", bbox_to_anchor=(0.5, -0.30), ncols=2, borderaxespad=0,
        handletextpad=0.37, handlelength=0.92, columnspacing=0.95)
    stem = "fig_new1_policy_certification_tradeoffs"
    export(fig, stem, "The strip compares 54 observations and needs more width than the heatmap.")
    parts = [
        "### New-1 · Policy certification and trade-offs",
        "**a.** Complete certificates out of four tested tasks per cell.",
        md_table(["N", "Family", *POLICIES],
                 [(n, family, *(f"{closed[n, family, p]}/{counts[n, family, p]}" for p in POLICIES))
                  for n, family in groups]),
        "**b.** Clustered N=20, data seed 71012, h=0. All three rows have complete certificates.",
        md_table(["Policy", *POS], [(p, *vec) for p, vec in zip(POLICIES, v)]),
        "**c.** Changed-entity counts and frequencies among jointly certified domains. "
        "Badges give the unchanged assignments at zero. Dots represent changed assignments, with vertical offsets separating equal counts.",
        md_table(["Policy", "Domains", "Vector differences", "Domains with changed actions",
                  "Counts by changed entities (count×frequency)", "Counts for changed-vector domains"],
                 [(p, len(rows), *totals[p], ", ".join(f"{n}×{k}" for n, k in sorted(Counter(n for n, _ in rows).items())),
                   ", ".join(str(n) for n, different in sorted(rows) if different) or "None")
                  for p, rows in changes.items()]),
    ]
    return "\n\n".join(parts)

def evidence_figure():
    detail = read_csv(DERIVED / "VERIFICATION_RESULTS.csv")
    aggregate = read_csv(DERIVED / "TABLE_EVIDENCE_VALIDATION.csv")
    assert len(detail) == 132 and len(aggregate) == 3
    by_case = {(r["case_id"], r["mode"]): r for r in detail}
    cases = {r["case_id"] for r in detail}
    assert len(cases) == 44 and set(by_case) == {(c, m) for c in cases for m in MODES}
    control = [f"CONTROL_{i}" for i in range(1, 9)]
    faults = [[f"F{i:02}_{j}" for j in range(1, 4)] for i in range(1, 13)]
    assert cases == set(control) | {c for group in faults for c in group}
    assert all(by_case[c, m]["injection"] == "CONTROL" for c in control for m in MODES)
    assert all(by_case[c, m]["injection"] == f"F{i}" for i, group in enumerate(faults, 1)
               for c in group for m in MODES)
    summary = {r["mode"]: r for r in aggregate}
    assert set(summary) == set(MODES)
    flags = ("invalid_assignment_forwarded", "misrepresented_result_forwarded", "incorrect_claim_forwarded")
    count_cols = ("invalid_forwarded", "misreport_forwarded", "unsupported_claims_forwarded",
                  "unknown_missing_evidence")
    denom_cols = ("invalid_total", "misreport_total", "unsupported_claims_total")
    truth_cols = ("invalid_assignment", "misrepresented_result", "incorrect_certification_claim")
    nums, denoms, rejections = {}, {}, {}
    for mode in MODES:
        rows = [by_case[c, mode] for c in cases]
        nums[mode] = tuple(sum(true(r[k]) for r in rows) for k in flags) + (
            sum(r["evidence_result"] == "UNKNOWN_MISSING_EVIDENCE" for r in rows),)
        denoms[mode] = tuple(sum(true(r[k]) for r in rows) for k in truth_cols) + (
            sum(r["evidence_truth"] == "UNKNOWN_MISSING_EVIDENCE" for r in rows),)
        rejections[mode] = sum(true(r["false_rejection"]) for r in rows)
        assert int(summary[mode]["records"]) == 44
        assert int(summary[mode]["fault_fixtures"]) == len(cases) - len(control)
        assert nums[mode] == tuple(int(summary[mode][k]) for k in count_cols)
        assert denoms[mode][:3] == tuple(int(summary[mode][k]) for k in denom_cols)
        assert int(summary[mode]["valid_controls"]) == len(control)
        assert rejections[mode] == int(summary[mode]["valid_control_false_rejections"]) == 0
    assert nums == {"V0": (12, 9, 35, 0), "V1": (0, 0, 14, 0), "V2": (0, 0, 0, 1)}
    assert all(v == (12, 9, 35, 1) for v in denoms.values())
    unknown = [(r["case_id"], r["mode"]) for r in detail if r["evidence_result"] == "UNKNOWN_MISSING_EVIDENCE"]
    assert unknown == [("F12_1", "V2")]

    def gate(case, mode):
        r = by_case[case, mode]
        if r["injection"] == "CONTROL":
            assert not true(r["false_rejection"])
            return "Control delivered"
        if r["evidence_result"] == "UNKNOWN_MISSING_EVIDENCE":
            return "Unknown evidence"
        if any(true(r[k]) for k in flags) or r["evidence_result"] == "FORWARDED_UNVERIFIED":
            return "Fault forwarded"
        assert true(r["fault_flagged"])
        return "Fault blocked"

    gate_colors = {
        "Control delivered": TEAL, "Fault blocked": ICE,
        "Fault forwarded": RUST, "Unknown evidence": OCHRE,
    }
    matrix = {(c, m): gate(c, m) for c, m in by_case}
    fig, (a, b) = panels(
        (11.2, 4.3), ["Record-level verification outcomes", "Category-level gate rates"],
        margins=(0.065, 0.977, 0.25, 0.862, 0.40), ratios=(1.15, 1.0),
    )
    a.set(xlim=(0, 8.82), ylim=(0, 10.75))
    a.set_axis_off()
    step_y = 0.67

    def band(groups, top, control_band=False):
        for index, mode in enumerate(MODES):
            a.text(0.015, top - index * step_y, mode, ha="left", va="center")
        for j, group in enumerate(groups):
            x0 = 0.86 + 1.306 * j
            if control_band:
                name = f"Controls ({len(group)})"
                spacing, tile = 0.52, 0.44
                a.text(x0, top + 0.57, name, ha="left", va="bottom")
            else:
                name = by_case[group[0], MODES[0]]["injection"]
                spacing, tile = 0.40, 0.35
                a.text(x0 + spacing + tile / 2, top + 0.57, name, ha="center", va="bottom")
            for k, case in enumerate(group):
                x = x0 + k * spacing
                for index, mode in enumerate(MODES):
                    y = top - index * step_y
                    outcome = matrix[case, mode]
                    a.add_patch(Rectangle(
                        (x, y - 0.235), tile, 0.47, facecolor=gate_colors[outcome],
                        linewidth=0, edgecolor="none",
                    ))
                    if (case, mode) in unknown:
                        a.plot(x + tile / 2, y, marker="o", ms=3.4, mfc="white",
                               mec="white", linestyle="none")
                        a.annotate(case, (x + tile / 2, y - 0.24), xytext=(0, -6),
                                   textcoords="offset points", ha="center", va="top", color=INK)

    band([control], 9.13, control_band=True)
    band(faults[:6], 5.92)
    band(faults[6:], 2.71)
    a.legend(handles=handles(gate_colors.values(), gate_colors.keys()),
             loc="lower center", bbox_to_anchor=(0.5, -0.18), ncols=2,
             handlelength=1.15, handletextpad=0.50, columnspacing=1.25,
             borderaxespad=0, labelspacing=0.6)

    metrics = ("Invalid\nforwarded", "Misreported\nforwarded", "Unsupported claim\nforwarded",
               "Missing bound\nmarked UNKNOWN")
    colors = (GRAY, SLATE, TEAL)
    y = np.arange(len(metrics))
    rates = {mode: [100 * count / total for count, total in zip(nums[mode], denoms[mode])]
             for mode in MODES}
    for i, (mode, color) in enumerate(zip(MODES, colors)):
        centers = y + (i - 1) * 0.255
        b.barh(centers, rates[mode], height=0.196, color=color, zorder=2)
        for y0, rate, numerator, denominator in zip(centers, rates[mode], nums[mode], denoms[mode]):
            b.text(rate + (2.65 if rate else 1.5), y0, f"{numerator}/{denominator}",
                   ha="left", va="center")
    ticks = (0, 25, 50, 75, 100)
    b.set(xlim=(0, 118), ylim=(3.55, -0.55), xticks=ticks, xticklabels=[f"{v}%" for v in ticks],
          yticks=y, yticklabels=metrics)
    b.tick_params(axis="y", length=0, pad=7)
    b.set_xlabel("Percentage of cases in category")
    b.legend(handles=handles(colors, MODES), loc="lower center",
             bbox_to_anchor=(0.5, -0.263), ncols=3, borderaxespad=0,
             columnspacing=1.35, handlelength=1.16, handletextpad=0.48)
    b.text(0.5, -0.295, f"Valid control false rejections: {rejections['V2']}/{len(control)} across V0, V1 and V2",
           transform=b.transAxes, ha="center", va="top", color="#4A5560", fontsize=9.5)
    stem = "fig_new2_evidence_scope_verification"
    export(fig, stem, "The record-level panel needs room for 44 case columns packed into three bands.")
    metric_rows = [
        (name.replace("\n", " "), *(f"{nums[m][i]}/{denoms[m][i]} ({rates[m][i]:g}%)" for m in MODES))
        for i, name in enumerate(metrics)
    ]
    parts = [
        "### New-2 · Record-level evidence scope",
        "**a.** Tile categories by mode. Controls are shown first, followed by F1–F12 in increasing index order. "
        "Cases inside each group are ordered by suffix from left to right.",
        md_table(["Case ID", *MODES],
                 [(c, *(matrix[c, m] for m in MODES)) for c in control + [x for g in faults for x in g]]),
        "**b.** Counts and denominators. One missing-bound case, F12_1, is marked UNKNOWN under V2.",
        md_table(["Outcome", *MODES], metric_rows + [
            ("False rejections on valid controls", *(f"{rejections[m]}/{len(control)}" for m in MODES))
        ]),
    ]
    return "\n\n".join(parts)


def anytime_figure():
    rows = read_csv(CHECKPOINTS)
    assert len(rows) == 480
    times = sorted({int(r["checkpoint_s"]) for r in rows})
    assert times == [30, 120, 300, 600]
    assert {int(r["N"]) for r in rows} == set(SIZES)
    assert len({r["run_id"] for r in rows}) == 120
    assert len({(r["run_id"], r["checkpoint_s"]) for r in rows}) == 480
    received = [r for r in rows if r["R"].strip()]
    assert len(received) == 479
    missing = [r for r in rows if not r["R"].strip()]
    assert [(r["run_id"], r["checkpoint_s"], r["status"], r["full_vector"]) for r in missing] == [
        ("M1_N500_seed2027_cell_lex", "600", "NOT_REACHED_EARLY_FINISH", ""),
    ]
    assert all(r["status"] == "REACHED" and int(r["R"]) == json.loads(r["full_vector"])[0]
               for r in received)
    series = (
        ("M1", "pairwise_lex", "Pairwise rigid", OCHRE, "o", "-"),
        ("M3", "pairwise_lex", "Pairwise flexible", OCHRE, "o", "--"),
        ("M1", "cell_lex", "Cell rigid", TEAL, "s", "-"),
        ("M3", "cell_lex", "Cell flexible", TEAL, "s", "--"),
    )
    assert {(r["phase"], r["method"]) for r in rows} == {(phase, meth) for phase, meth, *_ in series}
    # H labels are scenario values specified in the figure brief. The checkpoint CSV has no H column.
    horizons = {150: 643, 300: 1286, 500: 2144}
    fig, axes = panels(
        (11.6, 3.9), [f"N = {n}  (H = {horizons[n]})" for n in SIZES],
        margins=(0.098, 0.978, 0.242, 0.85, 0.37),
    )
    positions = np.arange(len(times))
    plotted = []
    for n, ax in zip(SIZES, axes):
        for phase, meth, name, color, marker, style in series:
            medians, lower, upper = [], [], []
            for x, t in zip(positions, times):
                bucket = sorted(
                    (r for r in rows if (r["N"], r["phase"], r["method"], r["checkpoint_s"])
                     == (str(n), phase, meth, str(t))),
                    key=lambda r: int(r["seed"]),
                )
                seeds = [int(r["seed"]) for r in bucket]
                assert seeds == list(range(2026, 2036))
                vals = [(i, int(r["R"])) for i, r in enumerate(bucket) if r["R"].strip()]
                expect = 9 if (n, t, phase, meth) == (500, 600, "M1", "cell_lex") else 10
                assert len(vals) == expect
                values = [value for _, value in vals]
                median = float(np.median(values))
                q1, q3 = np.percentile(values, [25, 75], method="inverted_cdf")
                medians.append(median)
                lower.append(q1)
                upper.append(q3)
                plotted.append((n, name, t, len(vals), median, q1, q3,
                                ", ".join(r["R"] if r["R"].strip() else "—" for r in bucket)))
                if len(vals) != len(bucket):
                    ax.annotate(f"n = {len(vals)}/{len(bucket)}", (x, median),
                                xytext=(-10, 20), textcoords="offset points", ha="right", va="bottom",
                                color=TEAL, fontsize=9,
                                arrowprops={"arrowstyle": "-", "color": TEAL, "lw": 0.8},
                                zorder=5)
            ax.fill_between(positions, lower, upper, color=color, alpha=0.13, linewidth=0, zorder=1)
            ax.plot(positions, medians, color=color, linestyle=style, marker=marker,
                    mfc=color if phase == "M1" else "white",
                    mec="white" if phase == "M1" else color,
                    mew=0.9 if phase == "M1" else 1.3, ms=6.8, lw=2.1, zorder=4)
        ax.set(xlim=(-0.25, 3.25), xticks=positions, xticklabels=times)
        ax.margins(y=0.12)
        ax.set_xlabel("Checkpoint (s)")
    axes[0].set_ylabel("Verified cancellation incumbent R")
    legend(fig, [
        Line2D([], [], color=color, marker=marker, mfc=color if phase == "M1" else "white",
               mec=color, ms=5.5, lw=2.1, linestyle="-" if phase == "M1" else (0, (4, 2.2)), label=name)
        for phase, _, name, color, marker, style in series
    ], y=0.056, handlelength=3.0)
    stem = "fig_new3_anytime_exact_checkpoints"
    export(fig, stem)
    return "\n\n".join([
        "### New-3 · Observed exact-encoding checkpoints",
        "**a–c.** Each row gives the plotted median, interquartile boundaries, and observed R in seed order "
        "2026–2035. Quartiles use the inverse empirical CDF, which selects observed order statistics. "
        "A dash marks the early-finish checkpoint without a recorded value. The ribbons join checkpoint summaries with straight segments.",
        md_table(["N", "Series", "Seconds", "Observed n", "Median R", "Q1 R", "Q3 R", "Observed R by seed"], plotted),
    ])


def matched_figure():
    source = read_csv(DERIVED / "PAIRED_COMPLETE_VECTORS.csv")
    cert = read_csv(DERIVED / "TABLE_B0_B1_CERTIFICATION.csv")
    pairs = [r for r in source if r["cohort"] == "FORMAL_PANEL"]
    assert len(source) == 48 and len(pairs) == len(cert) == 36
    index = {(r["input_id"], r["h"], r["solver_seed"]): r for r in cert}
    assert len(index) == 36
    assert set(index) == {(r["input_id"], r["h"], r["seed"]) for r in pairs}
    assert {r["h"] for r in pairs} == {"0", "10"} and {r["seed"] for r in pairs} == {"32001", "32002"}
    assert len({r["input_id"] for r in pairs}) == 9
    joined = []
    for r in pairs:
        d = index[r["input_id"], r["h"], r["seed"]]
        assert r["outcome"] == d["outcome"]
        for alg in ("B0", "B1"):
            assert json.loads(r[f"{alg}_vector"]) == json.loads(d[f"{alg}_vector"])
            assert r[f"{alg}_prefix"] == d[f"{alg}_native_prefix"]
            assert true(d[f"{alg}_full_certified"]) == (int(d[f"{alg}_native_prefix"]) == 5)
        b0 = tuple(json.loads(r["B0_vector"]))
        b1 = tuple(json.loads(r["B1_vector"]))
        assert r["outcome"] == ("B0_WIN" if b0 < b1 else "B1_WIN" if b1 < b0 else "TIE")
        x, y = (float(r[k]) for k in ("B0_wall_s", "B1_wall_s"))
        assert x > 0 and y > 0 and np.isfinite([x, y]).all()
        both = true(d["B0_full_certified"]) and true(d["B1_full_certified"])
        joined.append((int(r["N"]), r["input_id"], r["h"], r["seed"], x, y, both))
    wins = Counter(r["outcome"] for r in pairs)
    assert wins == {"B0_WIN": 1, "B1_WIN": 7, "TIE": 28}
    native = {m: Counter(int(r[f"{m}_native_prefix"]) for r in cert) for m in ("B0", "B1")}
    assert native == {"B0": {1: 8, 4: 2, 5: 26}, "B1": {0: 13, 5: 23}}
    derived = [r for r in cert if r["B1_native_prefix"] == "0" and r["B1_posthoc_derived_prefix"] == "4"]
    assert len(derived) == 4
    assert all(r["B1_posthoc_derived_prefix"] in ("0", "4", "5") for r in cert)

    fig, (a, b, c) = panels(
        (11.8, 3.95), ["Candidate quality", "Certification prefix depth", "Paired computational wall time"],
        margins=(0.085, 0.975, 0.248, 0.845, 0.38), ratios=(1.0, 1.0, 1.13),
    )
    palette = (TEAL, PALE, OCHRE)
    results = ("B1_WIN", "TIE", "B0_WIN")
    sizes = sorted({r[0] for r in joined})
    outcomes = {n: Counter(r["outcome"] for r in pairs if int(r["N"]) == n) for n in sizes}
    assert all(sum(outcomes[n].values()) == 12 for n in sizes)
    for i, n in enumerate(sizes):
        left = 0
        for verdict, color in zip(results, palette):
            width = outcomes[n][verdict]
            if width:
                a.barh(i, width, left=left, height=0.55, color=color, edgecolor="white",
                       linewidth=1.2, zorder=2)
                a.text(left + width / 2, i, str(width), ha="center", va="center",
                       color="white" if verdict == "B1_WIN" else BLACK)
            left += width
    a.set(xlim=(0, 12.18), ylim=(2.5, -0.5), xticks=(0, 4, 8, 12), yticks=np.arange(3),
          yticklabels=[f"N = {n}" for n in sizes])
    a.tick_params(axis="y", length=0)
    a.set_xlabel("Matched pairs")
    a.legend(handles=handles(palette, [f"{name} ({wins[key]})" for name, key in zip(
                 ("B1 better", "Tie", "B0 better"), results)]),
             loc="lower center", bbox_to_anchor=(0.5, -0.31), ncols=3, borderaxespad=0,
             handlelength=0.91, handletextpad=0.32, columnspacing=0.66)

    depth = np.arange(6)
    b.set(xticks=depth, xlim=(-0.54, 5.54), ylim=(0, 30.5), yticks=(0, 10, 20, 30))
    for i, (method, color) in enumerate([("B0", "#5A6B7C"), ("B1", TEAL)]):
        xs = depth + (i - 0.5) * 0.375
        vals = [native[method][k] for k in depth]
        bars = b.bar(xs, vals, width=0.34, color=color, zorder=2)
        b.bar_label(bars, labels=[str(value) if value else "" for value in vals], padding=3.5, fontsize=9.5)
    outline = b.bar(4.1875, len(derived), width=0.34, facecolor="white",
                    edgecolor=TEAL, linewidth=1.3, zorder=2)
    stripes(b, outline[0], TEAL, spacing=5.2)
    b.bar_label(outline, padding=3.5, fontsize=9.5)
    b.set_xlabel("Certified prefix depth")
    b.set_ylabel("Runs")
    b.legend(handles=[
        Patch(facecolor="#5A6B7C", label="B0 native"),
        Patch(facecolor=TEAL, label="B1 native"),
        Patch(facecolor="white", edgecolor=TEAL, linewidth=1.3, label=f"B1 post-hoc ({len(derived)})"),
    ], loc="lower center", bbox_to_anchor=(0.5, -0.31), ncols=3, borderaxespad=0,
        handlelength=0.88, handletextpad=0.31, columnspacing=0.65)

    encodings = dict(zip(sizes, [(SLATE, "o"), (OCHRE, "s"), (TEAL, "^")]))
    c.set(xscale="log", yscale="log", xlim=(0.04, 48), ylim=(0.04, 48))
    ticks = [0.05, 0.2, 1, 5, 30]
    tick_labels = ["0.05", "0.2", "1", "5", "30"]
    c.set_xticks(ticks, tick_labels)
    c.set_yticks(ticks, tick_labels)
    c.tick_params(which="minor", length=0)
    c.axhline(30, color=PALE, lw=0.9, ls=":", zorder=0)
    c.axvline(30, color=PALE, lw=0.9, ls=":", zorder=0)
    c.plot([0.04, 48], [0.04, 48], color=GRAY, ls="--", lw=0.95, zorder=0)
    c.text(0.06, 0.86, "B0 faster", transform=c.transAxes, fontsize=9,
           fontstyle="italic", color="#6B7280", ha="left")
    c.text(0.887, 0.09, "B1 faster", transform=c.transAxes, fontsize=9,
           fontstyle="italic", color="#6B7280", ha="right")
    c.set_xlabel("B0 wall time (s)")
    c.set_ylabel("B1 wall time (s)")
    assert all(0.135 < v[4] < 47 and 0.039 < v[5] < 51 for v in joined)

    # Leader lines keep the true coordinates visible when near-limit symbols are offset.
    near = sorted(row for row in joined if row[4] >= 29.9 and row[5] >= 29.9)
    fig.canvas.draw()
    pixels_per_pt = fig.dpi / 72
    anchors = c.transData.transform([(r[4], r[5]) for r in near]) / pixels_per_pt
    outsiders = c.transData.transform([(r[4], r[5]) for r in joined if r not in near]) / pixels_per_pt
    left, bottom, right, top = c.bbox.extents / pixels_per_pt
    angles = np.arange(len(near)) * 2 * np.pi / len(near)
    best = None
    for radius in (11.5, 13.5, 15.5):
        for phase in np.linspace(0, 2 * np.pi / len(near), 15, endpoint=False):
            ring = radius * np.column_stack((np.cos(angles + phase), np.sin(angles + phase)))
            for shift in [(-9, -10), (-12, -8), (-14, -7), (-6, -9), (-7, -12)]:
                shown = anchors + ring + shift
                x, y = shown.T
                if not (np.all((left + 4 < x) & (x < right - 4))
                        and np.all((bottom + 4 < y) & (y < top - 4))):
                    continue
                distance = np.linalg.norm(shown[:, None, :] - outsiders[None, :, :], axis=2).min()
                spacing = min(distance, 2 * radius * np.sin(np.pi / len(near)))
                score = min(spacing, 8.3) - 0.025 * np.linalg.norm(ring + shift, axis=1).max()
                if best is None or score > best[0]:
                    best = (score, shown - anchors)
    assert best is not None and len(near) == 9, "No unclipped near-limit layout"
    display_offsets = {tuple(row[:4]): shift for row, shift in zip(near, best[1])}
    for n, input_id, h, seed, x, y, both in joined:
        dx, dy = display_offsets.get((n, input_id, h, seed), (0, 0))
        transform = c.transData
        if dx or dy:
            c.annotate("", (x, y), xytext=(dx, dy), textcoords="offset points",
                       arrowprops={"arrowstyle": "-", "color": GRAY, "alpha": 0.65,
                                   "lw": 0.65, "shrinkA": 2.8, "shrinkB": 0}, zorder=2)
            transform += ScaledTranslation(dx / 72, dy / 72, fig.dpi_scale_trans)
        color, marker = encodings[n]
        c.plot(x, y, marker=marker, ms=6.2, mfc=color if both else "white",
               mec="white" if both else color, mew=0.85 if both else 1.5,
               linestyle="none", transform=transform, zorder=3)
    c.legend(handles=[
        Line2D([], [], marker=marker, color=color, ms=6.2, linestyle="none", label=f"N={n}")
        for n, (color, marker) in encodings.items()
    ], loc="lower center", bbox_to_anchor=(0.5, -0.280), ncols=3, borderaxespad=0,
        handlelength=0.87, handletextpad=0.37, columnspacing=0.82)
    c.text(0.5, -0.31, "Filled: both fully certified", transform=c.transAxes, ha="center", va="top", fontsize=9.5)
    stem = "fig_new4_b0_b1_matched_comparison"
    export(fig, stem, "The log-time panel needs more width for the nine separated near-limit symbols.")
    return "\n\n".join([
        "### New-4 · Matched B0 versus B1",
        "**a.** Complete-vector comparison by instance size.",
        md_table(["N", "B1 better", "Tie", "B0 better"],
                 [(n, *(outcomes[n][k] for k in results)) for n in sizes] +
                 [("All", *(wins[k] for k in results))]),
        "**b.** Native certificate depth and the separate B1 post-hoc result.",
        md_table(["Prefix", "B0 native", "B1 native", "B1 derived subset"],
                 [(i, native["B0"][i], native["B1"][i], len(derived) if i == 4 else 0) for i in range(6)]),
        "**c.** Exact source coordinates in seconds for all 36 pairs. "
        f"Both runs are fully certified in {sum(row[-1] for row in joined)}/36 pairs. "
        f"Leader lines link the {len(near)} radially offset symbols to the recorded time coordinates. "
        "Offsets apply only to pairs with both wall times at least 29.9 s. They are measured in display points.",
        md_table(["N", "Input", "h", "Seed", "B0 wall time (s)", "B1 wall time (s)", "Both fully certified", "Display offset (pt)"],
                 [(*row, ", ".join(f"{v:.2f}" for v in display_offsets.get(tuple(row[:4]), (0, 0))))
                  for row in sorted(joined)]),
    ])



def build_memory_figure():
    source = DERIVED / "BUILD_MEMORY_SCALING_DATA.csv"
    rows = read_csv(source)
    assert len(rows) == 12
    data = {(r["phase"], r["method"], int(r["N"])): r for r in rows}
    series = (
        ("M1", "pairwise_lex", "Pairwise rigid", OCHRE, "o", "-"),
        ("M3", "pairwise_lex", "Pairwise flexible", OCHRE, "o", (0, (4, 2.2))),
        ("M1", "cell_lex", "Cell rigid", TEAL, "s", "-"),
        ("M3", "cell_lex", "Cell flexible", TEAL, "s", (0, (4, 2.2))),
    )
    assert set(data) == {(phase, method, n) for phase, method, *_ in series for n in SIZES}
    assert all(int(r["cells"]) == 10 for r in rows)
    build = "build_s_median"
    memory = "peak_rss_mb_median"
    assert [round(float(data["M1", "pairwise_lex", n][build]), 2) for n in (150, 500)] == [1.83, 7.02]
    assert [round(float(data["M1", "cell_lex", n][build]), 2) for n in (150, 500)] == [0.53, 1.92]
    assert all(np.isfinite(float(r[k])) and float(r[k]) >= 0 for r in rows for k in (build, memory))

    fig, axes = panels(
        (10.6, 3.85), ["Model construction time", "Peak resident memory"],
        margins=(0.109, 0.975, 0.28, 0.85, 0.39),
    )
    horizons = {150: 643, 300: 1286, 500: 2144}
    x = np.arange(len(SIZES))
    proxies, tabular = [], []
    for phase, method, label, color, marker, style in series:
        plotted = [data[phase, method, n] for n in SIZES]
        for ax, field in zip(axes, (build, memory)):
            y = [float(r[field]) for r in plotted]
            ax.plot(x, y, color=color, marker=marker, linestyle=style, lw=2.1, ms=6.8,
                    mfc=color if phase == "M1" else "white", mec="white" if phase == "M1" else color,
                    mew=0.9 if phase == "M1" else 1.3)
        proxies.append(Line2D([], [], color=color, marker=marker, linestyle=style, lw=2.1, ms=5.5,
                              mfc=color if phase == "M1" else "white", mec=color, mew=1.1, label=label))
        tabular.extend((label, n, row[build], row[memory]) for n, row in zip(SIZES, plotted))
    for ax, label in zip(axes, ("Median build time (s)", "Median peak RSS (MiB)")):
        ax.set(xlim=(-0.24, 2.24), xticks=x,
               xticklabels=[f"N={n} · H={horizons[n]}" for n in SIZES],
               xlabel="Configuration", ylabel=label)
        ax.set_ylim(bottom=0)
    legend(fig, proxies, y=0.061, handlelength=3.0)
    export(fig, "fig7_build_memory_unified")
    return "\n\n".join([
        "### Figure 7 · Model construction and peak resident memory",
        "All plotted coordinates are archived medians per configuration. Each series uses ten instances per size.",
        md_table(["Series", "N", "Median build time (s)", "Median peak RSS (MiB)"], tabular),
    ])


CAPTIONS = """## Manuscript captions

**Figure New-1. Policy sensitivity and trade-offs.** (a) Fully certified tasks in each size, family and policy cell. Each cell contains four tasks spanning two base inputs and two flexibility settings. (b) Certified outcome vectors for the clustered instance at N = 20, data seed 71012 and h = 0. Bars show cancellation (R), adjustment (A) and affected-entity counts (CA and CB). The box gives the integer disturbance component (D10). The striped P2 bars identify a vector identical to P0 for this instance. (c) Changed entities relative to P0 in the 27 jointly certified domains per policy comparison. Labels at zero give counts of unchanged assignments. A changed entity has a different action label or displacement. Diamonds mark changed outcome vectors and circles mark unchanged outcome vectors.

**Figure New-2. Scope of verification across targeted records.** (a) Outcomes for 44 records in eight controls and 12 groups of three fault cases, ordered by case suffix within each group. Rows show V0, V1 and V2. Control delivery under V0 denotes unverified presentation. The missing-bound case F12_1 appears as UNKNOWN under V2. (b) Within-category percentages with exact counts overlaid. Invalid-assignment, misreported-impact and unsupported-claim categories overlap, with denominators of 12, 9 and 35, respectively. The missing-bound denominator is one. F12_1 was forwarded unverified under V0 and V1 and falls outside the unsupported-claim denominator. Each mode had 0/8 false rejections among valid controls. The results describe the targeted records.

**Figure New-3. Verified cancellation incumbents at exact-encoding checkpoints.** (a–c) Results for N = 150, 300 and 500, respectively. Markers show the observed median R and ribbons show the pointwise interquartile range using empirical order statistics. Segments connect the four checkpoint summaries. At N = 500 and 600 s, rigid Cell has n = 9/10 because M1_N500_seed2027_cell_lex exited before the checkpoint. The median and quartiles for that cell use the nine recorded values. Each other median and interquartile range uses ten observations.

**Figure New-4. Matched comparison of sequential (B0) and scalar (B1) lexicographic optimization.** (a) Candidate-vector comparison for 36 matched pairs, grouped by instance size. (b) Native certificate depth by method. The striped depth-4 B1 bar shows four post-hoc derived prefixes. Those same runs also contribute to the native depth-0 count. (c) Paired computational wall time on log axes, with a dashed equality line and dotted 30 s references. Filled symbols indicate both runs were fully certified. Leader lines connect the radially spaced symbols in the near-30 s cluster to their measured coordinates. The separation applies only to the nine pairs with both measured wall times at least 29.9 s.
"""


def main():
    assert sys.flags.optimize == 0, "Run without -O so publication checks are active."
    OUTPUT.mkdir(exist_ok=True)
    parts = [policy_figure(), evidence_figure(), anytime_figure(), matched_figure(), build_memory_figure()]
    assert all(sha256((ROOT / path).read_bytes()).hexdigest() == digest
               for path, digest in SOURCE_HASHES.items())
    source_table = md_table(["Repository-relative CSV", "SHA-256"], SOURCE_HASHES.items())
    intro = (
        "# PASCS figure reproduction report\n\n"
        "All data assertions passed. Figures 3, 4, 5, 7 and 8 were exported as PDF, SVG and 600 dpi PNG.\n\n"
        f"Python {sys.version.split()[0]}, NumPy {np.__version__}, Matplotlib {mpl.__version__}.\n\n"
        "## Archived inputs\n\n" + source_table + "\n\n"
        "## Values plotted by panel\n\n"
    )
    (OUTPUT / "FIGURE_VERIFICATION_REPORT.md").write_text(
        intro + "\n\n".join(parts) + "\n\n" + CAPTIONS, encoding="utf-8",
    )
    print("All data assertions passed. Exported five figures and the verification report to figures/.")


if __name__ == "__main__":
    main()
