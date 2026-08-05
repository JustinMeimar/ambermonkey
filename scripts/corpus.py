#!/usr/bin/env python3
"""Baseline/IC corpus redundancy over a tp6 sweep.

Two redundancy axes are reported, and they answer different questions.

Within-instance (across the processes of one browser launch) is real
simultaneous resident memory: the same bytes exist P times right now.
This is the memory-savings claim and it scales with process count.

Across-workload (across separate launches, one per site) is not
concurrent memory. It says whether one AOT corpus generalizes, which
scopes what belongs in the corpus in the first place.

Artifacts are split by dedupability class:
  fixed      jitcode owned by the interpreter blob / trampolines,
             bit-identical in every process by construction
  selfhosted baseline code for self-hosted scripts, deterministic
  guest      baseline code for page and chrome script
"""

import collections
import json
import os
import sys

KINDS = ("script-create", "baseline-compile", "ic-body-emit", "jitcode-create")
PREFILTER = tuple('"kind":"%s"' % k for k in KINDS)

FIXED_OWNERS = {"baseline-interpreter", "trampoline", "shared-ic"}


class Proc:
    __slots__ = ("name", "site", "cls", "bl", "ic", "owner", "scripts",
                 "collisions")

    def __init__(self, name, site):
        self.name = name
        self.site = site
        self.cls = {}          # script_local_id -> source_class
        self.bl = {}           # semantic_id -> (bytes, source_class)
        self.ic = {}           # ic_body_id -> bytes
        self.owner = collections.Counter()
        self.scripts = collections.Counter()
        self.collisions = 0


def read_proc_multi(path):
    """semantic_id -> [bytes per compile]. Repeats mean the same source
    was compiled into more than one realm of the same process."""
    m = collections.defaultdict(list)
    with open(path) as f:
        for ln in f:
            if '"kind":"baseline-compile"' in ln:
                o = json.loads(ln)
                m[o["semantic_id"]].append(
                    o["method_bytes"] + o["metadata_bytes"])
    return m


def read_proc(path, site):
    # The `rt` field is not a usable join key: the runtime is registered
    # lazily, so script-create carries rt=0 while the baseline-compile
    # for that same script carries the assigned id. Each file is one
    # process, and script_local_id has been observed collision-free
    # within a file, so join on it alone and count any class conflict.
    p = Proc(os.path.basename(path).rsplit(".", 1)[0], site)
    pending = []
    with open(path) as f:
        for ln in f:
            if not any(s in ln for s in PREFILTER):
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "script-create":
                sid = o["script_local_id"]
                sc = o["source_class"]
                if p.cls.get(sid, sc) != sc:
                    p.collisions += 1
                p.cls[sid] = sc
                p.scripts[sc] += 1
            elif k == "baseline-compile":
                pending.append(o)
            elif k == "ic-body-emit":
                p.ic[o["ic_body_id"]] = o["body_bytes"]
            elif k == "jitcode-create":
                p.owner[o["owner"]] += o["bytes"]
    for o in pending:
        sc = p.cls.get(o["script_local_id"], "unknown")
        p.bl[o["semantic_id"]] = (o["method_bytes"] + o["metadata_bytes"], sc)
    return p


def load(root):
    sites = collections.OrderedDict()
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        procs = [read_proc(os.path.join(full, f), d)
                 for f in sorted(os.listdir(full)) if f.endswith(".jsonl")]
        if procs:
            sites[d] = procs
    return sites


def kb(n):
    return n / 1024.0


def redundancy(groups, pick):
    """groups: iterable of dicts {key: bytes}. -> (total, distinct)"""
    total = 0
    distinct = {}
    for g in groups:
        for k, b in pick(g):
            total += b
            distinct[k] = b
    return total, sum(distinct.values()), distinct


def sect(t):
    print("\n" + "=" * 66)
    print(t)
    print("=" * 66)


def within_instance(sites):
    """Per-launch, across processes. Real concurrent duplication."""
    sect("A. WITHIN-INSTANCE REDUNDANCY (across processes of one launch)")
    print(f"{'site':<20} {'proc':>5} {'self KB':>9} {'dist':>8} "
          f"{'guest KB':>10} {'dist':>9} {'fixed KB':>9}")
    agg = collections.Counter()
    for site, procs in sites.items():
        sh_t, sh_d, _ = redundancy(
            procs, lambda p: ((k, b) for k, (b, c) in p.bl.items()
                              if c == "self-hosted"))
        g_t, g_d, _ = redundancy(
            procs, lambda p: ((k, b) for k, (b, c) in p.bl.items()
                              if c != "self-hosted"))
        fixed = sum(v for p in procs for o, v in p.owner.items()
                    if o in FIXED_OWNERS)
        print(f"{site:<20} {len(procs):>5} {kb(sh_t):>9.1f} {kb(sh_d):>8.1f} "
              f"{kb(g_t):>10.1f} {kb(g_d):>9.1f} {kb(fixed):>9.1f}")
        agg["procs"] += len(procs)
        agg["sh_t"] += sh_t
        agg["sh_d"] += sh_d
        agg["g_t"] += g_t
        agg["g_d"] += g_d
        agg["fixed"] += fixed
    n = len(sites)
    print(f"\n  averaged over {n} launches, {agg['procs']/n:.1f} procs each")
    for lab, t, d in (("self-hosted", agg["sh_t"], agg["sh_d"]),
                      ("guest+chrome", agg["g_t"], agg["g_d"])):
        r = 100 * (t - d) / t if t else 0
        print(f"    {lab:<14} resident {kb(t)/n:8.1f} KB  distinct "
              f"{kb(d)/n:8.1f} KB  --> {r:5.1f}% duplicate")
    print(f"    {'fixed jitcode':<14} resident {kb(agg['fixed'])/n:8.1f} KB "
          f" (100% duplicate by construction)")


