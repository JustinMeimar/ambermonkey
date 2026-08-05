#!/usr/bin/env python3
"""Live JIT-code redundancy at AWSY checkpoints.

Differs from corpus.py in the one way that matters for a memory claim.
corpus.py counts every artifact ever allocated; over a 30-tab session
with tab churn that number is meaningless, because most of it has been
finalized. Here every quantity is taken from a synchronized snapshot:
what is resident at a checkpoint, nothing else.

Checkpoints are recovered by clustering snapshot markers on absolute
time (wall_us_epoch + ts_us), since the marker sequence number is
per-process and a process born mid-session has its own numbering.

Live baseline code is reconstructed from jitcode-create/finalize on
code_local_id, joined to baseline-compile by sequence adjacency: the
allocation is emitted immediately before the compile record and their
byte counts agree.
"""

import bisect
import collections
import json
import os
import sys

SKIP = ('"kind":"ic-instance-attach"', '"kind":"ic-instance-detach"',
        '"kind":"entries-flush"')

FIXED = ("baseline-interpreter", "trampoline", "shared-ic")


class Proc:
    __slots__ = ("pid", "kind", "epoch", "markers", "live", "foot",
                 "created", "finalized", "cls", "bl", "icb")

    def __init__(self, pid, kind):
        self.pid = pid
        self.kind = kind
        self.epoch = 0
        self.markers = []      # (abs_us, marker)
        self.live = []         # (abs_us, {owner: bytes}, mmap, ic_bytes)
        self.foot = []         # (abs_us, used, unused, mmap)
        self.created = {}      # code_local_id -> (abs_us, bytes, owner)
        self.finalized = {}    # code_local_id -> abs_us
        self.cls = {}          # script_local_id -> source_class
        self.bl = {}           # code_local_id -> (semantic_id, sclid, bytes)
        self.icb = {}          # ic_body_id -> bytes


def parse(path):
    p = None
    prev = None          # last jitcode-create seen
    pend_foot = []
    with open(path) as f:
        for ln in f:
            if any(s in ln for s in SKIP):
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "run-header":
                p = Proc(o["pid"], o["proc"])
                p.epoch = o["wall_us_epoch"]
                continue
            if p is None:
                continue
            t = p.epoch + o["ts_us"]
            if k == "jitcode-create":
                p.created[o["code_local_id"]] = (t, o["bytes"], o["owner"])
                prev = o
            elif k == "jitcode-finalize":
                p.finalized[o["code_local_id"]] = t
            elif k == "baseline-compile":
                if (prev is not None and prev["seq"] == o["seq"] - 1
                        and prev["owner"] == "baseline-script"
                        and prev["bytes"] == o["method_bytes"]):
                    p.bl[prev["code_local_id"]] = (
                        o["semantic_id"], o["script_local_id"],
                        o["method_bytes"] + o["metadata_bytes"])
            elif k == "script-create":
                p.cls[o["script_local_id"]] = o["source_class"]
            elif k == "ic-body-emit":
                p.icb[o["ic_body_id"]] = o["body_bytes"]
            elif k == "snapshot-marker":
                p.markers.append((t, o["marker"]))
            elif k == "snapshot-live":
                by = {d["owner"]: d["code_bytes"] for d in o["by_owner"]}
                p.live.append((t, by, o["live_mmap_bytes"],
                               o["distinct_ic_body_bytes"]))
                if pend_foot:
                    pend_foot = []
            elif k == "snapshot-footprint":
                p.foot.append((t, o["used_bytes"], o["unused_bytes"],
                               o["mmap_bytes"]))
    return p


CHECKPOINTS = ("Start", "StartSettled", "TabsOpen", "TabsOpenSettled",
               "TabsOpenForceGC", "TabsClosed", "TabsClosedExtra",
               "TabsClosedSettled", "TabsClosedForceGC")


def cluster(procs):
    """The parent drives the report fan-out, so its marker sequence is the
    global checkpoint clock. Content processes are matched to the nearest
    parent marker; a per-process sequence number cannot be used because a
    process born mid-session starts its own numbering at one."""
    par = max((p for p in procs if p.kind == "parent"),
              key=lambda p: len(p.markers))
    return [(t, CHECKPOINTS[i] if i < len(CHECKPOINTS) else m)
            for i, (t, m) in enumerate(sorted(par.markers))]


