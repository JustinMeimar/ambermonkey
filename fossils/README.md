# fossils

Benchmark experiments for AmberMonkey. Each subdirectory is one fossil — a
self-contained experiment with a `fossil.toml` declaring its variants,
analyses, figures, and tables.

## Layout

```
fossils/
  project.toml          shared constants (@FIREFOX, @JSSHELL, ...)
  scripts/              cross-fossil utilities (figure_style, corpus, ...)
  <N-M-slug>/
    fossil.toml         experiment definition
    scripts/            experiment-local helpers (record, reduce, ...)
    analyses/           per-observation parsers
    figures/            figure and table emitters
    records/            fossil-managed observation store (do not edit)
```

## Fossils

| id  | topic                                          |
|-----|------------------------------------------------|
| 0-0 | hand-authored taxonomy tables                  |
| 3-1 | JIT allocation census on AWSY tp6              |
| 3-2 | intra-workload IC concentration (tp6, 8 sites) |
| 3-3 | inter-workload overlap (tp6, 8 sites)          |
| 7-1 | AOT corpus recorder over tp6 + self-hosted     |
| 7-2 | corpus coverage on held-out workloads          |
| 7-3 | Speedometer 3 tier ladder                      |
| 7-4 | AOT indirection overhead                       |
| 7-5 | per-process peak memory on Octane              |
| 7-6 | per-runtime memory scaling in the jsshell      |
| 7-7 | indirection microbenchmarks (perf cycles)      |
| 7-8 | AOT attachment cost (cpstartup)                |
| 7-9 | on-disk binary size                            |
| 9-1 | retired: JetStream 3 startup 2x2               |
| 9-3 | retired: AmberMonkey held-out performance      |

## Running

```
fossil bury <fossil>                          # run all variants
fossil bury <fossil> --variant <v1,v2...>     # run one
fossil bury <fossil> --dry-run                # print the expanded command
fossil analyze <fossil>                       # (re-)run analyses on records
fossil figure  <fossil> <figure-name>         # render a figure
fossil table   <fossil> <table-name>          # emit a JSON table
```

Variant strings are shell fragments with `@CONST` (from `project.toml`) and
`$VAR` (from the fossil's `[variables]`) substituted before execution.
Substitution is single-pass, so `$VAR` inside another variable is left
literal — inline instead of nesting.

## Style
- Fossil descriptions are one line: what is measured, not why.
- Figure scripts are decoupled from any particular variant set.
