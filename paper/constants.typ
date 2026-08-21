// Paper-facing named citations grouped by source fossil.
// Each entry composes a JSON accessor (json-field / cell-value /
// cell-from-table) with a formatter (pct / mb / kb / int-str / words)
// so the draft can read a bare `#foo` and get a ready-to-print string.

#import "lib/tables.typ": cell-value, json-field, cell-from-table
#import "lib/configurations.typ": config-name, config-short, config-prose
#import "lib/cite.typ": *


// --- Execution-configuration display-name aliases ---
// Never write "AmberMonkey" / "Baseline JIT" / etc. as literal strings in
// prose or captions. Use these constants so the whole paper tracks the
// registry at fossils/configurations.toml.
#let interp-only-name = config-name("interp-only")
#let interp-only-prose = config-prose("interp-only")
#let am     = config-prose("aot-corpus")
#let am-ic  = config-prose("aot-corpus-ic")
#let am-ion = config-prose("aot")
#let baseline-jit = config-prose("default-no-ion")
#let default-ion  = config-prose("default")


// --- 7-1 corpus construction (complete tp6-Train union) ---
#let tp6-train-site-count = int-str(json-field("7-1-composition.json", "train_site_count"))
#let tp6-test-site-count  = int-str(json-field("7-1-composition.json", "test_site_count"))
#let tp6-site-count       = int-str(json-field("7-1-composition.json", "total_site_count"))
#let ic-stub-count        = int-str(json-field("7-1-composition.json", "train_union_ic_count"))
#let ic-stub-bytes        = kb(json-field("7-1-composition.json", "train_union_ic_bytes"))
#let self-hosted-fn-count = int-str(json-field("7-1-composition.json", "self_hosted_function_count"))


// --- 3-3 inter-workload coverage ---
// Site keys used to prettify the argmin pair. Small enough to live here;
// promote to a taxonomy JSON if a second consumer appears.
#let _site-display = (
  amazon: "Amazon", "bing-search": "Bing Search", buzzfeed: "BuzzFeed",
  cnn: "CNN", ebay: "eBay", espn: "ESPN", expedia: "Expedia", facebook: "Facebook",
)
#let _medians = json-field("inter-workload-coverage.json", "medians")
#let _argmin  = json-field("inter-workload-coverage.json", "ic_coverage_argmin")
#let inter-baseline-jaccard-median  = float-str(_medians.baseline_jaccard)
#let inter-ic-jaccard-median        = float-str(_medians.ic_jaccard)
#let inter-baseline-coverage-median = pct(_medians.baseline_coverage)
#let inter-ic-coverage-median       = pct(_medians.ic_coverage)
#let inter-site-count               = int-str(json-field("inter-workload-coverage.json", "site_count"))
#let inter-baseline-cnn-range     = range-pct(json-field("inter-workload-coverage.json", "baseline_coverage_per_target").cnn)
#let inter-baseline-expedia-range = range-pct(json-field("inter-workload-coverage.json", "baseline_coverage_per_target").expedia)
#let inter-ic-threshold-pct       = pct(json-field("inter-workload-coverage.json", "ic_coverage_threshold"))
#let inter-ic-pairs-at-threshold  = int-str(json-field("inter-workload-coverage.json", "ic_coverage_pairs_at_or_above_threshold"))
#let inter-ic-offdiag-count       = int-str(json-field("inter-workload-coverage.json", "off_diagonal_count"))
#let inter-ic-min-value           = pct(_argmin.value)
#let inter-ic-min-corpus          = _site-display.at(_argmin.corpus)
#let inter-ic-min-target          = _site-display.at(_argmin.target)


// --- 7-2 held-out corpus coverage ---
#let sp3-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "speedometer3")
#let js3-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "jetstream3")
#let tp6-test-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "tp6_test")


// --- 7-3 restricted-execution Speedometer perf ---
// Ratios come from the tier-ladder table's aggregate score; the ratio equals
// the geometric mean of the 20 per-workload speedups.
#let _sp3-aot-ratio      = cell-value("restricted-execution-perf.json", "aot-corpus",     "ratio_over_interp")
#let _sp3-aot-ic-ratio   = cell-value("restricted-execution-perf.json", "aot-corpus-ic",  "ratio_over_interp")
#let _sp3-bl-ratio       = cell-value("restricted-execution-perf.json", "default-no-ion", "ratio_over_interp")
#let _sp3-default-ratio  = cell-value("restricted-execution-perf.json", "default",        "ratio_over_interp")
#let sp3-aot-speedup           = pct(json-field("restricted-execution-perf.json", "aot_over_interp_speedup"))
#let sp3-aot-ic-speedup        = pct(json-field("restricted-execution-perf.json", "aot_ic_over_interp_speedup"))
#let sp3-aot-default-fraction  = pct(json-field("restricted-execution-perf.json", "aot_over_default_ratio"))
#let sp3-aot-ratio             = float-str(_sp3-aot-ratio)     + "×"
#let sp3-aot-ic-ratio          = float-str(_sp3-aot-ic-ratio)  + "×"
#let sp3-bl-ratio              = float-str(_sp3-bl-ratio)      + "×"
#let sp3-default-ratio         = float-str(_sp3-default-ratio) + "×"
#let sp3-aot-over-bl-fraction  = pct(_sp3-aot-ratio / _sp3-bl-ratio)
#let sp3-workload-count        = int-str(20)


