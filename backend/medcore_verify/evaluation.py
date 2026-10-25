"""Scores the checkers on a generated dataset and writes a results table.

    python -m medcore_verify.datagen dataset --out ../data/claims --per-diagnosis 30
    python -m medcore_verify.evaluation --data ../data/claims --out ../data/results.md

'Caught' means the claim is held for review. For each claim the verdict is recomputed
using only checker 1, only checker 2, only checker 3, and all three, which answers the
research question: do content checks catch what file forensics misses?
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .models import Flag, decide_verdict
from .pipeline import analyze

SUBSETS = {"Checker 1 only": {1}, "Checker 2 only": {2}, "Checker 3 only": {3},
           "Checkers 2 + 3": {2, 3}, "All three": {1, 2, 3}}


def _run(folder: str) -> dict:
    path = Path(folder)
    truth = json.loads((path / "truth.json").read_text())
    files = [(p.name, p.read_bytes()) for p in sorted(path.glob("*.pdf"))]
    report, _ = analyze(files)
    held = {}
    for name, checkers in SUBSETS.items():
        subset: list[Flag] = [f for f in report.flags if f.checker in checkers]
        held[name] = decide_verdict(subset) == "hold"
    return {"truth": truth, "held": held, "codes": sorted({f.code for f in report.flags}),
            "seconds": report.seconds}


def _pct(k: int, n: int) -> str:
    return f"{100 * k / n:.0f}% ({k}/{n})" if n else "-"


def evaluate(data: Path, workers: int | None = None) -> tuple[str, dict]:
    folders = sorted(str(p) for p in data.iterdir() if (p / "truth.json").exists())
    if not folders:
        raise SystemExit(f"No claims found in {data}")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_run, folders, chunksize=8))

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        t = r["truth"]
        groups["Genuine" if t["genuine"] else f"{t['forgery_type']} {t['variant']}"].append(r)

    cols = list(SUBSETS)
    lines = ["# MedCore Verify evaluation", "",
             f"{len(results)} synthetic claims. A cell shows the share of claims held for review "
             "when only those checkers' flags count. For genuine claims, that share is the false-alarm rate.", "",
             "| Group | Claims | " + " | ".join(cols) + " |",
             "| --- | --- | " + " | ".join("---" for _ in cols) + " |"]
    summary: dict[str, dict] = {}
    order = ["Genuine"] + sorted(k for k in groups if k != "Genuine")
    for name in order:
        rows = groups[name]
        caught = {c: sum(r["held"][c] for r in rows) for c in cols}
        summary[name] = {"claims": len(rows), **{c: caught[c] / len(rows) for c in cols}}
        lines.append(f"| {name} | {len(rows)} | " + " | ".join(_pct(caught[c], len(rows)) for c in cols) + " |")

    for family in ("F2", "F5"):
        rows = [r for r in results if r["truth"]["forgery_type"] == family]
        if rows:
            caught = {c: sum(r["held"][c] for r in rows) for c in cols}
            summary[f"All {family}"] = {"claims": len(rows), **{c: caught[c] / len(rows) for c in cols}}
            lines.append(f"| **All {family}** | {len(rows)} | "
                         + " | ".join(f"**{_pct(caught[c], len(rows))}**" for c in cols) + " |")

    secs = sorted(r["seconds"] for r in results)
    lines += ["", f"Median time per claim: {secs[len(secs) // 2]:.2f} s "
                  f"(slowest {secs[-1]:.2f} s), PDF documents only.", "",
              "F2 = clean edit (document re-printed with changed facts, no file traces). "
              "F5 = value painted over inside the PDF and the file saved again.",
              "pharmacy_qty is a known gap: quantities are inflated consistently, and this version has no rule "
              "comparing medicine quantities with the length of stay."]
    return "\n".join(lines) + "\n", summary


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m medcore_verify.evaluation")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    table, summary = evaluate(args.data, args.workers)
    print(table)
    if args.out:
        args.out.write_text(table)
        args.out.with_suffix(".json").write_text(json.dumps(summary, indent=2))
        print(f"Saved {args.out} and {args.out.with_suffix('.json')}")


if __name__ == "__main__":
    main()
