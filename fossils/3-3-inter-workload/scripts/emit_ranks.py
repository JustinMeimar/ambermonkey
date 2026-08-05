#!/usr/bin/env python3
"""Reduce a JS_INSTR_DIR of per-process JSONL into per-body IC
metrics, split by process type (content vs parent).

For each process type we emit two Counters keyed by ic_body_id:

    attaches  : sum of ic-instance-attach events. One count per time
                a stub is wired into an IC chain. Cheap and always
                available; poor proxy for hotness.

    entered   : sum of ic-instance-detach.entered_count over
                non-fallback detaches. This is the number of times
                the stub was executed while it was attached, sampled
                from every stub that got unplugged during the run
                (chain trimming, script destroy, GC purge, ...).

                Known bias: stubs still alive at process exit are
                NOT counted -- no shutdown sweep emits detach events
                for them. The bias systematically under-weights
                cold-startup-then-idle sites; hot loops that trigger
                churn are captured well.

Both maps are keyed by hex ic_body_id (source SHA of the CacheIR).
Baseline is attach-only; there's no per-body execution counter for
baseline scripts.

Output shape:
    {
      "ic": {
        "content": {"attaches": {"HEX": n}, "entered": {"HEX": n}},
        "parent":  { ...same shape... }
      },
      "baseline": {
        "content": {"attaches": {"HEX": n}},
        "parent":  {"attaches": {"HEX": n}}
      }
    }
"""

import collections
import json
import os
import sys


def die(msg):
    print(f"emit_ranks: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse(path, s):
    with open(path) as f:
        for ln in f:
            if ('"ic-instance-attach"' not in ln
                    and '"ic-instance-detach"' not in ln
                    and '"baseline-compile"' not in ln):
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "ic-instance-attach":
                s["attaches_ic"][o["ic_body_id"]] += 1
            elif k == "baseline-compile":
                s["attaches_bl"][o["semantic_id"]] += 1
            elif k == "ic-instance-detach":
                if o.get("is_fallback"):
                    continue
                ec = int(o.get("entered_count", 0))
                if ec:
                    s["entered_ic"][o["ic_body_id"]] += ec


def new_proc_state():
    return {
        "attaches_ic": collections.Counter(),
        "attaches_bl": collections.Counter(),
        "entered_ic":  collections.Counter(),
    }


def main(root):
    per_proc = {"content": new_proc_state(), "parent": new_proc_state()}

    n_files = 0
    for fn in sorted(os.listdir(root)):
        if not fn.endswith(".jsonl"):
            continue
        proc = fn.split(".", 1)[0]
        if proc not in per_proc:
            continue
        n_files += 1
        parse(os.path.join(root, fn), per_proc[proc])

    if n_files == 0:
        die(f"no content/parent .jsonl files in {root}")
    if not (per_proc["content"]["attaches_ic"]
            or per_proc["parent"]["attaches_ic"]):
        die("no ic-instance-attach events; InstrCh_IC disabled?")

    out = {"ic": {}, "baseline": {}}
    for proc, s in per_proc.items():
        out["ic"][proc] = {
            "attaches": dict(s["attaches_ic"]),
            "entered":  dict(s["entered_ic"]),
        }
        out["baseline"][proc] = {"attaches": dict(s["attaches_bl"])}

    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