def per_process_floor(sites):
    """Bytes every process pays regardless of what it runs."""
    sect("B. PER-PROCESS FLOOR (jitcode owner mix)")
    tot = collections.Counter()
    nproc = 0
    per = collections.defaultdict(list)
    for procs in sites.values():
        for p in procs:
            nproc += 1
            for o, v in p.owner.items():
                tot[o] += v
                per[o].append(v)
    print(f"{nproc} processes over {len(sites)} launches\n")
    print(f"{'owner':<22} {'total MB':>9} {'%':>6} {'mean KB/proc':>13} "
          f"{'min KB':>8} {'procs':>6}")
    g = sum(tot.values())
    for o, v in tot.most_common():
        s = sorted(per[o])
        print(f"{o:<22} {v/1048576:>9.2f} {100*v/g:>5.1f}% "
              f"{kb(v)/nproc:>13.1f} {kb(s[0]):>8.1f} {len(s):>6}")
    fixed = sum(v for o, v in tot.items() if o in FIXED_OWNERS)
    if fixed:
        print(f"\n  fixed-by-construction: {kb(fixed)/nproc:.1f} KB/proc, "
              f"{fixed/1048576:.2f} MB over {nproc} procs")
    else:
        print("\n  NOTE: no baseline-interpreter/trampoline/shared-ic owners "
              "present.\n  Binary predates owner attribution; the blob is "
              "hiding inside 'other'.")


def cross_workload(sites):
    """Across launches. Does one corpus generalize?"""
    sect("C. CROSS-WORKLOAD COVERAGE (does an AOT corpus generalize?)")
    n = len(sites)

    def cov(pick):
        cnt = collections.Counter()
        size = {}
        for procs in sites.values():
            seen = {}
            for p in procs:
                for k, b in pick(p):
                    seen[k] = b
            for k, b in seen.items():
                cnt[k] += 1
                size[k] = b
        return cnt, size

    for lab, pick in (
        ("self-hosted baseline",
         lambda p: ((k, b) for k, (b, c) in p.bl.items()
                    if c == "self-hosted")),
        ("guest+chrome baseline",
         lambda p: ((k, b) for k, (b, c) in p.bl.items()
                    if c != "self-hosted")),
        ("IC bodies", lambda p: p.ic.items()),
    ):
        cnt, size = cov(pick)
        if not cnt:
            continue
        tot = sum(size.values())
        hb = collections.Counter()
        hn = collections.Counter()
        for k, c in cnt.items():
            hb[c] += size[k]
            hn[c] += 1
        naive = sum(c * size[k] for k, c in cnt.items())
        print(f"\n--- {lab}: {len(cnt)} distinct, {kb(tot):.1f} KB union")
        print(f"{'in N sites':>11} {'count':>8} {'KB':>10} {'% bytes':>9} "
              f"{'cum %':>8}")
        cum = 0.0
        for i in range(n, 0, -1):
            if not hn[i]:
                continue
            cum += 100 * hb[i] / tot
            print(f"{i:>11} {hn[i]:>8} {kb(hb[i]):>10.1f} "
                  f"{100*hb[i]/tot:>8.1f}% {cum:>7.1f}%")
        only1 = 100 * hb[1] / tot if tot else 0
        alln = 100 * hb[n] / tot if tot else 0
        print(f"  in exactly one site : {only1:5.1f}% of bytes")
        print(f"  in all {n:>2} sites      : {alln:5.1f}% of bytes")


def join_quality(sites):
    n = collections.Counter()
    col = 0
    for procs in sites.values():
        for p in procs:
            col += p.collisions
            for _, (b, c) in p.bl.items():
                n[c] += 1
    tot = sum(n.values())
    unk = 100 * n["unknown"] / tot if tot else 0
    print(f"  script join: {dict(n)}  unresolved {unk:.1f}%  "
          f"id collisions {col}")
    if unk > 5:
        print("  WARNING: high unresolved rate, class split is unreliable")


def intra_process(root):
    """Same source compiled once per realm inside a single process. All
    copies are simultaneously resident: the emitted machine code differs
    only in the script and IC pointers baked into it."""
    sect("D. INTRA-PROCESS DUPLICATION (same source, multiple realms)")
    rows = []
    emit = dist = 0
    for site in sorted(os.listdir(root)):
        d = os.path.join(root, site)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".jsonl"):
                continue
            m = read_proc_multi(os.path.join(d, fn))
            if not m:
                continue
            e = sum(sum(v) for v in m.values())
            s = sum(v[0] for v in m.values())
            emit += e
            dist += s
            rows.append((site, fn, e, e - s))
    if not emit:
        return
    rows.sort(key=lambda r: -r[3])
    print(f"  emitted   {emit/1048576:8.2f} MB over {len(rows)} compiling procs")
    print(f"  distinct  {dist/1048576:8.2f} MB")
    print(f"  duplicate {(emit-dist)/1048576:8.2f} MB  "
          f"({100*(emit-dist)/emit:.1f}%), {kb(emit-dist)/len(rows):.1f} KB/proc")
    print("\n  worst processes:")
    for site, fn, e, d in rows[:10]:
        print(f"    {site:<18} {fn:<22} emit {kb(e):>8.1f} KB  "
              f"dup {kb(d):>7.1f} KB  {100*d/e:>5.1f}%")


def main(root):
    sites = load(root)
    print(f"{len(sites)} launches: {' '.join(sites)}")
    join_quality(sites)
    within_instance(sites)
    per_process_floor(sites)
    cross_workload(sites)
    intra_process(root)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/amber-sweep-structural")
