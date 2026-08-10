#!/usr/bin/env python3
"""Sample /proc/<pid>/smaps_rollup for every firefox / plugin-container
process whose exe lives under the given browser bin dir. One JSON object
per (timestamp, pid) written to stdout, flushed per sample."""

import json
import os
import sys
import time


FIELDS = (
    "Rss", "Pss",
    "Private_Clean", "Private_Dirty",
    "Shared_Clean", "Shared_Dirty",
    "Anonymous",
)
BASENAMES = ("firefox", "firefox-bin", "plugin-container")


def die(msg):
    print(f"smaps_sampler: {msg}", file=sys.stderr)
    raise SystemExit(1)


def matching_pids(bin_dir):
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            exe = os.readlink(f"/proc/{entry}/exe")
        except OSError:
            continue
        d, base = os.path.split(exe)
        if d == bin_dir and base in BASENAMES:
            yield int(entry), base


def read_rollup(pid):
    try:
        with open(f"/proc/{pid}/smaps_rollup") as fh:
            out = {}
            for line in fh:
                key, _, rest = line.partition(":")
                key = key.strip()
                if key not in FIELDS:
                    continue
                value = rest.strip()
                if not value.endswith(" kB"):
                    continue
                out[key] = int(value[:-3])
            return out
    except OSError:
        return None


def main():
    if len(sys.argv) != 3:
        die("usage: smaps_sampler.py <bin_dir> <interval_sec>")
    bin_dir = os.path.realpath(sys.argv[1])
    interval = float(sys.argv[2])
    if not os.path.isdir(bin_dir):
        die(f"not a directory: {bin_dir}")
    while True:
        ts = time.time()
        for pid, base in matching_pids(bin_dir):
            r = read_rollup(pid)
            if r is None:
                continue
            row = {"ts": ts, "pid": pid, "exe": base}
            for f in FIELDS:
                row[f.lower()] = r.get(f, 0)
            print(json.dumps(row), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