def assign(procs, cks, tol_us=20_000_000):
    """Each process snapshot goes to its nearest checkpoint. Adjacent AWSY
    checkpoints are only seconds apart, so a fixed window would alias them."""
    sel = [{} for _ in cks]
    ts = [t for t, _ in cks]
    for p in procs:
        for s in p.live:
            i = min(range(len(ts)), key=lambda j: abs(ts[j] - s[0]))
            if abs(ts[i] - s[0]) > tol_us:
                continue
            cur = sel[i].get(p.pid)
            if cur is None or abs(ts[i] - s[0]) < abs(ts[i] - cur[0]):
                sel[i][p.pid] = s
    return sel


def live_at(p, t):
    """code_local_ids resident in p at absolute time t."""
    out = []
    for cid, (ct, b, ow) in p.created.items():
        if ct > t:
            continue
        ft = p.finalized.get(cid)
        if ft is not None and ft <= t:
            continue
        out.append((cid, b, ow))
    return out


def mb(n):
    return n / 1048576.0


def kb(n):
    return n / 1024.0


def main(root):
    procs = []
    for fn in sorted(os.listdir(root)):
        if fn.endswith(".jsonl"):
            p = parse(os.path.join(root, fn))
            if p:
                procs.append(p)
    print(f"{len(procs)} processes "
          f"({sum(1 for p in procs if p.kind=='parent')} parent)")

    cks = cluster(procs)
    sel = assign(procs, cks)

    print(f"{'checkpoint':<20} {'procs':>6} {'code':>8} {'mmap':>8} {'slack':>8} "
          f"{'fixed':>8} {'bl-meth':>8} {'bl-ic':>7} {'ion':>7}")
    rows = []
    for ci, (t, name) in enumerate(cks):
        by = collections.Counter()
        mmap = 0
        n = 0
        for p in procs:
            s = sel[ci].get(p.pid)
            if s is None:
                continue
            n += 1
            for k, v in s[1].items():
                by[k] += v
            mmap += s[2]
        if not n:
            continue
        tot = sum(by.values())
        fixed = sum(by[o] for o in FIXED)
        rows.append((ci, name, n, by, mmap))
        print(f"{name:<20} {n:>6} {mb(tot):>7.2f}M {mb(mmap):>7.2f}M "
              f"{mb(mmap-tot):>7.2f}M {mb(fixed):>7.2f}M "
              f"{mb(by['baseline-script']):>7.2f}M "
              f"{mb(by['baseline-ic']):>6.2f}M {mb(by['ion']):>6.2f}M")

    pk = max(rows, key=lambda r: sum(r[3].values()))
    ci, name, n, by, mmap = pk
    tot = sum(by.values())
    print(f"\n{'='*66}\nPEAK CHECKPOINT: {name}, {n} processes\n{'='*66}")
    for o, v in by.most_common():
        print(f"  {o:<22} {mb(v):>7.2f} MB  {100*v/tot:>5.1f}%  "
              f"{kb(v)/n:>7.1f} KB/proc")
    print(f"  {'TOTAL code':<22} {mb(tot):>7.2f} MB")
    print(f"  {'mapped (RSS cost)':<22} {mb(mmap):>7.2f} MB  "
          f"slack {mb(mmap-tot):.2f} MB ({100*(mmap-tot)/mmap:.1f}%)")

    analyse_live(procs, sel[ci], tot, mmap)


