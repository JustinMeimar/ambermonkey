#!/usr/bin/env python3
"""Leave-one-out coverage of a shipped CacheIR stub corpus.

Answers the feasibility question behind JIT-restricted execution: if
the stub corpus is built from other workloads, what fraction of the
inline caches an unseen workload attaches at runtime are already in
it, and therefore attachable without generating any code?

Coverage is weighted by attach events, not by distinct bodies. A body
attached ten thousand times matters ten thousand times more to
throughput than one attached once, and the static count would hide
that.

Held-out means held out: for site S the corpus is the union over the
other 31 sites, so no site ever contributes to the corpus it is
scored against.
"""

import collections
import os
import sys

ATTACH = '"kind":"ic-instance-attach"'
BID = '"ic_body_id":"'
SCL = '"source_class":"'
ENG = '"engine":"'


def field(ln, key):
    i = ln.find(key)
    if i < 0:
        return None
    i += len(key)
    j = ln.find('"', i)
    return ln[i:j]


def scan(root):
    """site -> Counter(ic_body_id -> attach count), split by class."""
    sites = {}
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        per = {"guest": collections.Counter(),
               "self-hosted": collections.Counter()}
        for fn in sorted(os.listdir(full)):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(full, fn)) as f:
                for ln in f:
                    if ATTACH not in ln:
                        continue
                    b = field(ln, BID)
                    if not b or b.startswith("00000000"):
                        continue
                    c = field(ln, SCL)
                    if c not in per:
                        per[c] = collections.Counter()
                    per[c][b] += 1
        if any(per.values()):
            sites[d] = per
    return sites


def main(root):
    sites = scan(root)
    names = sorted(sites)
    print(f"{len(names)} sites\n")

    classes = ("guest", "self-hosted")
    print(f"{'held-out site':<20} " + " ".join(
        f"{c+' att%':>14}" for c in classes) + f"{'all att%':>10}"
        f"{'distinct%':>11}")

    agg = {c: [0, 0] for c in classes}
    agg["all"] = [0, 0]
    dis = [0, 0]
    for s in names:
        corpus = {c: set() for c in classes}
        for o in names:
            if o == s:
                continue
            for c in classes:
                corpus[c] |= set(sites[o].get(c, ()))
        row = []
        tot_h = tot_a = 0
        dh = da = 0
        for c in classes:
            cnt = sites[s].get(c, collections.Counter())
            a = sum(cnt.values())
            h = sum(v for b, v in cnt.items() if b in corpus[c])
            agg[c][0] += h
            agg[c][1] += a
            tot_h += h
            tot_a += a
            dh += sum(1 for b in cnt if b in corpus[c])
            da += len(cnt)
            row.append(f"{100*h/a:13.1f}%" if a else f"{'-':>14}")
        agg["all"][0] += tot_h
        agg["all"][1] += tot_a
        dis[0] += dh
        dis[1] += da
        print(f"{s:<20} " + " ".join(row) +
              (f"{100*tot_h/tot_a:9.1f}%" if tot_a else f"{'-':>10}") +
              (f"{100*dh/da:10.1f}%" if da else f"{'-':>11}"))

    print()
    for c in classes + ("all",):
        h, a = agg[c]
        if a:
            print(f"  {c:<14} attach-weighted coverage {100*h/a:5.1f}%  "
                  f"({h:,} of {a:,} attachments)")
    print(f"  {'distinct':<14} body coverage            "
          f"{100*dis[0]/dis[1]:5.1f}%  ({dis[0]:,} of {dis[1]:,} bodies)")

    # what a miss costs: how concentrated are attachments?
    tot = collections.Counter()
    for s in names:
        for c in classes:
            tot.update(sites[s].get(c, ()))
    n = sum(tot.values())
    cum = 0
    print(f"\n  attachment concentration over {len(tot):,} distinct bodies:")
    for k in (10, 50, 100, 500, 1000):
        cum = sum(v for _, v in tot.most_common(k))
        print(f"    top {k:>5} bodies serve {100*cum/n:5.1f}% of attachments")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/amber-sweep-structural")
