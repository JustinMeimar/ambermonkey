"""Shared JSONL parsing / aggregation for ambermonkey fossils.

The instrumented SpiderMonkey engine writes one JSONL file per JS-
hosting process into JS_INSTR_DIR. Fossil variants concatenate every
per-process file into observation stderr; each JSONL line still
carries `pid`, `proc`, `tid`, and `seq` so we can reconstruct the
per-process streams from the flat concatenation.

This module gives the five subsection analyzers a common view of that
data: iteration, live-set folding, per-marker checkpoint construction,
and cross-PID join by marker name.

Event schema (see js/src/jit/Instr.cpp):

  run-header         v, seq, ts_us, pid, proc, tid, rt, run_id, mode,
                     channels, wall_us_epoch
  pool-create        pool_id, pool_kind, mmap_bytes
  pool-unmap         pool_id
  jitcode-create     code_local_id, pool_id, bytes, owner
  jitcode-finalize   code_local_id
  script-create      script_local_id, source_id, source_class, line, col
  script-destroy     script_local_id
  baseline-compile   script_local_id, semantic_id, code_id,
                     method_bytes, metadata_bytes, num_ic_entries
  baseline-retire    script_local_id
  baseline-entries-retire script_local_id, entered_count
  ic-body-emit       ic_body_local_id, ic_body_id, cache_kind,
                     body_bytes, stub_data_bytes, coupling[...]
  ic-instance-attach site_local_id, script_local_id, ic_body_id,
                     engine, source_class
  ic-instance-detach site_local_id, script_local_id, ic_body_id,
                     reason, entered_count, is_fallback,
                     chain_length_before
  snapshot-marker    marker
  snapshot-footprint pool_id, pool_kind, mmap_bytes, used_bytes,
                     unused_bytes
  snapshot-live      live_pool_count, live_mmap_bytes,
                     live_ic_body_count, live_ic_body_bytes,
                     by_owner[{owner, count, code_bytes}]
  snapshot-smaps     start, end, size_kb, rss_kb, pss_kb, ...
  entries-flush      reason, script_count, scripts[...]
  entries-overflow   script_local_id
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Iterator


# JitCodeOwner enum values (Instr.cpp `NameOf(JitCodeOwner)`).
OWNER_TO_CLASS = {
    "baseline-script": "baseline_function",
    "baseline-ic":     "cacheir_body",
    "shared-ic":       "cacheir_body",
    "trampoline":      "other",
    "ion":             "ion_code",
    "regexp":          "other",
    "wasm":            "other",
    "other":           "other",
}

ARTIFACT_CLASSES = (
    "baseline_interp",
    "baseline_function",
    "cacheir_body",
    "ic_instance",
    "ion_code",
    "other",
)

# Gecko process-type strings (Instr.cpp `GetProcTag`).
GECKO_PROC_TO_ROLE = {
    "parent":       "parent",
    "content":      "content",
    "gpu":          "helper",
    "rdd":          "helper",
    "socket":       "helper",
    "vr":           "helper",
    "gmplugin":     "helper",
    "forkserver":   "helper",
    "utility":      "helper",
    "crashhelper":  "helper",
    "ipdlunittest": "helper",
    "jsshell":      "shell",
}


def process_role(proc: str) -> str:
    return GECKO_PROC_TO_ROLE.get(proc, "unknown")


def artifact_class(row: dict) -> str:
    """Best-effort mapping from event -> artifact class.

    - jitcode-create rows carry `owner`.
    - snapshot-live's `by_owner` array has one entry per owner.
    - ic-instance-attach maps to ic_instance regardless of engine.
    - ic-body-emit maps to cacheir_body (the immutable body).
    """
    kind = row.get("kind")
    if kind == "jitcode-create":
        return OWNER_TO_CLASS.get(row.get("owner", "other"), "other")
    if kind == "ic-body-emit":
        return "cacheir_body"
    if kind in ("ic-instance-attach", "ic-instance-detach"):
        return "ic_instance"
    if kind == "baseline-compile":
        return "baseline_function"
    return "other"


# ---------------------------------------------------------------------
# Event iteration
# ---------------------------------------------------------------------

def _iter_lines(source) -> Iterator[str]:
    """Yield JSONL lines from a directory, a file path, an iterable of
    lines/paths, or a raw string of newline-joined lines."""
    if isinstance(source, str):
        if os.path.isdir(source):
            for p in sorted(glob.glob(os.path.join(source, "*.jsonl"))):
                with open(p) as f:
                    yield from f
            return
        if os.path.isfile(source):
            with open(source) as f:
                yield from f
            return
        # Raw multi-line string.
        yield from source.splitlines()
        return

    if isinstance(source, (list, tuple)):
        # Could be list of paths or list of lines; disambiguate by
        # checking the first element.
        if source and isinstance(source[0], str) and (
                os.path.exists(source[0]) or "\n" not in source[0]
                and not source[0].startswith("{")):
            # Treat as paths.
            for item in source:
                if os.path.isdir(item):
                    for p in sorted(glob.glob(os.path.join(item, "*.jsonl"))):
                        with open(p) as f:
                            yield from f
                elif os.path.isfile(item):
                    with open(item) as f:
                        yield from f
                else:
                    yield item
            return
        yield from source
        return

    # File-like or arbitrary iterable.
    yield from source


def iter_events(source, sort_by_pid_seq: bool = True) -> Iterator[dict]:
    """Yield parsed JSONL event dicts.

    When `sort_by_pid_seq` is True (the default), events are grouped
    per-PID and yielded in stream order within each PID, but PIDs are
    interleaved in the order they first appear. This preserves per-
    process causality (create-then-finalize) without pretending a total
    wall-clock ordering across processes.
    """
    events: list[dict] = []
    bad = 0
    for line in _iter_lines(source):
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            bad += 1
            continue
    if bad:
        print(f"instr_stream: skipped {bad} malformed JSONL lines",
              file=sys.stderr)
    if not sort_by_pid_seq:
        yield from events
        return
    per_pid: dict[int, list[dict]] = defaultdict(list)
    order: list[int] = []
    for e in events:
        pid = int(e.get("pid", 0))
        if pid not in per_pid:
            order.append(pid)
        per_pid[pid].append(e)
    for pid in order:
        per_pid[pid].sort(key=lambda r: int(r.get("seq", 0)))
        yield from per_pid[pid]


# ---------------------------------------------------------------------
# Live set: incremental fold of the artifact-lifecycle stream.
# ---------------------------------------------------------------------

@dataclass
class LiveSet:
    """Incremental fold of definition + lifecycle events.

    Feed events with `.apply(event)`. At any point `.snapshot()` returns
    per-artifact-class counts and bytes reflecting the state after the
    last applied event.
    """
    # code_local_id -> (owner, bytes)
    _jitcode: dict[int, tuple[str, int]] = field(default_factory=dict)
    # script_local_id -> {source_class, code_id, method_bytes,
    #                     metadata_bytes, num_ic_entries}
    _scripts: dict[int, dict] = field(default_factory=dict)
    # ic_body_id (hex) -> {cache_kind, body_bytes, stub_data_bytes}
    _ic_bodies: dict[str, dict] = field(default_factory=dict)
    # (script_local_id, site_local_id) -> {ic_body_id, engine, source_class}
    _ic_instances: dict[tuple, dict] = field(default_factory=dict)
    # pool_id -> (pool_kind, mmap_bytes)
    _pools: dict[int, tuple[str, int]] = field(default_factory=dict)
    # Sticky "ever seen" tracking for lifecycle reconciliation.
    _scripts_ever_created: set[int] = field(default_factory=set)
    _ic_instances_ever_attached: set[tuple] = field(default_factory=set)
    # Attach/detach counters -- useful even for fallbacks where the
    # attach path never emits a create (HarvestIcChain emits fallback
    # detach unconditionally).
    _attach_count: int = 0
    _detach_count: int = 0
    _detach_fallback_count: int = 0
    # Violations recorded during fold. Cleared by reconcile().
    _violations: list[str] = field(default_factory=list)

    def apply(self, e: dict) -> None:
        k = e.get("kind")
        if k == "jitcode-create":
            self._jitcode[e["code_local_id"]] = (
                e.get("owner", "other"), int(e.get("bytes", 0)))
        elif k == "jitcode-finalize":
            self._jitcode.pop(e.get("code_local_id"), None)
        elif k == "script-create":
            sid = e["script_local_id"]
            self._scripts_ever_created.add(sid)
            self._scripts[sid] = {
                "source_class": e.get("source_class", "unknown"),
            }
        elif k == "baseline-compile":
            rec = self._scripts.setdefault(e["script_local_id"], {})
            rec.update({
                "code_id":         e.get("code_id"),
                "method_bytes":    int(e.get("method_bytes", 0)),
                "metadata_bytes":  int(e.get("metadata_bytes", 0)),
                "num_ic_entries":  int(e.get("num_ic_entries", 0)),
            })
        elif k == "script-destroy":
            sid = e.get("script_local_id")
            if sid is not None and sid not in self._scripts_ever_created:
                self._violations.append(
                    f"script-destroy without prior script-create: sid={sid}")
            self._scripts.pop(sid, None)
            # The engine cannot walk the IC chain from finalize (stubs
            # are already swept), so we treat script-destroy as an
            # implicit detach of every IC instance still attached to
            # this script. Count them as fallback-style implicit
            # detaches so the reconciler's non-fallback attach/detach
            # balance stays honest.
            implicit = [key for key in self._ic_instances
                        if key[0] == sid]
            for key in implicit:
                self._ic_instances.pop(key, None)
                self._detach_fallback_count += 1
        elif k == "baseline-retire":
            # Baseline retirement retracts the baseline compile but does
            # not by itself remove the script from the live set; the
            # script may still be executing under the interpreter.
            sid = e.get("script_local_id")
            rec = self._scripts.get(sid)
            if rec is not None:
                for key in ("code_id", "method_bytes", "metadata_bytes",
                            "num_ic_entries"):
                    rec.pop(key, None)
        elif k == "ic-body-emit":
            self._ic_bodies[e["ic_body_id"]] = {
                "cache_kind":      e.get("cache_kind", ""),
                "body_bytes":      int(e.get("body_bytes", 0)),
                "stub_data_bytes": int(e.get("stub_data_bytes", 0)),
            }
        elif k == "ic-instance-attach":
            key = (e["script_local_id"], e["site_local_id"])
            self._ic_instances_ever_attached.add(key)
            self._attach_count += 1
            self._ic_instances[key] = {
                "ic_body_id":   e.get("ic_body_id"),
                "engine":       e.get("engine"),
                "source_class": e.get("source_class"),
            }
        elif k == "ic-instance-detach":
            key = (e["script_local_id"], e["site_local_id"])
            is_fallback = bool(e.get("is_fallback", False))
            if is_fallback:
                self._detach_fallback_count += 1
            else:
                self._detach_count += 1
                if key not in self._ic_instances_ever_attached:
                    self._violations.append(
                        f"ic-instance-detach without prior attach: "
                        f"script={key[0]} site={key[1]}")
            self._ic_instances.pop(key, None)
        elif k == "pool-create":
            self._pools[e["pool_id"]] = (
                e.get("pool_kind", "other"), int(e.get("mmap_bytes", 0)))
        elif k == "pool-unmap":
            self._pools.pop(e.get("pool_id"), None)

    def snapshot(self) -> dict:
        """Return per-class {count, bytes} plus a supplementary
        `by_owner` breakdown from the raw jitcode fold."""
        by_class: dict[str, dict] = {
            c: {"count": 0, "bytes": 0} for c in ARTIFACT_CLASSES
        }
        by_owner: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "bytes": 0})

        for owner, nbytes in self._jitcode.values():
            cls = OWNER_TO_CLASS.get(owner, "other")
            by_class[cls]["count"] += 1
            by_class[cls]["bytes"] += nbytes
            by_owner[owner]["count"] += 1
            by_owner[owner]["bytes"] += nbytes

        # Baseline-compiled functions: we already counted their JitCode
        # via owner="baseline-script" above. But baseline-compile
        # events also carry method_bytes / metadata_bytes which reflect
        # allocation-rounded size. Expose those as a supplementary
        # measure so §3.1 can distinguish "code bytes" (JitCode) from
        # "alloc bytes" (JitScript struct + inline caches).
        bl_method_bytes = sum(s.get("method_bytes", 0)
                              for s in self._scripts.values())
        bl_metadata_bytes = sum(s.get("metadata_bytes", 0)
                                for s in self._scripts.values())

        # ic_instance: count only; instances carry no JitCode of their
        # own (their body bytes are shared via the cacheir_body pool).
        by_class["ic_instance"]["count"] = len(self._ic_instances)

        # cacheir_body: IC bodies are pooled, not tracked as separate
        # jitcode-create events. Their bytes come from ic-body-emit's
        # body_bytes field. Populate by_class from the interned dict
        # rather than the (always-empty) owner=baseline-ic bucket.
        cacheir_bytes = sum(b["body_bytes"] for b in self._ic_bodies.values())
        cacheir_stub_bytes = sum(b["stub_data_bytes"]
                                 for b in self._ic_bodies.values())
        by_class["cacheir_body"]["count"] = len(self._ic_bodies)
        by_class["cacheir_body"]["bytes"] = cacheir_bytes

        pool_bytes = sum(sz for (_, sz) in self._pools.values())

        return {
            "by_class": by_class,
            "by_owner": dict(by_owner),
            "baseline_function_method_bytes":   bl_method_bytes,
            "baseline_function_metadata_bytes": bl_metadata_bytes,
            "cacheir_body_interned_count":      len(self._ic_bodies),
            "cacheir_body_interned_bytes":      cacheir_bytes,
            "cacheir_body_stub_data_bytes":     cacheir_stub_bytes,
            "pool_count":                       len(self._pools),
            "pool_mmap_bytes":                  pool_bytes,
        }


# ---------------------------------------------------------------------
# Checkpoint construction
# ---------------------------------------------------------------------

@dataclass
class ProcessSnapshot:
    pid: int
    proc: str
    rt: int
    live: dict = field(default_factory=dict)
    footprint: list[dict] = field(default_factory=list)
    smaps: list[dict] = field(default_factory=list)
    entries_flush: dict | None = None
    snapshot_live: dict | None = None


@dataclass
class Checkpoint:
    marker: str
    processes: dict[int, ProcessSnapshot] = field(default_factory=dict)


def iter_checkpoints(events: Iterable[dict]) -> Iterator[Checkpoint]:
    """Yield one Checkpoint per snapshot-marker line.

    Each process's snapshot-* rows immediately follow its own
    snapshot-marker in the concatenated stream (Instr.cpp emits them
    sequentially under the same lock). We group by (marker, pid).

    Live sets are maintained per-PID across the entire stream; the
    checkpoint captures the LiveSet.snapshot() taken at the moment the
    marker fires.
    """
    live_per_pid: dict[int, LiveSet] = defaultdict(LiveSet)
    header_per_pid: dict[int, dict] = {}
    # marker string -> Checkpoint object (each marker string may fire
    # once per PID; we accumulate all PIDs under a single Checkpoint).
    open_ckpt: dict[str, Checkpoint] = {}
    # (pid, marker) -> ProcessSnapshot we are actively filling.
    active: dict[tuple[int, str], ProcessSnapshot] = {}

    def _flush() -> Iterator[Checkpoint]:
        # Nothing to flush proactively; callers get checkpoints on
        # subsequent snapshot-marker events. See the tail flush at end.
        return iter(())

    for e in events:
        kind = e.get("kind")
        pid = int(e.get("pid", 0))

        if kind == "run-header":
            header_per_pid[pid] = e

        if kind == "snapshot-marker":
            marker = e.get("marker", "")
            ckpt = open_ckpt.setdefault(marker, Checkpoint(marker=marker))
            ps = ProcessSnapshot(
                pid=pid,
                proc=e.get("proc", "unknown"),
                rt=int(e.get("rt", 0)),
                live=live_per_pid[pid].snapshot(),
            )
            ckpt.processes[pid] = ps
            active[(pid, marker)] = ps
            continue

        if kind == "snapshot-footprint":
            for (a_pid, _), ps in list(active.items()):
                if a_pid == pid:
                    ps.footprint.append(e)
                    break
            continue
        if kind == "snapshot-smaps":
            for (a_pid, _), ps in list(active.items()):
                if a_pid == pid:
                    ps.smaps.append(e)
                    break
            continue
        if kind == "snapshot-live":
            for (a_pid, _), ps in list(active.items()):
                if a_pid == pid:
                    ps.snapshot_live = e
                    break
            continue
        if kind == "entries-flush":
            for (a_pid, _), ps in list(active.items()):
                if a_pid == pid:
                    ps.entries_flush = e
                    break
            continue

        # Non-snapshot events advance the live set. Also closes the
        # process's active checkpoint slot (subsequent snapshot rows
        # would belong to a later marker).
        live_per_pid[pid].apply(e)
        for key in [k for k in active if k[0] == pid]:
            del active[key]

    # Emit checkpoints in the order they first appeared.
    for marker, ckpt in open_ckpt.items():
        yield ckpt


def group_processes_by_role(ckpt: Checkpoint) -> dict[str, list[ProcessSnapshot]]:
    out: dict[str, list[ProcessSnapshot]] = defaultdict(list)
    for ps in ckpt.processes.values():
        out[process_role(ps.proc)].append(ps)
    return dict(out)


# ---------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------

def reconcile(events: Iterable[dict],
              tolerance: float = 0.02) -> tuple[list[str], dict]:
    """Fold events once and return (violations, stats).

    Violations that BLOCK analyzer output (invariant breakages):
      - script-destroy without prior script-create
      - ic-instance-detach (non-fallback) without prior attach
      - process-shutdown missing at end of any PID's stream
      - LiveSet-derived owner byte totals diverge from snapshot-live
        by more than `tolerance` at any snapshot point

    Non-fatal stats returned for context:
      attach/detach counts, per-PID event counts, distinct bodies.

    The FOSSIL_ALLOW_RECONCILIATION_FAILURES=1 env var lets exploratory
    runs proceed despite violations; callers should honour it.
    """
    live_per_pid: dict[int, LiveSet] = defaultdict(LiveSet)
    shutdown_seen: dict[int, int] = defaultdict(int)
    events_per_pid: dict[int, int] = defaultdict(int)
    snapshot_live_seen: dict[int, int] = defaultdict(int)
    divergences: list[str] = []

    for e in events:
        pid = int(e.get("pid", 0))
        events_per_pid[pid] += 1
        kind = e.get("kind")

        if kind == "snapshot-live":
            # Compare LiveSet-derived byte total vs reported total.
            reported = sum(o.get("code_bytes", 0)
                           for o in e.get("by_owner", []))
            snap = live_per_pid[pid].snapshot()
            derived = sum(rec.get("bytes", 0)
                          for rec in snap.get("by_owner", {}).values())
            if reported > 0:
                delta = abs(derived - reported) / reported
                if delta > tolerance:
                    divergences.append(
                        f"pid={pid} snapshot-live divergence: "
                        f"derived={derived} reported={reported} "
                        f"delta={delta:.1%} > tol={tolerance:.1%}")
            snapshot_live_seen[pid] += 1
            continue

        if kind == "process-shutdown":
            shutdown_seen[pid] += 1
            continue

        live_per_pid[pid].apply(e)

    violations: list[str] = []
    for pid, ls in live_per_pid.items():
        for v in ls._violations:
            violations.append(f"pid={pid}: {v}")

    for pid in events_per_pid:
        if shutdown_seen[pid] == 0:
            violations.append(
                f"pid={pid}: missing process-shutdown at end of stream "
                f"(instrumentation atexit hook may not have fired)")

    violations.extend(divergences)

    stats = {
        "pids":                  len(events_per_pid),
        "events_per_pid":        dict(events_per_pid),
        "snapshot_live_seen":    dict(snapshot_live_seen),
        "attach_count_per_pid":  {p: ls._attach_count
                                  for p, ls in live_per_pid.items()},
        "detach_count_per_pid":  {p: ls._detach_count
                                  for p, ls in live_per_pid.items()},
        "detach_fallback_per_pid": {p: ls._detach_fallback_count
                                    for p, ls in live_per_pid.items()},
        "distinct_scripts":      {p: len(ls._scripts_ever_created)
                                  for p, ls in live_per_pid.items()},
        "distinct_ic_bodies":    {p: len(ls._ic_bodies)
                                  for p, ls in live_per_pid.items()},
    }
    return violations, stats


def variant_name() -> str:
    """Return the fossil variant name for the currently-analyzing record,
    if the fossil CLI supplied one via env. Falls back to '?'.
    """
    return os.environ.get("FOSSIL_VARIANT_NAME", "?")


# ---------------------------------------------------------------------
# Self-check invoked when run as a script.
# ---------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: instr_stream.py <dir-or-jsonl>", file=sys.stderr)
        sys.exit(2)
    src = sys.argv[1]
    events = list(iter_events(src))
    print(f"events: {len(events)}")
    kinds: dict[str, int] = defaultdict(int)
    for e in events:
        kinds[e.get("kind", "?")] += 1
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k:24s} {v}")
    ckpts = list(iter_checkpoints(iter(events)))
    print(f"checkpoints: {len(ckpts)}")
    for c in ckpts:
        roles = group_processes_by_role(c)
        print(f"  {c.marker!r}: "
              f"procs={len(c.processes)} "
              f"roles={ {r: len(ps) for r, ps in roles.items()} }")