// --- Speedometer 3 engine-memory reduction at Peak ---
// Compare the Ion-disabled runtime-Baseline and AOT-only configurations so
// both measurements have the same tier ceiling.
#let _jit-memory-runtime-pss = cell-value("cross-process-memory-sharing-aggregate.json", "default-no-ion", "per_proc_engine_pss_mb")
#let _jit-memory-aot-pss     = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus",     "per_proc_engine_pss_mb")
#let jit-memory-reduction    = pct(1 - _jit-memory-aot-pss / _jit-memory-runtime-pss)


// --- 7-7 indirection microbenchmark aggregate (Geometric mean row) ---
#let indirection-reps            = json-field("7-7-cycles.json", "repetitions_per_configuration")
#let indirection-benchmark-count = words(json-field("7-7-cycles.json", "benchmark_count"))
#let indirection-targeted-count  = words(json-field("7-7-cycles.json", "targeted_benchmark_count"))
#let indirection-control-count   = words(json-field("7-7-cycles.json", "control_benchmark_count"))
#let indirection-repetitions     = words(indirection-reps)
#let indirection-process-word    = if indirection-reps == 1 { "process" } else { "processes" }
#let indirection-ratio           = float-str(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ratio")) + "×"
#let indirection-overhead        = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_overhead"))
#let indirection-ipi-overhead    = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ipi_overhead"))
#let indirection-ipc-delta       = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ipc_delta"))


// --- 7-10 AWSY cross-process JIT memory (TabsOpenForceGC anchor) ---
#let _awsy-stock-engine-pss      = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "engine_pss_mb")
#let _awsy-aot-engine-pss        = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "engine_pss_mb")
#let _awsy-stock-per-proc-pss    = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "per_proc_engine_pss_mb")
#let _awsy-aot-per-proc-pss      = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "per_proc_engine_pss_mb")
#let _awsy-stock-anon-exec-pss   = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "anon_exec_pss_mb")
#let _awsy-aot-anon-exec-pss     = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "anon_exec_pss_mb")
#let _awsy-stock-libxul-exec-pss = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "libxul_exec_pss_mb")
#let _awsy-aot-libxul-exec-pss   = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "libxul_exec_pss_mb")
#let _awsy-stock-libxul-exec-rss = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "libxul_exec_rss_mb")
#let _awsy-aot-libxul-exec-rss   = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "libxul_exec_rss_mb")

#let awsy-content-procs           = int-str(cell-value("7-10-aggregate.json", "awsy-tp6-stock", "n_procs"))
#let awsy-stock-engine-pss        = mb-str(_awsy-stock-engine-pss)
#let awsy-aot-engine-pss          = mb-str(_awsy-aot-engine-pss)
#let awsy-stock-per-proc-pss      = mb-str(_awsy-stock-per-proc-pss)
#let awsy-aot-per-proc-pss        = mb-str(_awsy-aot-per-proc-pss)
#let awsy-engine-pss-reduction    = pct(1 - _awsy-aot-engine-pss / _awsy-stock-engine-pss)
#let awsy-per-proc-pss-reduction  = pct(1 - _awsy-aot-per-proc-pss / _awsy-stock-per-proc-pss)
#let awsy-anon-exec-pss-reduction = pct(1 - _awsy-aot-anon-exec-pss / _awsy-stock-anon-exec-pss)
#let awsy-libxul-exec-rss-growth  = pct(_awsy-aot-libxul-exec-rss / _awsy-stock-libxul-exec-rss - 1)
#let awsy-stock-libxul-sharing    = float-str(_awsy-stock-libxul-exec-rss / _awsy-stock-libxul-exec-pss, digits: 1) + "×"
#let awsy-aot-libxul-sharing      = float-str(_awsy-aot-libxul-exec-rss / _awsy-aot-libxul-exec-pss, digits: 1) + "×"


