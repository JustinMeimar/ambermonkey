"""JetStream 3 suite → normalised metrics.

JetStream 3 emits per-subtest scores in four flavours (First, Worst,
Average, Geometric). Different fossils care about different reductions,
so this module exposes the primitives rather than forcing one shape:

    parse_overall(suite)     -> suite.value (with replicates[0] fallback)
    parse_startup(suite)     -> {startup_geomean_ms, startup_score, n_subtests}
    parse_geometric(suite)   -> {name: geomean_score} per subtest

Callers compose these into whatever meta shape their fossil emits.
"""

from __future__ import annotations

import math

from . import manifest, raptor

SUITE_NAME = "jetstream3"


def parse_overall(suite: dict, prefix: str = "jetstream3") -> float:
    """Return the suite-level score, falling back to replicates[0]."""
    overall = suite.get("value")
    if isinstance(overall, (int, float)):
        return float(overall)
    reps = suite.get("replicates") or []
    if reps and isinstance(reps[0], (int, float)):
        return float(reps[0])
    manifest.fail(prefix, "no suite-level score in raptor JSON")


def parse_startup(suite: dict, prefix: str = "jetstream3") -> dict:
    """Geomean of ``<name>-First`` subtest values, expressed two ways.

    startup_geomean_ms is the raw geomean in ms (lower is better).
    startup_score = 1000 / startup_geomean_ms so it composes with
    overall score on a higher-is-better axis.
    """
    subtests = suite.get("subtests") or []
    firsts = [
        s["value"] for s in subtests
        if s.get("name", "").endswith("-First")
        and isinstance(s.get("value"), (int, float))
        and s["value"] > 0
    ]
    if not firsts:
        manifest.fail(prefix, "no positive -First subtest values")
    startup_geomean_ms = math.exp(sum(math.log(v) for v in firsts) / len(firsts))
    return {
        "startup_geomean_ms": startup_geomean_ms,
        "startup_score": 1000.0 / startup_geomean_ms,
        "n_subtests": len(firsts),
    }


def parse_geometric(suite: dict, prefix: str = "jetstream3") -> dict:
    """Return ``{name: value}`` for each ``-Geometric`` subtest."""
    return {
        s["name"].removesuffix("-Geometric"): float(s["value"])
        for s in suite.get("subtests") or []
        if s.get("name", "").endswith("-Geometric")
        and isinstance(s.get("value"), (int, float))
        and s["value"] > 0
    }
