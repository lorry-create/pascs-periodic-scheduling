"""Run figure, solver and release-privacy checks with assertions enabled."""
import argparse
import csv
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIGURES = {
    "fig_new1_policy_certification_tradeoffs": (7080, 2400),
    "fig_new2_evidence_scope_verification": (6720, 2580),
    "fig_new3_anytime_exact_checkpoints": (6960, 2340),
    "fig7_build_memory_unified": (6360, 2310),
    "fig_new4_b0_b1_matched_comparison": (7080, 2370),
}
CSV_ROWS = {
    "TABLE_POLICY_CERTIFICATION.csv": 27,
    "TABLE_POLICY_TRADEOFF.csv": 108,
    "TABLE_FIFTH_METRIC_SENSITIVITY.csv": 12,
    "VERIFICATION_RESULTS.csv": 132,
    "TABLE_EVIDENCE_VALIDATION.csv": 3,
    "SUPPLEMENTARY_FIGURE_S1_DATA.csv": 480,
    "FIGURE3_SOURCE_DATA.csv": 60,
    "BUILD_MEMORY_SCALING_DATA.csv": 12,
    "PAIRED_COMPLETE_VECTORS.csv": 48,
    "TABLE_B0_B1_CERTIFICATION.csv": 36,
}
GENERATED = {
    f"figures/{stem}.{ext}" for stem in FIGURES for ext in ("pdf", "svg", "png")
} | {"figures/FIGURE_VERIFICATION_REPORT.md"}
LOCAL_PATH = re.compile(
    r'(?i)(?<![\w/])[a-z]\x3a[\\/]|\\\\[^\\\s]+\\[^\\\s]+'
    r'|(?<![A-Za-z0-9.])/(?:home|Users|mnt|Volumes|tmp|private|var/folders)/'
)
PRIVATE = ("\u5927\u4e00\u8d44\u6599", "\u4eba\u5de5\u667a\u80fd\u671f\u520a", "\u8bba\u6587")
EMAIL = re.compile(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}")
RESTRICTED = {".xlsx", ".xlsm", ".xls", ".docx", ".zip", ".rar", ".7z", ".gz", ".whl"}
TEXT_SUFFIXES = {".py", ".md", ".csv", ".json", ".yaml", ".yml", ".cff", ".txt", ".svg"}


def scan():
    files = []
    payload_size = 0
    total_size = 0
    for entry in ROOT.rglob("*"):
        assert not entry.is_symlink(), entry.relative_to(ROOT)
        if not entry.is_file():
            continue
        rel = entry.relative_to(ROOT)
        label = rel.as_posix()
        files.append(rel)
        size = entry.stat().st_size
        total_size += size
        assert not LOCAL_PATH.search(label) and not any(v in label for v in PRIVATE), rel
        assert entry.suffix.lower() not in RESTRICTED, rel
        assert not entry.name.lower().startswith(("canonical150", "historical_input")), rel
        assert entry.suffix.lower() != ".pdf" or label in GENERATED, rel
        metadata = rel.parts[0] == ".git"
        if not metadata and label not in GENERATED:
            payload_size += size
        raw = entry.read_bytes()
        if metadata and b"\0" in raw:
            continue
        if not metadata and entry.suffix.lower() not in TEXT_SUFFIXES and entry.name not in {
            ".gitattributes", ".gitignore", ".gitkeep", "LICENSE",
        }:
            assert label in GENERATED and entry.suffix.lower() in {".png", ".pdf"}, rel
            continue
        try:
            body = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            assert metadata, rel
            continue
        assert not LOCAL_PATH.search(body) and not any(v in body for v in PRIVATE), rel
        if not metadata:
            assert not EMAIL.search(body), rel
            assert ("PRIVATE" + " KEY-----") not in body, rel
    assert {rel.as_posix() for rel in files if rel.parts[:2] == ("data", "raw")} == {"data/raw/README.md"}
    assert payload_size < 5_000_000 and total_size < 20_000_000, (payload_size, total_size)
    return files, payload_size, total_size


def inputs():
    actual = {p.name for p in (ROOT / "data/derived").iterdir()}
    assert actual == set(CSV_ROWS)
    digests = {}
    for name, count in CSV_ROWS.items():
        p = ROOT / "data/derived" / name
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        assert len(rows) == count + 1 and all(len(r) == len(rows[0]) for r in rows)
        digests[name] = sha256(p.read_bytes()).hexdigest()
    return digests


def verify(clean_figures=False):
    assert sys.flags.optimize == 0, "Run with assertions enabled."
    scan()
    initial = inputs()
    with TemporaryDirectory(prefix="pascs_mpl_") as cache:
        env = dict(os.environ, MPLCONFIGDIR=cache, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONIOENCODING="utf-8")
        for script in ("tests/test_smoke.py", "scripts/generate_figures.py"):
            subprocess.run([sys.executable, "-B", script], cwd=ROOT, env=env, check=True)
    assert inputs() == initial, "Derived inputs changed during verification."
    for stem, size in FIGURES.items():
        for ext in ("pdf", "svg", "png"):
            path = ROOT / "figures" / f"{stem}.{ext}"
            assert path.is_file() and path.stat().st_size > 0
        with Image.open(ROOT / "figures" / f"{stem}.png") as png:
            assert png.size == size and all(abs(dpi - 600) < 0.02 for dpi in png.info["dpi"])
    assert (ROOT / "figures/FIGURE_VERIFICATION_REPORT.md").is_file()
    print("PASS: five figure sets, 15 exports, 600 dpi, unchanged inputs")
    files, payload, total = scan()
    print(f"PASS: recursive privacy and raw-file scan; {len(files)} files; "
          f"release payload {payload} bytes; working directory during verification {total} bytes")
    if clean_figures:
        for name in GENERATED:
            (ROOT / name).unlink()
        assert {p.name for p in (ROOT / "figures").iterdir()} == {".gitkeep"}
        files, payload, total = scan()
        print(f"PASS: restored empty figures directory; {len(files)} files, {total} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-figures", action="store_true",
                        help="Remove the verified generated exports and leave only .gitkeep.")
    verify(parser.parse_args().clean_figures)
