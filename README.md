# Storm-POMDP Benchmarking Utilities

## Interactive configuration selection

When creating an invocation file interactively with `python3 scripts/run.py`,
choose one or more configuration families instead of individual
configurations:

- `discretisation` selects every declared discretisation configuration.
- `cutoff` selects every declared cut-off configuration, including `cut00`.
- `clipping` selects every declared clipping configuration, including the
  heuristic `clip00res*` variants.
- `clip-mini` selects only `clip16res02` (threshold $2^{16}$ and clipping
  resolution 2).
- `MDP` selects the fully observable MDP configuration.

Every interactive menu displays numbered options; enter the number shown to
select an option. The textual option ids, `a` (all), `c` (clear), and `d`
(done) continue to work as well.

Adding a configuration to one of these families in `scripts/storm.py` makes
it available automatically in the corresponding interactive selection.

## Offline HTML results

Open `data/html/index.html` in a browser to view all 4,826 recorded runs across
38 instances and 127 configurations. The export follows the toolpaper package's
offline table: filter benchmarks, sort columns, show or hide entire families or
individual configurations, and switch between bounds, runtimes, and resulting
belief-MDP state counts. The compact reproduction preset selects resolutions
2, 5, and 12 in both discretisation modes, explicit exploration thresholds
`2^8, 2^12, ..., 2^32`, the heuristic thresholds, and clipping resolutions 2--4.
It filters the existing measurements; it does not change their 1,800-second
run limit or launch experiments.

Green cells mark the best visible under-approximation (CUT/CLIP) and
over-approximation (DISCR/MDP) separately, using six-decimal comparisons and
runtime tie-breaking. Exact under-approximation results take precedence, as in
the summary tables. Packet objectives and Crypt sizes are labelled separately.
Each recorded cell links to an individual page containing the invocation,
result, status, return codes, metadata, and an escaped preview of the source log.
Each page provides a compressed download of the complete log. Large previews
show only the beginning and end, keeping the offline export small.
Timeouts, non-timeout SIGKILLs (`killed`), and identified memory errors are
distinguished. Derived best-configuration selections are excluded from measured
run counts and total runtime.

Generate only this export from the existing parsed data, without rerunning
experiments or regenerating the thesis tables:

```sh
python3 scripts/html_results.py
```

Optional `--data-dir PATH` and `--output-dir PATH` arguments select other input
and output directories. Normal postprocessing also generates the HTML export.
Share the entire `data/html/` directory, including `logs/`, `results.css`, and
`results.js`. It works directly from local files, without a web server or
internet connection; full source logs are included as `.log.gz` files alongside
the run pages. Unchanged compressed logs are reused on subsequent exports.

## Copyable thesis plots

`data/tikzpictures/` is the single plot export: eight `.tex` files, each
containing one self-contained `tikzpicture`. All data are inline. Copy the code
into the dissertation, or input a file inside your own figure environment.
Load PGFPlots and `\usepgfplotslibrary{statistics}` in the document preamble.
Fonts and text spacing are inherited; existing TikZ externalisation works
without additional package macros or wrappers.

Regenerate the pictures and their audit data from the existing parsed JSON:

```sh
python3 scripts/export_tikzpictures.py
```

Normal postprocessing uses the same pipeline. Intermediate panels and legends
exist only in a temporary directory. Numeric exports are kept once under
`data/plot-data/`, and all 19 retained tables remain in `data/tables-general/`.
The sole preview is `data/storm-table-check.pdf`; its source inputs the same
eight pictures rather than maintaining another set of plot sources.

| Picture | Content |
|---|---|
| `discretisation-budget.tex` | Instances improving on MDP versus per-run time budget |
| `discretisation-resolution.tex` | Normalised improvement and runtime by resolution |
| `cut-vs-clip-runtime.tex` | Matched-threshold CUT/CLIP runtime comparison |
| `drone-threshold.tex` | Drone bounds, runtimes, and resulting MDP sizes |
| `cut-outcomes-heatmap.tex` | CUT outcomes for every instance and explicit threshold |
| `cut-bound-overview.tex` | Bound improvement and outcome counts by threshold |
| `combined-bounds.tex` | Interval tightness for three bound combinations |
| `discretisation-exact-reference.tex` | DISCR error on the 13 exact CUT cases |

## Over-approximation tables

Postprocessing generates separate tables for probability and reward objectives
and each optimisation direction (`prbmin`, `prbmax`, `rewmin`, `rewmax`):

- `data/tables-general/overapprox/tableoverapprox<objective>.tex`: MDP, the fastest successful
  discretisation whose bound matches or improves on MDP, and tightest
  discretisation.
- `data/tables-general/overapprox/tableoverapproxresolution<objective>.tex`: resolutions 2, 5, and 12,
  with static and dynamic in paired columns for each resolution.

Under-approximation tables are written to `data/tables-general/underapprox/`. For each
objective, `tableunderapprox*.tex` groups the heuristic and tightest cut-off runs,
followed by the heuristic clipping runs at resolutions 2 through 4 and the tightest
clipping run. The tightest columns use the 1800-second
meta-configurations and show their selected parameters. Detailed tables of all
cut-off and clipping thresholds are no longer generated.
Benchmark and combined result tables remain directly in `data/tables-general/`.

Long model names use the following abbreviations in LaTeX tables:

- `grid-avoid` → `grid-av`
- `grid-large-30-5` → `grid-l`
- `samplerocks` → `rocks`
- `lanes-100` → `lanes`
- `network2` → `netw2`
- `network3` → `netw3`
- `network-priorities2` → `netw-p2`
- `network-priorities3` → `netw-p3`

