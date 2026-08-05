#!/usr/bin/env python3
"""Cross-workload coverage over baseline artifacts.

Reads a sweep root produced by tp6-sweep.sh (one subdirectory per site,
each holding that run's per-process JSONL) and answers: for each
distinct artifact, in how many of the N workloads does it appear?

Artifacts present in all N are engine- or chrome-resident and are
redundant by construction. Artifacts present in one are site-specific.
The distribution of *bytes* over that axis is the AOT opportunity.
"""

import collections
import json
import os
import sys

IC = '"kind":"ic-body-emit"'
BL = '"kind":"baseline-compile"'
JC = '"kind":"jitcode-create"'


def read_site(d):
    """-> (ic{id:bytes}, bl{id:bytes}, owner_bytes{owner:bytes}) split by
    parent vs content."""
    out = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".jsonl"):
            continue
        proc = "parent" if fn.startswith("parent") else "content"
        ic, bl, ob = out.setdefault(proc, ({}, {}, collections.Counter()))
        with open(os.path.join(d, fn)) as f:
            for ln in f:
                if IC in ln:
                    o = json.loads(ln)
                    ic[o["ic_body_id"]] = o["body_bytes"]
                elif BL in ln:
                    o = json.loads(ln)
                    bl[o["semantic_id"]] = o["method_bytes"] + o["metadata_bytes"]
                elif JC in ln:
                    o = json.loads(ln)
                    ob[o["owner"]] += o["bytes"]
    for p in ("parent", "content"):
        out.setdefault(p, ({}, {}, collections.Counter()))
    return out


def coverage(per_site, idx):
    """per_site: {site: (ic, bl, ob)}. -> {artifact: (nsites, bytes)}"""
    n = collections.Counter()
    size = {}
    for site, t in per_site.items():
        for k, v in t[idx].items():
            n[k] += 1
            size[k] = v
    return {k: (n[k], size[k]) for k in n}


def report(label, cov, nsites):
    tot_b = sum(b for _, b in cov.values())
    print(f"\n=== {label}: {len(cov)} distinct, {tot_b/1024:.1f} KB")
    print(f"{'in N sites':>11}  {'count':>7}  {'KB':>9}  {'% bytes':>8}")
    hist = collections.Counter()
    hb = collections.Counter()
    for k, (n, b) in cov.items():
        hist[n] += 1
        hb[n] += b
    cum = 0
    for n in range(nsites, 0, -1):
        if not hist[n]:
            continue
        cum += hb[n]
        print(f"{n:>11}  {hist[n]:>7}  {hb[n]/1024:>9.1f}  {100*hb[n]/tot_b:>7.1f}%")
    # Bytes that would be paid once under a shared corpus vs once per site.
    naive = sum(n * b for n, b in cov.values())
    print(f"  sum over workloads : {naive/1024:9.1f} KB")
    print(f"  distinct (union)   : {tot_b/1024:9.1f} KB")
    print(f"  --> redundant      : {(naive-tot_b)/1024:9.1f} KB "
          f"({100*(naive-tot_b)/naive:.1f}%)")
    return hist, hb


def main(root):
    sites = sorted(
        d for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d))
        and any(f.endswith(".jsonl") for f in os.listdir(os.path.join(root, d)))
    )
    print(f"{len(sites)} workloads: {' '.join(sites)}")

    content = {}
    parent = {}
    owner = collections.Counter()
    for s in sites:
        r = read_site(os.path.join(root, s))
        content[s] = r["content"]
        parent[s] = r["parent"]
        owner.update(r["content"][2])
        owner.update(r["parent"][2])

    print(f"\n{'site':<20} {'ic n':>6} {'ic KB':>8} {'bl n':>6} {'bl KB':>9}")
    for s in sites:
        ic, bl, _ = content[s]
        print(f"{s:<20} {len(ic):>6} {sum(ic.values())/1024:>8.1f} "
              f"{len(bl):>6} {sum(bl.values())/1024:>9.1f}")

    n = len(sites)
    report("IC bodies (content procs)", coverage(content, 0), n)
    report("Baseline functions (content procs)", coverage(content, 1), n)
    report("Baseline functions (parent proc)", coverage(parent, 1), n)

    print("\n=== jitcode bytes by owner (all sites, all procs)")
    tot = sum(owner.values())
    for k, v in owner.most_common():
        print(f"  {k:<22} {v/1024/1024:>8.1f} MB  {100*v/tot:>5.1f}%")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/amber-sweep-structural")
