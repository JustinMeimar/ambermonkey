#!/usr/bin/env python3
"""Extract the content-process IC-body identity set and its
execution-weighted frequency map for one variant.

Content-only: parent-process ICs (browser chrome / frame scripts /
telemetry) load identically in every session and are a ~700-body
floor that swamps site-JS overlap. The AOT-sharing story around
parent-chrome ICs is real but orthogonal.

Frequency source: `entered` counts summed from ic-instance-detach
events (see emit_ranks.py for the sampling bias -- stubs alive at
process exit are not counted). This is a lower bound on real stub
hotness, biased against long-lived cold stubs; hot-loop stubs that
churn through the chain are captured well, which is what the
coverage-across-workloads question actually cares about.

Output shape (string-valued so fossil_figures loads as Metric.tag):
    {
      "hashes": "HEX,HEX,...",              # for static Jaccard
      "freqs":  "HEX=n;HEX=n;...",          # detach-weighted hotness
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

    # Static set: union of every body ever wired up in content. A
    # body that attached but got no detach-sampled executions is
    # still part of the compiled inventory a shared corpus would
    # have to hold.
    hashes = sorted(set(attaches) | set(entered))
    # Weighted frequency for coverage: real executions per body,
    # sampled via detach. Bodies with zero sampled executions are
    # omitted from the freq map (weight zero); they contribute to
    # the static set only.
    freqs = {h: entered[h] for h in hashes if entered.get(h, 0) > 0}

    hashes_csv = ",".join(hashes)
    freqs_str = ";".join(f"{k}={v}" for k, v in sorted(freqs.items(),
                                                       key=lambda kv: -kv[1]))
    total = sum(freqs.values())
    json.dump({
        "hashes": hashes_csv,
        "freqs":  freqs_str,
        "count":  len(hashes),
        "total_entered": total,
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
