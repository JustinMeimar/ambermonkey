#!/usr/bin/env python3

import collections
import glob
import gzip
import json
import os
import re
import sys

# JS::CodeSizes fields, reported per zone as .../code/<field>. The first
# four sum to ExecutablePool::usedCodeBytes(), which is the same quantity
# the snapshot footprints report, so the two are directly comparable.
CODE_KINDS = ("ion", "baseline", "regexp", "other", "unused")
CODE_PATH = re.compile(r"/code/(%s)$" % "|".join(CODE_KINDS))
INSTR_PREFIX = "explicit/js-instrumentation/"
# Utility processes append extra keys, e.g. "Utility (pid 47038,
# sandboxingKind 0)", so the pid is not always the whole parenthetical.
PID_LABEL = re.compile(r"^(.*?)\s*\(pid (\d+)[,)]")


def die(message):
    print(f"emit_allocation_summary: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def load_perfherder(root):
    path = os.path.join(root, "perfherder-data.json")
    if not os.path.exists(path):
        return None
    with open(path) as stream:
        data = json.load(stream)

    suites = {}
    for index, suite in enumerate(data.get("suites", [])):
        name = suite.get("name", f"suite-{index}")
        if name in suites:
            die(f"duplicate Perfherder suite {name}")
        row = {key: value for key, value in suite.items()
               if key not in ("name", "subtests")}
        subtests = {}
        for subindex, subtest in enumerate(suite.get("subtests", [])):
            subname = subtest.get("name", f"subtest-{subindex}")
            if subname in subtests:
                die(f"duplicate Perfherder subtest {name}/{subname}")
            subtests[subname] = {
                key: value for key, value in subtest.items() if key != "name"
            }
        row["subtests"] = subtests
        suites[name] = row
    return {"framework": data.get("framework", {}), "suites": suites}


def read_memory_report(path):
    with gzip.open(path, "rb") as stream:
        data = json.load(stream)
    if data.get("version") != 1:
        die(f"{path}: unexpected memory report version {data.get('version')}")

    procs = {}
    for report in data["reports"]:
        label = PID_LABEL.match(report["process"])
        if label is None:
            die(f"{path}: unparseable process label {report['process']!r}")
        pid = int(label.group(2))
        proc = procs.get(pid)
        if proc is None:
            proc = procs[pid] = {
                "name": label.group(1),
                "code": dict.fromkeys(CODE_KINDS, 0),
                "instr": {},
                "has_js": False,
            }
        reported = report["path"]
        if "js-non-window" in reported:
            proc["has_js"] = True
        kind = CODE_PATH.search(reported)
        if kind is not None:
            proc["code"][kind.group(1)] += report["amount"]
        elif reported.startswith(INSTR_PREFIX):
            proc["instr"][reported[len(INSTR_PREFIX):]] = report["amount"]
    return procs


def load_memory_reports(root):
    reports = {}
    for path in sorted(glob.glob(os.path.join(root, "memory-report-*.json.gz"))):
        stem = os.path.basename(path)[len("memory-report-"):-len(".json.gz")]
        name, _, iteration = stem.rpartition("-")
        if not name or not iteration.isdigit():
            die(f"unparseable memory report filename {path}")
        key = (name, int(iteration))
        if key in reports:
            die(f"duplicate memory report for {key}")
        reports[key] = read_memory_report(path)
    if not reports:
        die(f"no memory-report-*.json.gz in {root}")
    return reports


def reporter_summary(report, snapshotted, mmap_by_pid):
    code = collections.Counter()
    instrumented = []
    join_mismatches = []
    for pid, proc in report.items():
        if "live-mmap-bytes" not in proc["instr"]:
            continue
        instrumented.append(pid)
        code.update(proc["code"])
        published = proc["instr"]["live-mmap-bytes"]
        if pid in mmap_by_pid and published != mmap_by_pid[pid]:
            join_mismatches.append({
                "pid": pid,
                "reported_mmap_bytes": published,
                "snapshot_mmap_bytes": mmap_by_pid[pid],
            })

    used = sum(code[kind] for kind in CODE_KINDS if kind != "unused")
    return {
        "code_by_kind": {kind: code[kind] for kind in CODE_KINDS},
        "code_used_bytes": used,
        "code_unused_bytes": code["unused"],
        "code_mapped_bytes": used + code["unused"],
        "processes_reported": len(report),
        "processes_with_js": sum(1 for p in report.values() if p["has_js"]),
        "processes_instrumented": len(instrumented),
        "processes_missing_snapshot": sorted(set(instrumented) - snapshotted),
        "mmap_join_mismatches": join_mismatches,
    }


def split_token(token):
    parts = token.split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        die(f"malformed snapshot token {token!r}")
    return parts[0], int(parts[1])


def physical_summary(rows):
    fields = ("size_kb", "rss_kb", "pss_kb", "shared_clean_kb",
              "shared_dirty_kb", "private_clean_kb", "private_dirty_kb",
              "referenced_kb", "anonymous_kb")
    result = {
        key.removesuffix("_kb") + "_bytes":
            sum(row.get(key, 0) for row in rows) * 1024
        for key in fields
    }
    result["mapping_count"] = len(rows)
    return result


class Proc:
    def __init__(self, pid, kind, epoch):
        self.pid = pid
        self.kind = kind
        self.epoch = epoch
        self.markers = []
        self.snapshots = collections.defaultdict(
            lambda: {"footprints": [], "live": None, "smaps": []})


def parse(path):
    proc = None
    marker = None
    with open(path) as stream:
        for line in stream:
            if not any(kind in line for kind in (
                    '"kind":"run-header"',
                    '"kind":"snapshot-marker"',
                    '"kind":"snapshot-footprint"',
                    '"kind":"snapshot-live"',
                    '"kind":"snapshot-smaps"')):
                continue
            event = json.loads(line)
            kind = event["kind"]
            if kind == "run-header":
                proc = Proc(event["pid"], event["proc"],
                            event["wall_us_epoch"])
                continue
            if proc is None:
                continue
            timestamp = proc.epoch + event["ts_us"]
            if kind == "snapshot-marker":
                marker = event["marker"]
                proc.markers.append((timestamp, marker))
            elif marker is None:
                die(f"{path}: {kind} before snapshot-marker")
            elif kind == "snapshot-footprint":
                proc.snapshots[marker]["footprints"].append(event)
            elif kind == "snapshot-live":
                if proc.snapshots[marker]["live"] is not None:
                    die(f"{path}: duplicate snapshot-live for {marker}")
                proc.snapshots[marker]["live"] = event
            elif kind == "snapshot-smaps":
                proc.snapshots[marker]["smaps"].append(event)
    return proc


def summarize(root):
    procs = []
    for filename in sorted(os.listdir(root)):
        if not filename.endswith(".jsonl"):
            continue
        proc = parse(os.path.join(root, filename))
        if proc is not None:
            procs.append(proc)
    if not procs:
        die(f"no valid .jsonl files in {root}")

    parents = [proc for proc in procs if proc.kind == "parent"]
    if not parents:
        die("no parent process log")
    parent = max(parents, key=lambda proc: len(proc.markers))
    if not parent.markers:
        die("parent process has zero snapshot-marker events")

    reports = load_memory_reports(root)

    checkpoints = []
    seen = set()
    for index, (timestamp, token) in enumerate(sorted(parent.markers)):
        if token in seen:
            die(f"parent emitted duplicate snapshot token {token}")
        seen.add(token)
        name, iteration = split_token(token)
        report = reports.get((name, iteration))
        rows = []
        for proc in procs:
            snapshot = proc.snapshots.get(token)
            if snapshot is None or snapshot["live"] is None:
                continue
            live = snapshot["live"]
            footprints = snapshot["footprints"]
            footprint_mmap = sum(row["mmap_bytes"] for row in footprints)
            if footprint_mmap != live["live_mmap_bytes"]:
                die(f"pid {proc.pid}: footprint/live mmap mismatch at "
                    f"{token}: {footprint_mmap} != "
                    f"{live['live_mmap_bytes']}")
            rows.append({
                "pid": proc.pid,
                "kind": proc.kind,
                "live_by_owner": {
                    row["owner"]: row["code_bytes"]
                    for row in live["by_owner"]
                },
                "mmap_bytes": live["live_mmap_bytes"],
                "pool_used_bytes": sum(row["used_bytes"]
                                       for row in footprints),
                "pool_unused_bytes": sum(row["unused_bytes"]
                                         for row in footprints),
                "smaps": physical_summary(snapshot["smaps"]),
                "reporter_code": (report[proc.pid]["code"]
                                  if report and proc.pid in report else None),
            })
        snapshotted = {row["pid"] for row in rows}
        mmap_by_pid = {row["pid"]: row["mmap_bytes"] for row in rows}
        checkpoints.append({
            "index": index,
            "name": name,
            "iteration": iteration,
            "token": token,
            "abs_us": timestamp,
            "procs": rows,
            "reporter": (reporter_summary(report, snapshotted, mmap_by_pid)
                         if report is not None else None),
        })

    peak = max(checkpoints, key=lambda checkpoint: sum(
        sum(proc["live_by_owner"].values()) for proc in checkpoint["procs"]))
    result = {
        "n_processes": len(procs),
        "n_parent": len(parents),
        "checkpoints": checkpoints,
        "peak_checkpoint_index": peak["index"],
        "checkpoints_without_report": [
            checkpoint["token"] for checkpoint in checkpoints
            if checkpoint["reporter"] is None
        ],
    }
    perfherder = load_perfherder(root)
    if perfherder is not None:
        result["perfherder"] = perfherder
    return result


def main():
    print(json.dumps(summarize(sys.argv[1])))


if __name__ == "__main__":
    main()
