"""Aggregate interval tightness from paired over- and under-approximation bounds."""
import math
import os


SERIES = (
    ("mdp-cut", "mdp", "cut", "plotcut!70!black", "densely dotted", r"MDP + CUT"),
    ("discr-cut", "discr", "cut", "plotdiscr", "dashed", r"DISCR + CUT"),
    ("discr-best", "discr", "best", "plotclip", "solid", r"DISCR + best(CUT, CLIP)"),
)


def save_outputs(p, execution, instances, timelimit=None):
    if timelimit is None:
        timelimit = p.storm.META_CONFIG_TIMELIMITS[0]
    root = os.path.join(p.OUT_DIR, "combined-bounds-plots")
    os.makedirs(root, exist_ok=True)
    included = [b for b in p.benchmarks.INSTANCES if b["id"] in instances]
    configurations = [c["id"] for c in p.storm.CONFIGS]
    selections = [["instance", "objective", "method", "configuration", "result",
                   "raw-bound", "comparison-bound", "runtime"]]
    intervals = [["instance", "objective", "combination", "over-configuration",
                  "under-configuration", "over-runtime", "under-runtime",
                  "raw-lower", "raw-upper", "raw-relative-width-percent",
                  "comparison-lower", "comparison-upper", "relative-width-percent"]]
    widths = {name: [] for name, *_ in SERIES}
    exact_cases = []

    def select(benchmark, family):
        candidates = [p.get_result(execution, p.storm.NAME, cfg, benchmark["id"])
                      for cfg in configurations if cfg.startswith(family)]
        candidates = [r for r in candidates if p.is_successful_result(r, timelimit)]
        return max(candidates, key=lambda r: p.result_selection_score(
            r, p.expected_bound_relation(family, benchmark)), default=None)

    def value(run):
        bound = p.parse_result_value(run["result"])[1]
        if not math.isfinite(bound):
            raise ValueError(f"Non-finite bound: {run['id']}")
        return bound

    def relative_width(lower, upper):
        scale = max(abs(lower), abs(upper))
        return 100 * (upper - lower) / scale if scale else 0.0

    for benchmark in included:
        inst = benchmark["id"]
        objective = benchmark["property"]["type"] + benchmark["property"]["dir"]
        runs = {family: select(benchmark, family) for family in ("discr", "cut", "clip")}
        runs["mdp"] = p.get_result(execution, p.storm.NAME, "mdp", inst)
        for family in ("mdp", "discr", "cut"):
            if not p.is_successful_result(runs[family], timelimit):
                raise ValueError(f"Missing successful {family} bound within budget: {inst}")
        # Keep the established table selection policy: exact POMDP results take
        # precedence over approximate values, which can differ by solver noise.
        runs["best"] = max((runs[f] for f in ("cut", "clip") if runs[f] is not None),
                           key=lambda r: p.result_selection_score(
                               r, p.expected_bound_relation("cut", benchmark)))
        for family in ("mdp", "discr", "cut", "clip"):
            run = runs[family]
            selections.append([inst, objective, family,
                               run["configuration-id"] if run else None,
                               run["result"] if run else None,
                               value(run) if run else None,
                               p.comparison_value(value(run)) if run else None,
                               run["wallclock-time"] if run else None])
        for name, over_family, under_family, *_ in SERIES:
            over, under = runs[over_family], runs[under_family]
            # Use each method's designated side, including when a run reports
            # equality. This compares the requested pairs of bound endpoints.
            lower, upper = (value(under), value(over)) if benchmark["property"]["dir"] == "max" \
                else (value(over), value(under))
            rounded_lower, rounded_upper = map(p.comparison_value, (lower, upper))
            if rounded_lower > rounded_upper:
                raise ValueError(f"Inconsistent interval for {inst}, {name}: {lower}, {upper}")
            width = relative_width(rounded_lower, rounded_upper)
            widths[name].append(width)
            intervals.append([inst, objective, name, over["configuration-id"],
                              under["configuration-id"], over["wallclock-time"], under["wallclock-time"],
                              lower, upper, relative_width(lower, upper),
                              rounded_lower, rounded_upper, width])
        if p.parse_result_value(runs["cut"]["result"])[0] == "=":
            reference, bound = value(runs["cut"]), value(runs["discr"])
            rounded_reference, rounded_bound = map(p.comparison_value, (reference, bound))
            error = abs(relative_width(rounded_reference, rounded_bound))
            exact_cases.append((benchmark, runs["cut"], runs["discr"], reference, bound, error))

    def csv(filename, rows):
        p.save_csv([["nan" if c is None else c for c in row] for row in rows],
                   os.path.join(root, filename))

    csv("selected-bounds.csv", selections)
    csv("intervals.csv", intervals)
    # The horizontal coordinate is a positive tolerance, not a shifted interval
    # width. Zero-width intervals count at every tolerance and are also reported
    # in the legend, so no artificial positive value is assigned to zero.
    positive = [v for values in widths.values() for v in values if v > 0]
    start = 10 ** min(-3, math.floor(math.log10(min(positive)))) if positive else 0.001
    end = max(100, 10 ** math.ceil(math.log10(max(positive)))) if positive else 100
    events = sorted({start, end, *(v for v in positive if start <= v <= end)})
    cumulative = [["tolerance-percent", *(name for name, *_ in SERIES)]]
    for tolerance in events:
        cumulative.append([tolerance, *(sum(v <= tolerance for v in widths[name])
                                        for name, *_ in SERIES)])
    csv("cumulative-counts.csv", cumulative)
    thresholds = (0, 0.001, 0.01, 0.1, 1, 5, 10, 25, 50, 100)
    csv("tolerance-summary.csv", [["tolerance-percent", *(name for name, *_ in SERIES)]]
        + [[t, *(sum(v <= t for v in widths[name]) for name, *_ in SERIES)] for t in thresholds])
    curves = []
    for name, _, _, color, style, label in SERIES:
        matching = sum(v == 0 for v in widths[name])
        curves.append(r"\addplot[color=" + color + "," + style
                      + r",no marks,const plot] table[x=tolerance-percent,y=" + name
                      + r",col sep=space,row sep=\\]{" + p.latex_plot_table(cumulative) + "};\n"
                      + r"\addlegendentry{" + label + f" ({matching} matching)" + "}\n")
    ticks = [10 ** e for e in range(round(math.log10(start)), round(math.log10(end)) + 1)]
    options = (r"width=\linewidth,height=5.5cm,"
               + f"xmode=log,xmin={start:g},xmax={end:g},ymin=0,ymax={len(included) + 1},\n"
               + "xtick={" + ",".join(f"{t:g}" for t in ticks) + "},\n"
               + "xticklabels={" + ",".join(f"${t:g}$" for t in ticks) + "},\n"
               + "ytick={" + ",".join(map(str, sorted({0, 10, 20, 30, len(included)}))) + "},\n"
               + r"xlabel={interval-width tolerance (\%)},"
               + r"ylabel={instances within tolerance},"
               + r"grid=major,major grid style={draw=black!15,line width=0.25pt},"
               + r"tick align=outside,legend columns=1,")
    body = (r"\begin{tikzpicture}\begin{axis}[" + "\n" + options + "]\n"
            + "".join(curves) + r"\end{axis}\end{tikzpicture}" + "\n")
    def write(filename, body, styled=True):
        with open(os.path.join(root, filename), "w") as output:
            output.write("% Generated by scripts/combined_bounds_visuals.py.\n"
                         + (p.style_latex_plot(body) if styled else body))

    write("interval-tightness.tex", body)

    # An independent exact CUT result identifies the optimum. On this subset
    # the remaining DISCR/CUT interval can be attributed to discretisation.
    # Keep the zero errors as well as the positive ones to show the whole subset.
    exact_cases.sort(key=lambda row: (-row[-1], row[0]["id"]))
    if not exact_cases:
        raise ValueError("No exact CUT references available for the error panel")
    audit = [["instance", "objective", "row", "cut-configuration", "discr-configuration",
              "cut-runtime", "discr-runtime", "raw-optimum", "raw-discr-bound",
              "raw-discr-error-percent", "comparison-optimum", "comparison-discr-bound",
              "discr-error-percent", "cut-error-percent"]]
    labels, bars = [], []
    for index, (benchmark, cut, discr, reference, bound, error) in enumerate(exact_cases, 1):
        family = benchmark["benchmark-set"]
        name = family if benchmark["name"] == "crypt" else benchmark["name"]
        name = p.LATEX_MODEL_ABBREVIATIONS.get(name, name)
        parameters = (benchmark["model"].get("open-parameters") or {}).values()
        parameter_label = "-".join(f"{v:g}" if isinstance(v, (int, float)) else str(v) for v in parameters)
        symbol = "P" if benchmark["property"]["type"] == "prb" else "R"
        subscript = r"\min" if benchmark["property"]["dir"] == "min" else r"\max"
        if benchmark["property"]["id"].endswith("packets"):
            subscript += r",\mathrm{pkt}"
        labels.append(r"\textsc{" + name + ("/" + parameter_label if parameter_label else "")
                      + "} $" + symbol + "_{" + subscript + "}$")
        audit.append([benchmark["id"], benchmark["property"]["type"] + benchmark["property"]["dir"],
                      index, cut["configuration-id"], discr["configuration-id"],
                      cut["wallclock-time"], discr["wallclock-time"], reference, bound,
                      abs(relative_width(reference, bound)), p.comparison_value(reference),
                      p.comparison_value(bound), error, 0])
        if error > 0:
            bars.append(r"\fill[plotdiscr!65] " + f"(axis cs:0,{index - 0.25}) rectangle "
                        + f"(axis cs:{error:.12g},{index + 0.25});\n")
        bars.append(r"\node[anchor=west,font=\scriptsize,inner sep=1pt,xshift=2pt] at "
                    + f"(axis cs:{error:.12g},{index}) "
                    + r"{$\pgfmathprintnumber[fixed,precision=3]{" + f"{error:.12g}" + "}$};\n")
    csv("exact-cut-discr-errors.csv", audit)
    measured = [r"\dimen0=0pt" + "\n"]
    for label in labels:
        measured.append(r"\settowidth{\dimen2}{\scriptsize " + label + "}\n"
                        + r"\ifdim\dimen2>\dimen0 \dimen0=\dimen2\fi" + "\n")
    measured.append(r"\edef\exactErrorAxisWidth{\the\dimexpr\linewidth-\dimen0-5mm\relax}" + "\n")
    upper = max(100, math.ceil(max(case[-1] for case in exact_cases) / 25) * 25)
    options = (r"scale only axis,width=\exactErrorAxisWidth,"
               + f"height={len(exact_cases) * 3.3:g}mm,xmin=0,xmax={upper * 1.14:g},"
               + f"ymin=0.5,ymax={len(exact_cases) + 0.5},y dir=reverse,\n"
               + "ytick={" + ",".join(str(i) for i in range(1, len(exact_cases) + 1)) + "},"
               + "yticklabels={" + ",".join("{" + label + "}" for label in labels) + "},\n"
               + "xtick={" + ",".join(str(i) for i in range(0, upper + 1, 25)) + "},"
               + r"yticklabel style={font=\scriptsize},ytick style={draw=none},"
               + r"xlabel={relative discretisation error (\%)},"
               + r"xmajorgrids=true,major grid style={draw=black!15,line width=0.25pt},"
               + r"tick align=outside,enlarge y limits=false,")
    write("exact-cut-discr-error.tex", "".join(measured)
          + r"\begin{tikzpicture}\begin{axis}[" + "\n" + options + "]\n"
          + "".join(bars) + r"\end{axis}\end{tikzpicture}" + "\n")
    return {"instances": len(included), "matching-bounds": {k: v.count(0) for k, v in widths.items()},
            "within-one-percent": {k: sum(w <= 1 for w in v) for k, v in widths.items()},
            "exact-cut-instances": len(exact_cases),
            "exact-cut-with-discr-error": sum(case[-1] > 0 for case in exact_cases)}


if __name__ == "__main__":
    from export_tikzpictures import main
    main()
