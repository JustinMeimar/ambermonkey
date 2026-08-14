#!/usr/bin/env python3
"""Leave-one-site-out identity coverage over tp6_train.

For each training site w, form a candidate corpus from the other 23
training sites and measure the fraction of w's unique identities that
the candidate covers. Reported separately for IC bodies and for
baseline functions, so the design decision to include the first class
and exclude the second is a direct read of the same measurement.

Static identity coverage only. Dynamic entry coverage (fraction of w's
recorded compile requests whose identity is in the candidate corpus)
requires per-identity request counts the recorder does not emit -- it
writes one file per identity via O_EXCL and treats subsequent EEXISTs
as success, so multiplicity is not preserved on disk. Adding a compile
counter is a recorder-side change out of scope for this fossil; the
static number is already the evidence the design section needs.

Emits:

    {
      "kinds": {
        "ic": {
          "targets": [
            {"site": "amazon", "target_count": N, "covered": M, "pct": P},
            ...
          ],
          "median_pct": ..., "min_pct": ..., "max_pct": ...
        },
        "blfun": { ... }
      }
    }

Invoked as `fossil table loso`; arg 1 is the destination path.
"""

import json
import statistics
import sys
from pathlib import Path

CORPUS_DIR = Path("/tmp/amber-aot-corpus")
FOSSIL_DIR = Path(__file__).resolve().parent.parent
TRAIN_FILE = FOSSIL_DIR / "train.txt"

ARTIFACT_SUFFIX = ".aotb"
KINDS = {"ic": "ic-", "blfun": "blfun-"}

COLUMN_META = {
    "site":         {"label": "Site",           "align": "left",  "format": "str"},
    "ic_pct":       {"label": "IC coverage",    "align": "right", "format": "percent-str"},
    "blfun_pct":    {"label": "Blfun coverage", "align": "right", "format": "percent-str"},
    "ic_covered":   {"label": "IC covered",     "align": "right", "format": "int"},
    "ic_total":     {"label": "IC observed",    "align": "right", "format": "int"},
    "blfun_covered": {"label": "Blfun covered", "align": "right", "format": "int"},
    "blfun_total":  {"label": "Blfun observed", "align": "right", "format": "int"},
}
COLUMN_ORDER = ("site", "ic_pct", "ic_covered", "ic_total",
                "blfun_pct", "blfun_covered", "blfun_total")


def die(msg):
    sys.exit(f"loso: {msg}")


def read_sites_file(path):
    names = []
    for raw in path.read_text().splitlines():
        s = raw.split("#", 1)[0].strip()
        if s:
            names.append(s)
    if not names:
        die(f"{path} lists no sites")
    return names


def names_for_kind(site_dir, prefix):
    return {f.name for f in site_dir.iterdir()
            if f.name.startswith(prefix) and f.name.endswith(ARTIFACT_SUFFIX)}


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def fmt_pct(v):
    return f"{v:.1f}%"


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    train = read_sites_file(TRAIN_FILE)

    missing = [s for s in train if not (CORPUS_DIR / s).is_dir()]
    if missing:
        die(f"listed training sites without a per-site subdir under {CORPUS_DIR}: "
            f"{', '.join(missing)}")

    per_site = {}
    for site in train:
        per_site[site] = {k: names_for_kind(CORPUS_DIR / site, p) for k, p in KINDS.items()}

    kinds_out = {}
    per_row = {site: {"site": site} for site in train}
    for kind in KINDS:
        targets = []
        pcts = []
        for w in train:
            target = per_site[w][kind]
            others = set().union(*(per_site[s][kind] for s in train if s != w))
            covered = len(target & others)
            total = len(target)
            p = pct(covered, total)
            targets.append({"site": w, "target_count": total,
                            "covered": covered, "pct": p})
            pcts.append(p)
            per_row[w][f"{kind}_pct"] = fmt_pct(p)
            per_row[w][f"{kind}_covered"] = covered
            per_row[w][f"{kind}_total"] = total
        kinds_out[kind] = {
            "targets": targets,
            "median_pct": statistics.median(pcts),
            "min_pct": min(pcts),
            "max_pct": max(pcts),
        }

    output = {
        "kinds": kinds_out,
        "columns": [{"key": k, **COLUMN_META[k]} for k in COLUMN_ORDER],
        "rows": [[per_row[s][k] for k in COLUMN_ORDER] for s in train],
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
