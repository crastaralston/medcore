"""Generate synthetic claim files.

    python -m medcore_verify.datagen dataset --out ../data/claims --per-diagnosis 10
    python -m medcore_verify.datagen samples --out ../data/samples
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .forge import F2_VARIANTS, F5_VARIANTS, Forgery, forge
from .render import render_claim
from .scenarios import DIAGNOSES, make_claim

# diagnosis_upgrade relabels a claim as dengue, so it only makes sense on non-dengue claims.
VARIANT_DIAGNOSES = {"diagnosis_upgrade": ("typhoid",)}


def write_claim(folder: Path, files: dict[str, bytes], truth: dict) -> None:
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    (folder / "truth.json").write_text(json.dumps(truth, indent=2))


def truth_for(claim_id: str, diagnosis: str, forgery: Forgery | None) -> dict:
    return {
        "claim_id": claim_id,
        "diagnosis": diagnosis,
        "genuine": forgery is None,
        "forgery_type": forgery.forgery_type if forgery else None,
        "variant": forgery.variant if forgery else None,
        "changed_document": forgery.document if forgery else None,
        "description": forgery.description if forgery else "Unchanged genuine claim",
    }


def build_dataset(out: Path, per_diagnosis: int, seed: int) -> int:
    """Genuine claims plus forged ones made from separate base claims."""
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    s = seed
    for dx in DIAGNOSES:
        for i in range(per_diagnosis):
            s += 1
            cid = f"G-{dx}-{i:03d}"
            claim = make_claim(cid, dx, s)
            write_claim(out / cid, render_claim(claim), truth_for(cid, dx, None))
            count += 1
    for ftype, variants in (("F2", F2_VARIANTS), ("F5", F5_VARIANTS)):
        for variant in variants:
            for dx in VARIANT_DIAGNOSES.get(variant, DIAGNOSES):
                n = per_diagnosis // 3 if variant not in VARIANT_DIAGNOSES else per_diagnosis
                for i in range(max(n, 1)):
                    s += 1
                    cid = f"{ftype}-{variant}-{dx}-{i:03d}"
                    files, forgery = forge(make_claim(cid, dx, s), ftype, variant, seed=s * 7)
                    write_claim(out / cid, files, truth_for(cid, dx, forgery))
                    count += 1
    return count


SAMPLES = [
    ("01_genuine_dengue", "dengue", None, None),
    ("02_edited_lab_value_dengue", "dengue", "F2", "lab_value"),
    ("03_upgraded_diagnosis_typhoid", "typhoid", "F2", "diagnosis_upgrade"),
    ("04_painted_over_total_appendicitis", "appendicitis", "F5", "overlay_total"),
    ("05_padded_room_days_typhoid", "typhoid", "F2", "room_days"),
    ("06_tripled_pharmacy_qty_dengue", "dengue", "F2", "pharmacy_qty"),
]


def build_samples(out: Path, seed: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for i, (name, dx, ftype, variant) in enumerate(SAMPLES):
        claim = make_claim(name, dx, seed + i)
        if ftype is None:
            files, forgery = render_claim(claim), None
        else:
            files, forgery = forge(claim, ftype, variant, seed=seed + 100 + i)
        write_claim(out / name, files, truth_for(name, dx, forgery))
    return len(SAMPLES)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m medcore_verify.datagen")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dataset", help="genuine and forged claims for evaluation")
    d.add_argument("--out", type=Path, required=True)
    d.add_argument("--per-diagnosis", type=int, default=10)
    d.add_argument("--seed", type=int, default=2026)
    sm = sub.add_parser("samples", help="six named demo claims for the web app")
    sm.add_argument("--out", type=Path, required=True)
    sm.add_argument("--seed", type=int, default=41)
    dm = sub.add_parser("demo", help="the demo pack: sample claims, ABOUT.md notes and page pictures")
    dm.add_argument("--out", type=Path, required=True, help="the demo folder, e.g. ../demo")
    args = parser.parse_args()
    if args.cmd == "dataset":
        n = build_dataset(args.out, args.per_diagnosis, args.seed)
    elif args.cmd == "samples":
        n = build_samples(args.out, args.seed)
    else:
        from .demo import build_demo  # imports this module, so it is loaded only when needed
        n = len(build_demo(args.out))
        args.out = args.out / "claims"
    print(f"Wrote {n} claims to {args.out}")


if __name__ == "__main__":
    main()
