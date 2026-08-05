#!/usr/bin/env python3
"""Reduce a JS_INSTR_DIR of per-process JSONL into per-body IC
metrics, split by process type (content vs parent).

For each process type we emit two Counters keyed by ic_body_id:

    attaches  : sum of ic-instance-attach events. One count per time
                a stub is wired into an IC chain. Cheap; poor proxy
                for hotness (attach != execution).

    entered   : real per-stub execution counts. Composed from two
                complementary sources so every stub that ever ran
                contributes exactly once:
                  * entries-flush emitted at process shutdown
                    (JitInstrReporter observes xpcom-shutdown in the
                    parent and content-child-shutdown in content),
                    covering stubs still live when the flush fires.
                  * ic-instance-detach.entered_count, covering stubs
                    that were unplugged during the run and are gone
                    by shutdown.
                These populations are disjoint: a stub is either alive
                at shutdown (counted in flush) or gone (counted in
                detach), never both.

Baseline is attach-only; the instrumentation has no per-baseline-body
execution counter.

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
                    and '"baseline-compile"' not in ln
                    and '"entries-flush"' not in ln):
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "ic-instance-attach":
                s["attaches_ic"][o["ic_body_id"]] += 1
            elif k == "baseline-compile":
                s["attaches_bl"][o["semantic_id"]] += 1
            elif k == "ic-instance-detach":
                # Detached-before-shutdown stubs: no snapshot can see
                # them. Capture their lifetime enter counts here.
                if o.get("is_fallback"):
                    continue
                ec = int(o.get("entered_count", 0))
                if ec:
                    s["entered_ic"][o["ic_body_id"]] += ec
            elif k == "entries-flush":
                # Still-live stubs at shutdown: enter counts are
                # authoritative snapshots.
                s["flush_count"][0] += 1
                for row in o.get("scripts", []) or []:
                    for e in row.get("ic_entries", []) or []:
                        if e.get("is_fallback"):
                            continue
                        ec = int(e.get("entered_count", 0))
                        if ec:
                            s["entered_ic"][e["ic_body_id"]] += ec


def new_proc_state():
    return {
        "attaches_ic": collections.Counter(),
        "attaches_bl": collections.Counter(),
        "entered_ic":  collections.Counter(),
        "flush_count": [0],
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
    if (per_proc["content"]["flush_count"][0] == 0
            and per_proc["parent"]["flush_count"][0] == 0):
        die("no entries-flush events; either the Demand channel is off "
            "(JS_INSTR must include 'demand' or be 'all') or this Firefox "
            "does not yet have the runtime-shutdown flush patch")

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
