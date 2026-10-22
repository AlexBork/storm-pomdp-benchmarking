"""Offline results table and per-run logs, adapted from the toolpaper package."""

from collections import Counter
import gzip
import html
import json
import math
from pathlib import Path
import shutil
from urllib.parse import quote


def escape(value):
    return html.escape(str(value), quote=True)


def page(title, content, asset_prefix="", script=False):
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{escape(title)}</title>\n'
        f'<link rel="stylesheet" href="{asset_prefix}results.css">\n</head>\n'
        f'<body>\n{content}\n'
        + (f'<script src="{asset_prefix}results.js"></script>\n' if script else "")
        + '</body>\n</html>\n'
    )


def number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return f"{value:,}"
    return "—"


def runtime_status(p, run):
    if run is None:
        return "missing"
    if run.get("timeout"):
        return "timeout"
    if run.get("not-supported"):
        return "unsupported"
    # A non-timeout SIGKILL does not by itself establish memory exhaustion,
    # even if older parsing also set the memout flag.
    if -9 in run.get("return-codes", []):
        return "killed"
    if run.get("memout"):
        return "memout"
    if run.get("numerical-error"):
        return "numerical-error"
    if p.is_successful_result(run):
        return "successful"
    return "failed"


def runtime_duration(seconds):
    hours, remainder = divmod(round(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s"


def compact_configuration(config):
    """The uniform compact grid discussed for reproduction; no per-instance tuning."""
    if config == "mdp":
        return True
    if config.startswith("discr"):
        return int(config[5:8]) in (2, 5, 12)
    if config.startswith(("cut", "clip")):
        exponent = int(config[4:6] if config.startswith("clip") else config[3:5])
        return exponent in (0, 8, 12, 16, 20, 24, 28, 32)
    return False


def run_page(p, run, destination):
    """Embed a bounded preview and a compressed full log for offline inspection."""
    status = runtime_status(p, run)
    fields = [
        ("Benchmark", run["benchmark-id"]),
        ("Configuration", f"{run['tool']}.{run['configuration-id']}"),
        ("Status", status),
        ("Result", run.get("result", "unavailable")),
        ("Wall-clock time (s)", run.get("wallclock-time", "unavailable")),
        ("Time limit (s)", run.get("time-limit", "unavailable")),
        ("Return codes", json.dumps(run.get("return-codes", []))),
        ("Source log", run.get("log", "unavailable")),
    ]
    content = ['<p><a href="../index.html">← Results</a></p>',
               f'<h1>{escape(run["id"])}</h1>', '<dl>']
    content.extend(f'<dt>{escape(key)}</dt><dd>{escape(value)}</dd>' for key, value in fields)
    content.extend(['</dl>', '<h2>Invocation</h2>',
                    '<pre>' + escape("\n".join(run.get("commands", []))) + '</pre>',
                    '<p>' + escape(run.get("invocation-note", "")) + '</p>', '<h2>Log</h2>'])
    source = Path(run["log"]) if run.get("log") else None
    if source is not None and not source.is_absolute() and not source.is_file():
        source = Path(__file__).resolve().parent.parent / source
    if source is not None and source.is_file():
        limit = 64 * 1024
        size = source.stat().st_size
        with source.open("rb") as stream:
            preview = stream.read(limit if size <= limit else limit // 2)
            if size > limit:
                stream.seek(-limit // 2, 2)
                preview += b"\n\n[... middle of log omitted from preview ...]\n\n" + stream.read(limit // 2)
        compressed = destination.with_suffix(".log.gz")
        if not compressed.is_file() or compressed.stat().st_mtime_ns < source.stat().st_mtime_ns:
            temporary = compressed.with_suffix(".tmp")
            with source.open("rb") as original, temporary.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=1, mtime=0) as zipped:
                    shutil.copyfileobj(original, zipped, length=1024 * 1024)
            temporary.replace(compressed)
        content.append(f'<p><a href="{escape(quote(compressed.name))}" download>Download full log (gzip)</a></p>')
        if size > limit:
            content.append('<p class="sub">Preview shows the beginning and end of the log. '
                           'The download contains the complete log.</p>')
        content.append('<pre>' + escape(preview.decode("utf-8", errors="replace")) + '</pre>')
    else:
        content.append('<p class="sub">Source log unavailable when this export was generated.</p>')
    content.extend(['<details><summary>Parsed run metadata</summary><pre>',
                    escape(json.dumps(run, ensure_ascii=False, indent=2)), '</pre></details>'])
    destination.write_text(page(run["id"], "\n".join(content), "../"), encoding="utf-8")


def save_results(p, execution, instances, logdirs=(), output_dir=None):
    """Export actual configurations only; derived selections are not measured runs."""
    root = Path(output_dir) if output_dir is not None else Path(p.OUT_DIR) / "html"
    (root / "logs").mkdir(parents=True, exist_ok=True)
    # Remove generated pages for retired configurations; source logs stay intact.
    for tool in p.TOOLS:
        for config in getattr(tool, "RETIRED_CONFIG_IDS", ()):
            for obsolete in (root / "logs").glob(f"{tool.NAME}.{config}.*"):
                if obsolete.suffix == ".html" or obsolete.name.endswith(".log.gz"):
                    obsolete.unlink()
    assets = Path(__file__).parent / "html_assets"
    for asset in ("results.css", "results.js"):
        shutil.copyfile(assets / asset, root / asset)
    configs = [(tool.NAME, cfg) for tool in p.TOOLS for cfg in tool.CONFIGS]
    family_order = {"MDP": 0, "discretisation": 1, "cutoff": 2, "clipping": 3}
    configs.sort(key=lambda item: (family_order.get(item[1].get("family"), 4),
                                  item[0], item[1]["id"]))
    selected_instances = [inst for inst in p.benchmarks.INSTANCES
                          if inst["id"] in instances or any(
                              p.get_result(execution, tool, cfg["id"], inst["id"]) is not None
                              for tool, cfg in configs)]
    runs = [run for tool, cfg in configs for inst in selected_instances
            if (run := p.get_result(execution, tool, cfg["id"], inst["id"])) is not None]
    statuses = Counter(runtime_status(p, run) for run in runs)
    seconds = math.fsum(run.get("wallclock-time", 0) for run in runs)
    content = ['<h1>Storm-POMDP benchmark results</h1>',
               '<p class="sub">Each measured run links to its invocation and log. '
               'Click a column header to sort; use the buttons to show or hide configurations.</p>',
               f'<p class="sub">{len(selected_instances)} instances · {len(configs)} configurations · '
               f'{len(runs)} recorded runs · cumulative runtime: {escape(runtime_duration(seconds))}. '
               + ', '.join(f'{count} {escape(status)}' for status, count in sorted(statuses.items())) + '.</p>']
    if logdirs:
        content.append('<p class="sub">Sources: ' + ', '.join(escape(d) for d in logdirs) + '.</p>')
    content.extend([
        '<details class="explanation"><summary>How to read the results</summary><p class="sub">'
        'Green marks the best successful result among visible configurations, '
        'comparing CUT + CLIP separately from DISCR + MDP. Exact under-approximation results '
        'take precedence; otherwise bounds are compared at six decimal places. Runtime breaks ties. '
        'For maximisation, larger CUT/CLIP bounds and smaller '
        'discretisation/MDP bounds are better; minimisation reverses these directions. '
        'MDP values are shown as bounds on the POMDP optimum. '
        'Highlighting is the same in every display view. Killed means SIGKILL without a '
        'recorded timeout; it is separate from an identified memory error. '
        'Numerical-error means the clipping LP correctness check rejected the computation. '
        'Missing values are unavailable measurements, not zeros. Derived best-configuration '
        'selections are excluded from the measured runs and runtime total.</p></details>',
        '<div class="controls"><label>Filter benchmarks <input id="filter" type="search" '
        'placeholder="Name, parameters, or objective"></label> '
        '<label>Cell display <select id="metric"><option value="both">Bound &amp; runtime</option>'
        '<option value="runtime">Runtime (s)</option><option value="bound">Bound</option>'
        '<option value="states">Belief-MDP states</option></select></label> '
        '<label>Configuration preset <select id="preset"><option value="all">All configurations</option>'
        '<option value="compact">Compact reproduction grid</option>'
        '<option value="custom" disabled>Custom selection</option></select></label> '
        '<span id="row-count" role="status"></span></div>',
        '<div id="columns" class="controls" aria-label="Visible configurations">'
        '<button type="button" data-all="true">Show all</button> '
        '<button type="button" data-all="false">Hide all</button>',
    ])
    for family in dict.fromkeys(cfg.get("family", tool) for tool, cfg in configs):
        content.append(f'<button type="button" class="family-toggle" '
                       f'data-family="{escape(family)}" aria-pressed="true">{escape(family)}</button>')
    content.append('<span id="column-count" role="status"></span></div>'
                   '<details class="configuration-details"><summary>Choose individual configurations</summary>'
                   '<div class="controls">')
    for family in dict.fromkeys(cfg.get("family", tool) for tool, cfg in configs):
        content.append(f'<div class="configuration-family"><span class="family">{escape(family)}:</span>')
        for tool, cfg in configs:
            if cfg.get("family", tool) != family:
                continue
            key = f"{tool}.{cfg['id']}"
            content.append(f'<button type="button" class="toggle on" data-col="{escape(key)}" '
                           f'data-family="{escape(family)}" '
                           f'data-compact="{str(compact_configuration(cfg["id"])).lower()}" '
                           f'aria-pressed="true" title="{escape("; ".join(cfg.get("notes", [])))}">'
                           f'{escape(cfg["id"])}</button>')
        content.append('</div>')
    content.extend(['</div></details>', '<div class="table-scroll"><table id="results">',
                    '<caption>Bounds, recorded wall-clock runtimes in seconds, and resulting belief-MDP sizes. '
                    'Configuration columns sort by runtime, or by the selected bound or state count; '
                    'unsuccessful and missing results stay last.</caption>', '<thead><tr>'])
    metadata = [("benchmark", "text"), ("objective", "text"), ("states", "number"),
                ("choices", "number"), ("observations", "number")]
    for label, kind in metadata:
        content.append(f'<th scope="col" data-kind="{kind}"><button type="button" '
                       f'class="sort">{label}</button></th>')
    for tool, cfg in configs:
        content.append(f'<th scope="col" data-kind="run" data-col="{escape(tool + "." + cfg["id"])}" '
                       f'title="{escape("; ".join(cfg.get("notes", [])))}">'
                       f'<button type="button" class="sort">{escape(cfg["id"])}</button></th>')
    content.append('</tr></thead>\n<tbody>')
    log_count = 0
    for inst in selected_instances:
        inst_id = inst["id"]
        # Runs can fail before model statistics are printed.
        data = instances.get(inst_id, {
            "name": inst.get("name", inst_id),
            "par": ",".join(f"{key}={value}" for key, value in
                            inst.get("model", {}).get("open-parameters", {}).items()),
            "property": inst["property"]["type"],
            "property-dir": inst["property"]["dir"],
        })
        name = data.get("name", inst_id)
        if name == "crypt":
            name = inst["benchmark-set"]
        if data.get("par"):
            name += "/" + str(data["par"])
        objective = data.get("property-id", inst["property"]["id"])
        content.append(f'<tr data-direction="{escape(inst["property"]["dir"])}" '
                       f'data-search="{escape((inst_id + " " + name + " " + objective).lower())}">')
        for label, kind in metadata:
            value = name if label == "benchmark" else objective if label == "objective" else data.get(label)
            display = number(value) if kind == "number" else value
            sort_value = value if value is not None else ""
            content.append(f'<td data-sort="{escape(sort_value)}" title="{escape(inst_id)}">'
                           f'{escape(display)}</td>')
        for tool, cfg in configs:
            key = f"{tool}.{cfg['id']}"
            run = p.get_result(execution, tool, cfg["id"], inst_id)
            status = runtime_status(p, run)
            successful = status == "successful"
            runtime = run.get("wallclock-time") if run else None
            relation, value = p.parse_result_value(run["result"]) if successful else ("", "")
            states = run.get("belief-mdp", {}).get("states") if run else None
            attributes = (f'class="run {status}" data-col="{escape(key)}" '
                          f'data-family="{escape(cfg.get("family", tool))}" '
                          f'data-status="{status}" data-runtime="{escape(runtime if runtime is not None else "")}" '
                          f'data-bound="{escape(value)}" data-relation="{escape(relation)}" '
                          f'data-states="{escape(states if states is not None else "")}" '
                          f'data-quality="{escape(p.comparison_value(value) if successful else "")}"')
            content.append(f'<td {attributes}>')
            if run is None:
                content.append('<span title="No recorded run">missing</span>')
            else:
                filename = quote(f"{key}.{inst_id}", safe="") + ".html"
                run_page(p, run, root / "logs" / filename)
                log_count += 1
                bound = run["result"] if successful else status
                if successful and cfg["id"] == "mdp":
                    bound = ("≤ " if inst["property"]["dir"] == "max" else "≥ ") + str(value)
                elif successful and relation == "=" and not bound.lstrip().startswith("="):
                    bound = "= " + bound
                duration = f"{runtime:.2f}" if runtime is not None else "—"
                title = f'{status}; result: {run.get("result", "unavailable")}; wall-clock: {runtime}s'
                content.append(f'<a href="logs/{escape(quote(filename))}" title="{escape(title)}">'
                               f'<span class="bound">{escape(bound)}</span> '
                               f'<span class="runtime">({duration}s)</span>'
                               f'<span class="states">{escape(number(states))}</span></a>')
            content.append('</td>')
        content.append('</tr>')
    content.extend(['</tbody></table></div>'])
    (root / "index.html").write_text(page("Storm-POMDP results", "\n".join(content), script=True),
                                      encoding="utf-8")
    print(f"Generated {root}/index.html and {log_count} run pages.")
    return {"instances": len(selected_instances), "configurations": len(configs),
            "runs": len(runs), "seconds": seconds, "statuses": dict(statuses)}


if __name__ == "__main__":
    import argparse
    import postprocess as p

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    p.OUT_DIR = str(args.data_dir)
    print(save_results(p, p.load_json(args.data_dir / "execution-data.json"),
                       p.load_json(args.data_dir / "benchmark-data.json"), output_dir=args.output_dir))
