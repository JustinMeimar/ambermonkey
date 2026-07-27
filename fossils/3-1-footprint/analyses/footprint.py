#!/usr/bin/env python3
"""§3.1 footprint analyzer: live bytes per artifact class at each
synchronized checkpoint, split by process role.

Input:  fossil observation JSON on stdin (has `stderr` = JSONL lines
        from every JS-hosting process interleaved).
Output: analysis JSON on stdout with the shape described in the plan.
"""

import json
import os
import statistics
import sys
from collections import defaultdict

# Use realpath: fossil runs analyzers through the ~/.fossil/projects
# symlink, and abspath preserves symlinks, so ../../../scripts would
# resolve inside .fossil/ where the scripts dir doesn't exist.
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "scripts"))

from instr_stream import (  # noqa: E402
    ARTIFACT_CLASSES,
    iter_checkpoints,
    iter_events,
    group_processes_by_role,
    process_role,
)


def _stderr_lines(obs):
    err = obs.get("stderr", "")
    if isinstance(err, list):
        return err
    return err.splitlines() if err else []


def _classwise_bytes(ps_snapshot):
    """Extract per-class {bytes,count} from a ProcessSnapshot.live."""
    out = {}
    for cls, rec in ps_snapshot.get("by_class", {}).items():
        out[cls] = {"bytes": rec.get("bytes", 0), "count": rec.get("count", 0)}
    return out


def _aggregate_content(content_snaps):
    """Given a list of ProcessSnapshot objects (content role), return
    per-class median + range across PIDs."""
    per_class_bytes = defaultdict(list)
    per_class_count = defaultdict(list)
    for ps in content_snaps:
        for cls, rec in ps.live.get("by_class", {}).items():
            per_class_bytes[cls].append(rec.get("bytes", 0))
            per_class_count[cls].append(rec.get("count", 0))
    med, rng, cnt = {}, {}, {}
    for cls in ARTIFACT_CLASSES:
        vals = per_class_bytes.get(cls, [])
        med[cls] = statistics.median(vals) if vals else 0
        rng[cls] = [min(vals), max(vals)] if vals else [0, 0]
        cvals = per_class_count.get(cls, [])
        cnt[cls] = statistics.median(cvals) if cvals else 0
    return {"median_bytes": med, "range_bytes": rng, "median_count": cnt}


def _pss_by_role(ckpt):
    out = defaultdict(list)
    for ps in ckpt.processes.values():
        pss_kb = sum(r.get("pss_kb", 0) for r in ps.smaps)
        out[process_role(ps.proc)].append(pss_kb)
    return {r: (statistics.median(v) if v else 0) for r, v in out.items()}


def analyze(obs, variant):
    events = iter_events(_stderr_lines(obs))
    checkpoints = list(iter_checkpoints(events))
    out_ckpts = []
    for ck in checkpoints:
        by_role = group_processes_by_role(ck)
        # Parent: usually one process. Report singleton snapshot.
        parent_snaps = by_role.get("parent", [])
        parent = _classwise_bytes(parent_snaps[0].live) if parent_snaps else {}
        # Content: potentially many PIDs; report per-pid list + summary.
        content_snaps = by_role.get("content", [])
        content_list = [
            {"pid": ps.pid, "live": _classwise_bytes(ps.live)}
            for ps in content_snaps
        ]
        content_summary = _aggregate_content(content_snaps)
        # Shell: only present for shell variants; report as its own row.
        shell_snaps = by_role.get("shell", [])
        shell = _classwise_bytes(shell_snaps[0].live) if shell_snaps else {}

        # Cross-check: sum of LiveSet-derived code bytes across owners
        # vs snapshot-live.by_owner[*].code_bytes reported by the
        # engine. Divergence > 5% suggests missed events.
        for ps in ck.processes.values():
            if not ps.snapshot_live:
                continue
            reported = sum(o.get("code_bytes", 0)
                           for o in ps.snapshot_live.get("by_owner", []))
            derived = sum(rec.get("bytes", 0)
                          for rec in ps.live.get("by_owner", {}).values())
            if reported and abs(derived - reported) / reported > 0.05:
                print(f"footprint: reconciliation warning marker={ck.marker!r} "
                      f"pid={ps.pid} derived={derived} reported={reported}",
                      file=sys.stderr)

        out_ckpts.append({
            "marker": ck.marker,
            "n_processes": len(ck.processes),
            "parent": parent,
            "content_pids": content_list,
            "content_summary": content_summary,
            "shell": shell,
            "pss_kb_by_role": _pss_by_role(ck),
        })

    return {
        "variant": variant,
        "n_checkpoints": len(out_ckpts),
        "checkpoints": out_ckpts,
    }


def main():
    obs = json.load(sys.stdin)
    variant = obs.get("variant") or obs.get("meta", {}).get("variant", "?")
    if isinstance(obs.get("observations"), list) and obs["observations"]:
        obs = obs["observations"][0]
    result = analyze(obs, variant)
    json.dump(result, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
