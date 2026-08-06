#!/usr/bin/env python3
"""Sweep sharing thresholds over a per-site corpus and report picked count/bytes at each. Hashed artifacts only (blfun-, ic-); singletons excluded."""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_THRESHOLDS = [1.0, 0.75, 0.5, 0.25, 0.10, 0.05, 0.0]
ARTIFACT_PREFIXES = ("blfun-", "ic-")
ARTIFACT_SUFFIX = ".aotb"
KINDS = ("blfun", "ic")


def is_artifact(name: str) -> bool:
    return name.endswith(ARTIFACT_SUFFIX) and name.startswith(ARTIFACT_PREFIXES)


def kind_of(name: str) -> str:
    return name.split("-", 1)[0]


def index_corpus(root: Path) -> tuple[list[Path], dict[str, dict]]:
    if not root.exists():
        sys.exit(f"threshold_sweep: {root} does not exist")
    if not root.is_dir():
        sys.exit(f"threshold_sweep: {root} is not a directory")
    sites = sorted(p for p in root.iterdir() if p.is_dir())
    if not sites:
        sys.exit(f"threshold_sweep: no per-site subdirs under {root}")

    populated = [s for s in sites if any(is_artifact(f.name) for f in s.iterdir())]
    if not populated:
        sys.exit(f"threshold_sweep: no populated per-site subdirs under {root}")

    index: dict[str, dict] = {}
    for s in populated:
        for f in s.iterdir():
            if not is_artifact(f.name):
                continue
            e = index.get(f.name)
            if e is None:
                index[f.name] = {"sites": 1, "size": f.stat().st_size, "kind": kind_of(f.name)}
            else:
                e["sites"] += 1
    return populated, index


def sweep(index: dict[str, dict], n_sites: int, thresholds: list[float]) -> dict:
    columns = ["threshold", "min_sites", "artifacts_picked", "bytes_picked"]
    for k in KINDS:
        columns.extend([f"{k}_artifacts", f"{k}_bytes"])
    rows = []
    for t in thresholds:
        min_sites = max(1, int(round(t * n_sites)))
        eligible = [m for m in index.values() if m["sites"] >= min_sites]
        row = [t, min_sites, len(eligible), sum(m["size"] for m in eligible)]
        for k in KINDS:
            kind_elig = [m for m in eligible if m["kind"] == k]
            row.extend([len(kind_elig), sum(m["size"] for m in kind_elig)])
        rows.append(row)
    return {"columns": columns, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="dir containing per-site subdirs")
    ap.add_argument(
        "--thresholds",
        default=",".join(str(t) for t in DEFAULT_THRESHOLDS),
        help=f"comma-separated thresholds in [0, 1] (default: {','.join(str(t) for t in DEFAULT_THRESHOLDS)})",
    )
    args = ap.parse_args()

    thresholds = sorted({float(t) for t in args.thresholds.split(",")}, reverse=True)
    for t in thresholds:
        if not 0.0 <= t <= 1.0:
            sys.exit(f"threshold_sweep: threshold {t} out of [0, 1]")

    populated, index = index_corpus(args.input)
    n_sites = len(populated)

    all_dirs = [p for p in args.input.iterdir() if p.is_dir()]

    summary: dict = {
        "input": str(args.input),
        "sites_populated": n_sites,
        "sites_all": len(all_dirs),
        "sites_empty": sorted(p.name for p in all_dirs if p not in populated),
        "union_artifacts": len(index),
        "union_bytes": sum(m["size"] for m in index.values()),
    }
    for k in KINDS:
        kind_index = [m for m in index.values() if m["kind"] == k]
        summary[f"union_{k}_artifacts"] = len(kind_index)
        summary[f"union_{k}_bytes"] = sum(m["size"] for m in kind_index)
    summary["sweep"] = sweep(index, n_sites, thresholds)
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
