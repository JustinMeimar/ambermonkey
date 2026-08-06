#!/usr/bin/env python3
"""Build a corpus from per-site recording dirs by soft-intersection sharing threshold and byte budget."""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

STRICT_SINGLETONS = ("configuration.aotb",)
LOOSE_SINGLETONS = ("interp.aotb",)
ARTIFACT_PREFIXES = ("blfun-", "ic-")
ARTIFACT_SUFFIX = ".aotb"
LINK_MODES = ("copy", "symlink", "hardlink")


def place(src: Path, dst: Path, mode: str) -> None:
    if mode == "copy":
        shutil.copy2(src, dst)
    elif mode == "symlink":
        os.symlink(src.resolve(), dst)
    elif mode == "hardlink":
        os.link(src, dst)
    else:
        raise ValueError(f"unknown link mode: {mode}")


def is_artifact(name: str) -> bool:
    return name.endswith(ARTIFACT_SUFFIX) and name.startswith(ARTIFACT_PREFIXES)


def discover_sites(root: Path) -> list[Path]:
    sites = sorted(p for p in root.iterdir() if p.is_dir())
    if not sites:
        sys.exit(f"soft_intersection: no per-site subdirs under {root}")
    return sites


def index_artifacts(sites: list[Path]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for site in sites:
        for f in site.iterdir():
            if not is_artifact(f.name):
                continue
            entry = index.get(f.name)
            if entry is None:
                index[f.name] = {"sites": [site.name], "size": f.stat().st_size, "src": f}
            else:
                entry["sites"].append(site.name)
    return index


def pick_singletons(sites: list[Path]) -> tuple[dict[str, Path], list[str]]:
    picks: dict[str, Path] = {}
    notes: list[str] = []
    for name in STRICT_SINGLETONS:
        candidates = [s / name for s in sites if (s / name).exists()]
        if not candidates:
            sys.exit(f"soft_intersection: no site produced {name}")
        digests = {hashlib.sha256(c.read_bytes()).hexdigest() for c in candidates}
        if len(digests) > 1:
            sys.exit(
                f"soft_intersection: {name} differs across sites "
                f"({len(digests)} distinct digests) — build mismatch"
            )
        picks[name] = candidates[0]
    for name in LOOSE_SINGLETONS:
        candidates = [s / name for s in sites if (s / name).exists()]
        if not candidates:
            sys.exit(f"soft_intersection: no site produced {name}")
        buckets: dict[str, list[Path]] = {}
        for c in candidates:
            buckets.setdefault(hashlib.sha256(c.read_bytes()).hexdigest(), []).append(c)
        if len(buckets) > 1:
            sizes = sorted(((len(v), k) for k, v in buckets.items()), reverse=True)
            notes.append(
                f"{name}: {len(buckets)} distinct digests across {len(candidates)} sites "
                f"(sizes={[n for n, _ in sizes]}); picking majority"
            )
        majority_digest = max(buckets, key=lambda k: len(buckets[k]))
        picks[name] = buckets[majority_digest][0]
    return picks, notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="dir containing per-site subdirs")
    ap.add_argument("output", type=Path, help="corpus dir to create")
    ap.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="min proportion of sites containing an artifact for eligibility (0..1); "
        "1.0 = strict intersection, 0.0 = union",
    )
    ap.add_argument(
        "--budget",
        type=int,
        required=True,
        help="total byte budget for hashed artifacts (singletons excluded)",
    )
    ap.add_argument("--force", action="store_true", help="overwrite output dir if it exists")
    ap.add_argument(
        "--mode",
        choices=LINK_MODES,
        default="copy",
        help="how to place picked artifacts into OUTPUT (default: copy)",
    )
    args = ap.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        sys.exit("soft_intersection: --threshold must be in [0, 1]")
    if args.budget <= 0:
        sys.exit("soft_intersection: --budget must be positive")

    if args.output.exists():
        if not args.force:
            sys.exit(f"soft_intersection: {args.output} exists (pass --force to overwrite)")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    sites = discover_sites(args.input)
    n_sites = len(sites)
    threshold_count = max(1, int(round(args.threshold * n_sites)))

    singletons, notes = pick_singletons(sites)
    for name, src in singletons.items():
        place(src, args.output / name, args.mode)

    index = index_artifacts(sites)
    eligible = [(name, meta) for name, meta in index.items()
                if len(meta["sites"]) >= threshold_count]
    eligible.sort(key=lambda kv: (-len(kv[1]["sites"]), kv[1]["size"]))

    picked_bytes = 0
    picked_count = 0
    skipped_over_budget = 0
    for name, meta in eligible:
        if picked_bytes + meta["size"] > args.budget:
            skipped_over_budget += 1
            continue
        place(meta["src"], args.output / name, args.mode)
        picked_bytes += meta["size"]
        picked_count += 1

    summary = {
        "sites": n_sites,
        "threshold": args.threshold,
        "threshold_count": threshold_count,
        "budget_bytes": args.budget,
        "artifacts_seen": len(index),
        "artifacts_eligible": len(eligible),
        "artifacts_picked": picked_count,
        "artifacts_skipped_over_budget": skipped_over_budget,
        "bytes_picked": picked_bytes,
        "singletons": sorted(singletons),
        "singleton_notes": notes,
        "mode": args.mode,
        "output": str(args.output),
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
