#!/usr/bin/env python3
"""Run the given command; emit peak child RSS and peak anonymous-executable
residency in kilobytes to stderr, grep-friendly; propagate exit code.

Peak RSS comes from getrusage(RUSAGE_CHILDREN).ru_maxrss after the child
exits. Peak anon-exec is polled from /proc/<pid>/smaps every 50 ms while
the child runs -- summing Rss over VMAs whose perms contain 'x' and whose
pathname is empty (anonymous mmaps, which is where SpiderMonkey's
ExecutableAllocator places all JIT pools)."""

import re
import resource
import subprocess
import sys
import threading
import time


HEADER_RE = re.compile(r"^[0-9a-f]+-[0-9a-f]+ [rwxp-]+ ")


def anon_exec_rss_kb(pid):
    """Sum Rss (kB) across anonymous executable VMAs in /proc/<pid>/smaps.
    Returns None if the pid vanishes mid-read."""
    total = 0
    match = False
    try:
        with open(f"/proc/{pid}/smaps") as fh:
            for line in fh:
                if HEADER_RE.match(line):
                    parts = line.split(maxsplit=5)
                    perms = parts[1]
                    path = parts[5].strip() if len(parts) == 6 else ""
                    match = "x" in perms and not path
                elif match and line.startswith("Rss:"):
                    total += int(line.split()[1])
    except OSError:
        return None
    return total


def poll(pid, out, stop, interval=0.05):
    while not stop.is_set():
        r = anon_exec_rss_kb(pid)
        if r is None:
            return
        if r > out["peak"]:
            out["peak"] = r
        time.sleep(interval)


p = subprocess.Popen(sys.argv[1:])
out = {"peak": 0}
stop = threading.Event()
t = threading.Thread(target=poll, args=(p.pid, out, stop), daemon=True)
t.start()
p.wait()
stop.set()
t.join(timeout=1.0)

r = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"peak_rss_kb={r.ru_maxrss}", file=sys.stderr, flush=True)
print(f"peak_anon_exec_kb={out['peak']}", file=sys.stderr, flush=True)
sys.exit(p.returncode)
