# Storm-POMDP Benchmarking Utilities

## Interactive configuration selection

When creating an invocation file interactively with `python3 scripts/run.py`,
choose one or more configuration families instead of individual
configurations:

- `discretisation` selects every declared discretisation configuration.
- `cutoff` selects every declared cut-off configuration, including `cut00`.
- `clipping` selects every declared clipping configuration, including the
  heuristic `clip00res*` variants.
- `MDP` selects the fully observable MDP configuration.

Every interactive menu displays numbered options; enter the number shown to
select an option. The textual option ids, `a` (all), `c` (clear), and `d`
(done) continue to work as well.

Adding a configuration to one of these families in `scripts/storm.py` makes
it available automatically in the corresponding interactive selection.