// --- 7-11 Speedometer 3 cross-process sharing (Peak checkpoint) ---
// Sourced from the aggregate-table rows so the numbers in prose track the
// figure automatically. Intentionally does not export a reduction-vs-stock
// scalar: aot-corpus runs a different tier profile than stock, so no direct
// engine-PSS delta is defensible. The matched no-Ion comparison is above.
#let _sp3-stock-libxul-exec-pss = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "libxul_exec_pss_mb")
#let _sp3-aot-libxul-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "libxul_exec_pss_mb")
#let _sp3-stock-libxul-exec-rss = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "libxul_exec_rss_mb")
#let _sp3-aot-libxul-exec-rss   = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "libxul_exec_rss_mb")
#let _sp3-stock-anon-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "anon_exec_pss_mb")
#let _sp3-aot-anon-exec-pss     = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "anon_exec_pss_mb")
#let _sp3-stock-per-proc-pss    = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "per_proc_engine_pss_mb")
#let _sp3-runtime-per-proc-pss  = _jit-memory-runtime-pss
#let _sp3-aot-per-proc-pss      = _jit-memory-aot-pss

#let sp3-content-procs           = int-str(cell-value("cross-process-memory-sharing-aggregate.json", "default", "n_procs"))
#let sp3-stock-per-proc-pss      = mb-str(_sp3-stock-per-proc-pss)
#let sp3-runtime-per-proc-pss    = mb-str(_sp3-runtime-per-proc-pss)
#let sp3-aot-per-proc-pss        = mb-str(_sp3-aot-per-proc-pss)
#let sp3-stock-anon-exec-pss     = mb-str(_sp3-stock-anon-exec-pss)
#let sp3-aot-anon-exec-pss       = mb-str(_sp3-aot-anon-exec-pss)
#let sp3-stock-libxul-sharing    = float-str(_sp3-stock-libxul-exec-rss / _sp3-stock-libxul-exec-pss, digits: 1) + "×"
#let sp3-aot-libxul-sharing      = float-str(_sp3-aot-libxul-exec-rss / _sp3-aot-libxul-exec-pss, digits: 1) + "×"

// Marginal cost of adding the AOT image, expressed both as physical PSS
// growth and as mapped RSS growth. The RSS/PSS ratio of the delta captures
// how effectively the new file-backed pages are shared across content procs.
#let _sp3-image-pss-growth       = _sp3-aot-libxul-exec-pss - _sp3-stock-libxul-exec-pss
#let _sp3-image-rss-growth       = _sp3-aot-libxul-exec-rss - _sp3-stock-libxul-exec-rss
#let sp3-image-pss-growth        = mb-str(_sp3-image-pss-growth, digits: 1)
#let sp3-image-rss-growth        = mb-str(_sp3-image-rss-growth, digits: 1)
#let sp3-image-sharing-amplification = float-str(_sp3-image-rss-growth / _sp3-image-pss-growth, digits: 1) + "×"

// interp-only floor: no JIT backend attached, so anon-exec should be zero.
// Its per-proc engine PSS is the shared-image contribution alone, and gives
// the lower bound the JIT configurations are measured against.
#let _sp3-interp-anon-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "interp-only", "anon_exec_pss_mb")
#let _sp3-interp-per-proc-pss    = cell-value("cross-process-memory-sharing-aggregate.json", "interp-only", "per_proc_engine_pss_mb")
#let sp3-interp-anon-exec-pss    = mb-str(_sp3-interp-anon-exec-pss)
#let sp3-interp-per-proc-pss     = mb-str(_sp3-interp-per-proc-pss)


// --- 7-9 binary-size impact (libxul-focused) ---
// Row labels match the human-readable "Configuration" column of 7-9-libxul.json.
#let _libxul-default = cell-value("7-9-libxul.json", "Default JIT",       "pt_load_bytes")
#let _libxul-aot     = cell-value("7-9-libxul.json", "Default JIT + AOT", "pt_load_bytes")
#let _libxul-image   = cell-value("7-9-libxul.json", "Default JIT + AOT", "linked_image_bytes")
#let _libxul-growth  = _libxul-aot - _libxul-default
#let libxul-default-size = mb(_libxul-default)
#let libxul-aot-size     = mb(_libxul-aot)
#let libxul-growth       = mb(_libxul-growth)
#let libxul-growth-pct   = pct(_libxul-growth / _libxul-default, digits: 2)
#let aot-image-size      = mb(_libxul-image)
#let corpus-packed-size  = mb(cell-value("7-9-libxul.json", "Default JIT + AOT", "packed_image_bytes"))
#let nonimage-growth     = kb(_libxul-growth - _libxul-image)