def analyse_live(procs, sel, tot, mmap):
    """Redundancy among artifacts resident at one checkpoint."""
    per = []   # (proc, {semantic_id: [(bytes, class), ...]})
    for p in procs:
        s = sel.get(p.pid)
        if s is None:
            continue
        t = s[0]
        m = collections.defaultdict(list)
        for cid, b, ow in live_at(p, t):
            if ow != "baseline-script":
                continue
            r = p.bl.get(cid)
            if r is None:
                continue
            sid, sclid, tb = r
            m[sid].append((tb, p.cls.get(sclid, "unknown")))
        per.append((p, m))

    print(f"\n{'='*66}\nINTRA-PROCESS (same source, >1 realm), live only\n{'='*66}")
    emit = intra_d = 0
    rows = []
    for p, m in per:
        e = sum(b for v in m.values() for b, _ in v)
        d = sum(v[0][0] for v in m.values())
        if e:
            emit += e
            intra_d += d
            rows.append((p.pid, e, e - d))
    if emit:
        print(f"  live baseline  {mb(emit):8.2f} MB over {len(rows)} procs")
        print(f"  distinct       {mb(intra_d):8.2f} MB")
        print(f"  duplicate      {mb(emit-intra_d):8.2f} MB "
              f"({100*(emit-intra_d)/emit:.1f}%)")
        rows.sort(key=lambda r: -r[2])
        print("  worst:")
        for pid, e, d in rows[:8]:
            print(f"    {pid:<8} live {kb(e):>9.1f} KB  dup {kb(d):>8.1f} KB "
                  f"{100*d/e:>6.1f}%")

    print(f"\n{'='*66}\nINTER-PROCESS (same artifact in >1 live process)\n{'='*66}")
    inter = {}
    for lab, want in (("self-hosted", True), ("guest+chrome", False)):
        res = 0
        dist = {}
        for p, m in per:
            for sid, v in m.items():
                sh = any(c == "self-hosted" for _, c in v)
                if sh != want:
                    continue
                # intra-process copies are credited on the other axis
                res += v[0][0]
                dist[sid] = v[0][0]
        d = sum(dist.values())
        inter[lab] = res - d
        if res:
            print(f"  {lab:<14} resident {mb(res):7.2f} MB  distinct "
                  f"{mb(d):7.2f} MB  --> {100*(res-d)/res:5.1f}% duplicate")

    # The engine blob is not hashed, so (owner, size) stands in for identity.
    # Crediting one surviving copy per distinct size is conservative: it
    # treats every size variant as a genuinely different artifact.
    fixed = 0
    nfix = 0
    grp = collections.Counter()
    gproc = collections.defaultdict(set)
    for p in procs:
        s = sel.get(p.pid)
        if s is None:
            continue
        v = sum(s[1].get(k, 0) for k in FIXED)
        if v:
            fixed += v
            nfix += 1
        for cid, b, ow in live_at(p, s[0]):
            if ow in FIXED:
                grp[(ow, b)] += b
                gproc[(ow, b)].add(p.pid)
    fixed_rec = sum(v - k[1] for k, v in grp.items())
    print(f"  {'fixed blob':<14} resident {mb(fixed):7.2f} MB over {nfix} "
          f"procs ({kb(fixed)/nfix:.1f} KB each)")
    print(f"  {'':14} {len(grp)} distinct (owner,size) variants, "
          f"recoverable {mb(fixed_rec):.2f} MB "
          f"({100*fixed_rec/fixed:.1f}%)")
    print(f"  {'':14} variants in >=90% of procs:")
    for k, v in sorted(grp.items(), key=lambda x: -x[1])[:6]:
        print(f"  {'':16} {k[0]:<22} {k[1]:>7}B x{len(gproc[k]):>3} procs "
              f"{kb(v):>8.1f} KB")

    print(f"\n{'='*66}\nRECOVERABLE BUDGET at peak\n{'='*66}")
    terms = [
        ("per-process fixed blob", "AOT shared map", fixed_rec),
        ("self-hosted, cross-proc", "AOT shared map", inter["self-hosted"]),
        ("multi-realm, intra-proc", "pointer-free", emit - intra_d),
        ("guest, cross-proc", "pointer-free", inter["guest+chrome"]),
    ]
    s = 0
    for lab, mech, v in terms:
        s += v
        print(f"  {lab:<26} {mech:<16} {mb(v):>6.2f} MB "
              f"{100*v/tot:>5.1f}% of code {100*v/mmap:>5.1f}% of mapped")
    print(f"  {'TOTAL':<26} {'':<16} {mb(s):>6.2f} MB "
          f"{100*s/tot:>5.1f}% of code {100*s/mmap:>5.1f}% of mapped")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "/tmp/amber-awsy-tp6-0728-1309-K6YX")
