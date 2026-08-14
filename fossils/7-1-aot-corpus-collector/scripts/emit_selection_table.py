#!/usr/bin/env python3
"""Emit the paper's corpus-selection table plus its headline scalars.

Combines a threshold sweep over per-site .aotb dirs under $CORPUS with a
count of the self-hosted baseline functions harvested at $SELFHOSTED. The
sweep is delegated to threshold_sweep.py so its accounting stays the sole
source of truth; this wrapper narrows the emitted columns to the two the
paper renders (ic_stubs, ic_kb) and pins the scalars the constants layer
reads (training_site_count, selected_threshold, self_hosted_function_count).

Invoked as `fossil table selection`, arg 1 is the destination path.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CORPUS_DIR = Path("/tmp/amber-aot-corpus")
SELFHOSTED_DIR = Path("/tmp/amber-aot-selfhosted")
SELECTED_THRESHOLD = 0.1
KEEP_COLUMNS = ("threshold", "ic_stubs", "ic_kb")
COLUMN_META = {
    "threshold": {"label": "Threshold", "align": "right", "format": "percent"},
    "ic_stubs": {"label": "IC bodies", "align": "right", "format": "int"},
    "ic_kb": {"label": "IC bodies (KB)", "align": "right", "format": "int"},
}


def die(msg):
    sys.exit(f"emit_selection_table: {msg}")


def run_sweep(corpus_dir):
    script = Path(__file__).parent / "threshold_sweep.py"
    result = subprocess.run(
        [sys.executable, str(script), str(corpus_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        die(f"threshold_sweep failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def count_self_hosted_functions(selfhosted_dir):
    if not selfhosted_dir.is_dir():
        die(f"{selfhosted_dir} is not a directory (record self-hosted first)")
    return sum(
        1 for p in selfhosted_dir.iterdir()
        if p.name.startswith("blfun-") and p.name.endswith(".aotb")
    )


def project_columns(sweep):
    columns = sweep["columns"]
    idx = {c: columns.index(c) for c in KEEP_COLUMNS}
    projected = [[row[idx[c]] for c in KEEP_COLUMNS] for row in sweep["rows"]]
    return projected


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None

    summary = run_sweep(CORPUS_DIR)
    sweep = summary["sweep"]
    rows = project_columns(sweep)

    output = {
        "training_site_count": summary["sites_populated"],
        "selected_threshold": SELECTED_THRESHOLD,
        "self_hosted_function_count": count_self_hosted_functions(SELFHOSTED_DIR),
        "text_size": 8,
        "cell_inset": 3,
        "columns": [
            {"key": key, **COLUMN_META[key]} for key in KEEP_COLUMNS
        ],
        "rows": rows,
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
