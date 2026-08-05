#!/usr/bin/env python3
"""Extract the content-process IC-body identity set and its
execution-weighted frequency map for one variant.

Content-only: parent-process ICs (browser chrome / frame scripts /
telemetry) load identically in every session and are a ~700-body
floor that swamps site-JS overlap.

Executed-only: static set = bodies with entered_count > 0. A body
that attached during setup but never re-executed is off-story here;
including it inflates the static set (many one-shot attaches on a
short browsertime page load) and lets an attach-vs-execute mismatch
generate spurious static/dynamic paradoxes. This filter puts both
triangles over the same population so Jaccard and coverage are
directly comparable.

Frequency source: summed enteredCount from the shutdown entries-flush
(still-live stubs) plus ic-instance-detach entered_count (churned
stubs). The two populations are disjoint so summing is exact.

Output shape (string-valued so fossil_figures loads as Metric.tag):
    {
      "hashes": "HEX,HEX,...",              # executed bodies (static)
      "freqs":  "HEX=n;HEX=n;...",          # exec-weighted (dynamic)
      "count":  <int>,
      "total_entered": <int>
    }
"""

import json
import sys


def main():
    obs = json.load(sys.stdin)
    ob = obs.get("observations", [obs])[0]
    out = ob.get("stdout")
    if isinstance(out, list):
        out = "\n".join(out)
    reduced = json.loads(out.strip())
    ic_content = ((reduced.get("ic") or {}).get("content") or {})
    attaches = ic_content.get("attaches") or {}
    entered = ic_content.get("entered") or {}

    if not attaches:
        print("ic_set: FATAL: no content-process IC-attach events",
              file=sys.stderr)
        sys.exit(1)
    if not entered:
        print("ic_set: FATAL: no content-process entered_count; "
              "shutdown flush + detach fold both empty",
              file=sys.stderr)
        sys.exit(1)

    executed = {h: n for h, n in entered.items() if n > 0}
    hashes = sorted(executed.keys())

    hashes_csv = ",".join(hashes)
    freqs_str = ";".join(f"{k}={v}" for k, v in sorted(executed.items(),
                                                       key=lambda kv: -kv[1]))
    total = sum(executed.values())
    json.dump({
        "hashes": hashes_csv,
        "freqs":  freqs_str,
        "count":  len(hashes),
        "total_entered": total,
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