Result cells contain the bound on the first line and wall-clock time in seconds
on the next line. Approximation tables then show the belief-MDP state count.
Tightest under-approximation cells additionally show the selected configuration
after the state count. Summary discretisation cells show the state count followed by
the selected resolution and mode. The fastest column searches both modes at all
resolutions from 2 through 12, comparing bounds at precision `10^-6`
as in the other tables: larger is better for minimisation, smaller for
maximisation. It uses the individual run's wall-clock time, without adding
the MDP runtime. Equal runtimes are resolved by configuration order (lower
resolution, then static). A dash means no qualifying successful run, or no
successful MDP baseline with which to compare. The tightest column also uses a
dash if no discretisation succeeded. Blank state counts mean unavailable data.
Belief-MDP state counts of at least one million use scientific notation with
two digits after the decimal point.

These tables use ordinary `tabular` environments with fixed-width columns so
that corresponding columns match across objectives. Include `\usepackage{array}`,
`\usepackage{booktabs}`, and `\usepackage{multirow}`; the tables also use the existing `\model` and
`\resolution` macros. The `alternating_rows` argument to `save_latex` controls
whether data entries alternate between white and `gray!20`; load `xcolor` with
table support (or `colortbl`) for `\rowcolor`. It is enabled for the result and
approximation tables and disabled for the benchmark overview.
Selected cells use `RWTHblue25` on white rows and `RWTHblue25!80!gray` on
`gray!20` rows so their shading follows the alternating background intensity.
The `family_lines` option adds a `\midrule` only when the model family
changes; it is enabled only for the benchmark overview.

The generated LaTeX tables use the standard `\scriptsize` font size throughout.
The over-approximation widths target the dissertation's 121.45 mm B5 text block.
Summary tables use 2 pt column spacing; resolution tables use 1 pt column
spacing so that all six result columns fit. Runtime values appear on their own
line beneath each result, retain their `s` suffix, and have no parentheses.
The `\config{mdp}` Bound column reports the fully observable relaxation as a
bound on the POMDP optimum: `\leq` for maximisation and `\geq` for minimisation.

The four combined result overview tables target the same text block using
16 mm model, 10 mm objective, and four 21.5 mm result columns.
The space between the model and objective columns is reduced in both table types.

For example:

```tex
\input{data/tables-general/overapprox/tableoverapproxprbmax.tex}
\input{data/tables-general/overapprox/tableoverapproxresolutionprbmax.tex}
```

## Plot data and interpretation

All plots use the full study with a 1,800-second per-run limit. Comparisons use
bounds rounded to six decimal places. Best configurations are selected
retrospectively; their runtimes exclude configuration-search time. The compact
reproduction preset does not replace the full-study data.

`data/plot-data/discretisation/` contains four audit CSVs: observations, first
improving runs, cumulative budget counts, and resolution summaries. The budget
curves count strict improvement over MDP once per instance and mode. The
quality boxes normalise improvement by each instance's best observed gain
across both modes and all resolutions. Instances without positive gain are
excluded from that quality distribution; runtime boxes include every eligible
instance. Boxes show quartiles, medians, and minimum--maximum whiskers; failed
runs have no numeric observation.

`data/plot-data/underapproximation/` contains the matched comparison, Drone
observations, CUT classifications, outcome counts, and bound-gap audits. The
runtime comparison uses threshold `2^12` and clipping resolution 2. The Drone
example uses `N=5, R=3`, explicit thresholds `2^8`--`2^32`, and clipping
resolutions 2 and 3. Separate runs use unconnected markers. TO and MO* are
categorical outcomes, not numeric measurements. MO* includes non-timeout
SIGKILLs, retained as `killed` in the source-status fields; a kill alone does
not establish memory exhaustion. Across the 950 explicit CUT runs, 771
succeed, 177 are killed, and 2 time out.

CUT's bound-gap panel compares each successful bound with that instance's best
successful explicit-threshold bound using
`100 * abs(bound-best) / max(abs(bound), abs(best))`, with both-zero values
defined as zero. Zero matches the observed best, not necessarily the optimum.
All 38 instances are eligible; failures appear in the outcome panel instead
of the numeric distribution. Of the 38 instances, 31 improve over `2^8`.

`data/plot-data/combined-bounds/` contains selected configurations, intervals,
cumulative counts, tolerance summaries, and exact-reference errors. The three
curves compare MDP + CUT, DISCR + CUT, and DISCR + best(CUT, CLIP), counting
intervals within `100 * (U-L) / max(abs(L), abs(U))`. Both-zero endpoints give
zero width. Each method supplies its designated interval side, reversed for
minimisation. Family selection prefers exact results, then tighter bounds,
then faster runs; candidates include heuristic exploration thresholds.
Matching bounds count at every positive tolerance. At 1% tolerance, the three
combinations cover 1, 14, and 17 instances.

The exact-reference figure includes all 13 instances where CUT reports an
exact result. Error is
`100 * abs(discr-optimum) / max(abs(discr), abs(optimum))`, using rounded bounds.
CUT's error is zero throughout; DISCR retains error on nine instances and
matches on four. This attributes the remaining interval on the exact-reference
subset; the other 25 instances have no exact CUT reference.

The preview contains the 19 tables followed by the eight selected figures.
Compile it from the repository root:

```sh
lualatex --interaction=nonstopmode --halt-on-error --output-directory=data data/storm-table-check.tex
```

Its B5 Libertine layout and plot font size belong to the preview document.
The copyable TikZ snippets do not impose those font settings.
