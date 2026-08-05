#!/usr/bin/env python3
"""Reduce a JS_INSTR_DIR of per-process JSONL into IC/baseline hash
frequency maps, split by process type (content vs parent).

Hash provenance is retained (not just anonymous ranked counts) so
downstream Jaccard-style analyses can join across variants.

Output shape:
    {
      "ic":       {"content": {"HEX": n, ...},
                   "parent":  {"HEX": n, ...}},
      "baseline": {"content": {"HEX": n, ...},
                   "parent":  {"HEX": n, ...}}
    }

Process type is read from the filename (`<proc>.<pid>.jsonl`, per
Instr.cpp JsonlSink::Open).

Crashes loudly on missing files or fields.

Usage: emit_ranks.py DIR   (writes JSON to stdout)
"""

import collections
import json
import os
import sys


def die(msg):
    print(f"emit_ranks: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse(path, ic, bl):
    with open(path) as f:
        for ln in f:
            if '"ic-instance-attach"' not in ln \
                    and '"baseline-compile"' not in ln:
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "ic-instance-attach":
                ic[o["ic_body_id"]] += 1
            elif k == "baseline-compile":
                bl[o["semantic_id"]] += 1


def main(root):
    ic = {"content": collections.Counter(), "parent": collections.Counter()}
    bl = {"content": collections.Counter(), "parent": collections.Counter()}
    n_files = 0
    for fn in sorted(os.listdir(root)):
        if not fn.endswith(".jsonl"):
            continue
        proc = fn.split(".", 1)[0]
        if proc not in ic:
            continue
        n_files += 1
        parse(os.path.join(root, fn), ic[proc], bl[proc])
    if n_files == 0:
        die(f"no content/parent .jsonl files in {root}")
    if not (ic["content"] or ic["parent"]):
        die("no ic-instance-attach events; InstrCh_IC disabled?")
    if not (bl["content"] or bl["parent"]):
        die("no baseline-compile events; InstrCh_Baseline disabled?")
    out = {
        "ic":       {p: dict(c) for p, c in ic.items()},
        "baseline": {p: dict(c) for p, c in bl.items()},
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
