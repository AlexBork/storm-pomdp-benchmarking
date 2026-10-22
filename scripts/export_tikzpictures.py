"""Export the selected figures as self-contained, copyable TikZ pictures."""
import argparse
from pathlib import Path
import re
import shutil
import tempfile


COLORS = r"""\definecolor{plotcut}{cmyk}{0.35,0,1,0}
\definecolor{plotclip}{cmyk}{0.25,1,0.7,0.2}
\definecolor{plotdiscr}{cmyk}{1,0.5,0,0}
"""


def group(text, start):
    """Read a balanced TeX argument, respecting escaped braces and comments."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected a TeX argument")
    depth, index = 1, start + 1
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in "{}%\\":
            index += 2
            continue
        if char == "%":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline + 1
            continue
        depth += (char == "{") - (char == "}")
        if depth == 0:
            return text[start + 1:index], index + 1
        index += 1
    raise ValueError("Unclosed TeX argument")


def inherit_typography(text, relative):
    """Remove presentation overrides from intermediate plot sources."""
    text = re.sub(r"(?:[xy] label|[xy]ticklabel) style=\{[^{}]*\},?\s*", "", text)
    text = re.sub(r"font=\\(?:scriptsize|footnotesize|small)\b,?\s*", "", text)
    text = re.sub(r"\\(?:scriptsize|footnotesize|small)\b\s*", "", text)
    text = re.sub(r"nodes=\{scale=0\.75,transform shape\},?\s*", "", text)
    text = re.sub(r"(?:inner sep|[xy]shift)=-?[\d.]+pt,?\s*", "", text)
    text = text.replace("[scale=0.75,transform shape]", "")
    if relative.endswith(("cut-outcomes-heatmap.tex", "exact-cut-discr-error.tex")):
        count = len(re.findall(r"\\settowidth", text))
        text = re.sub(r"height=[\d.]+mm", lambda _: rf"height=\dimexpr{count}\baselineskip\relax", text)
    return text


def export_pictures(data_dir=Path("data"), output_dir=None):
    output_dir = output_dir or data_dir / "tikzpictures"
    output_dir.mkdir(parents=True, exist_ok=True)

    def fragment(relative):
        text = inherit_typography((data_dir / relative).read_text(), relative)
        text = re.sub(r"\\config\{([^{}]*)\}", lambda m: r"\textsc{" + m[1] + "}", text)
        before, inside = text.split(r"\begin{tikzpicture}", 1)
        inside = inside.split(r"\end{tikzpicture}", 1)[0]
        before = re.sub(r"(?m)^%[^\n]*\n", "", before)
        before = before.replace(r"\begingroup", "").replace(
            r"\providecommand{\config}[1]{\textsc{#1}}", "")
        before = re.sub(r"\\definecolor\{[^{}]+\}\{[^{}]+\}\{[^{}]+\}\s*", "", before)
        # TikZ uses nullfont outside nodes. Restore the surrounding font only
        # while measuring labels, keeping the entire picture self-contained.
        cursor = 0
        while match := re.search(r"\\settowidth\{\\dimen2\}", before[cursor:]):
            start = cursor + match.end()
            label, end = group(before, start)
            replacement = r"{\pgfinterruptpicture " + label + r"\endpgfinterruptpicture}"
            before = before[:start] + replacement + before[end:]
            cursor = start + len(replacement)
        return before.strip() + "\n" + inside.strip() + "\n"

    def axis(relative, options="", legend=""):
        text = fragment(relative)
        if options:
            start = text.index(r"\begin{axis}[") + len(r"\begin{axis}[")
            depth, end = 0, start
            while end < len(text):
                c = text[end]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                elif c == "]" and depth == 0:
                    break
                end += 1
            text = text[:end].rstrip().rstrip(",") + "," + options + "," + text[end:]
        return text.replace(r"\end{axis}", legend + "\n" + r"\end{axis}")

    def scope(name, body, placement=""):
        return (r"\begin{scope}[local bounding box=" + name + ("," + placement if placement else "")
                + "]\n" + body + r"\end{scope}" + "\n")

    pictures = {
        "discretisation-budget": fragment("discretisation-plots/improvement-budget.tex"),
        "cut-vs-clip-runtime": fragment("underapprox-plots/matched-runtime.tex"),
        "cut-outcomes-heatmap": fragment("underapprox-plots/cut-outcomes-heatmap.tex"),
        "combined-bounds": fragment("combined-bounds-plots/interval-tightness.tex"),
        "discretisation-exact-reference": fragment("combined-bounds-plots/exact-cut-discr-error.tex"),
    }
    for metric in ("quality", "runtime"):
        pictures[f"discretisation-resolution-{metric}"] = axis(
            f"discretisation-plots/resolution-{metric}-no-legend.tex",
            r"scale only axis,width=0.83\linewidth")
    pictures["discretisation-resolution-outcomes"] = axis(
        "discretisation-plots/resolution-outcomes.tex",
        r"scale only axis,width=0.83\linewidth")

    drone_legend = r"""\addlegendimage{only marks,color=plotcut,mark=o,mark options={fill=white}}
\addlegendentry{\textsc{cut}}
\addlegendimage{only marks,color=plotclip,mark=triangle,mark options={fill=white}}
\addlegendentry{\textsc{clip}, $\eta=2$}
\addlegendimage{only marks,color=plotdiscr,mark=square,mark options={fill=white}}
\addlegendentry{\textsc{clip}, $\eta=3$}
"""
    top = axis("underapprox-plots/drone-threshold-bound-no-legend.tex",
               r"name=bound,anchor=outer north west,"
               r"legend style={at={(0.5,1.18)},anchor=south}", drone_legend)
    left = axis("underapprox-plots/drone-threshold-time-compact.tex",
                r"anchor=outer north west,width=0.48\linewidth")
    right = axis("underapprox-plots/drone-threshold-states-compact.tex",
                 r"anchor=outer north west,width=0.48\linewidth")
    pictures["drone-threshold"] = (scope("boundbox", top)
        + scope("runtimebox", left, r"shift={(boundbox.south west)},yshift=-\baselineskip")
        + scope("statesbox", right, r"shift={(boundbox.south west)},xshift=0.52\linewidth,yshift=-\baselineskip"))

    top = axis("underapprox-plots/cut-bound-gap.tex",
               r"name=gap,anchor=north west,scale only axis,width=0.83\linewidth")
    bottom = axis("underapprox-plots/cut-outcomes-stacked.tex",
                  r"at={(gap.south west |- gapbox.south)},anchor=north west,"
                  r"yshift=-3\baselineskip,scale only axis,width=0.83\linewidth")
    pictures["cut-bound-overview"] = scope("gapbox", top) + bottom

    for name, content in pictures.items():
        picture = ("% Requires pgfplots and its statistics library. Fonts are inherited.\n"
                   + "\\begin{tikzpicture}\n" + COLORS + content + "\\end{tikzpicture}\n")
        assert picture.count(r"\begin{tikzpicture}") == 1
        assert picture.count(r"\end{tikzpicture}") == 1
        assert r"\input" not in picture and r"\POMDP" not in picture
        (output_dir / f"{name}.tex").write_text(picture)
    # Replaced by the independent quality and runtime pictures.
    (output_dir / "discretisation-resolution.tex").unlink(missing_ok=True)
    return {"folder": str(output_dir), "tikzpictures": len(pictures)}


def generate_plots(p, execution, instances, data_dir, output_dir=None):
    """Keep one final export and audit data; intermediate panels are temporary."""
    from discretisation_visuals import save_outputs as discretisation
    from underapprox_comparison_visuals import save_outputs as underapproximation
    from combined_bounds_visuals import save_outputs as combined

    families = ((discretisation, "discretisation-plots", "discretisation"),
                (underapproximation, "underapprox-plots", "underapproximation"),
                (combined, "combined-bounds-plots", "combined-bounds"))
    data_dir = Path(data_dir)
    with tempfile.TemporaryDirectory(prefix="pomdp-plot-panels-") as temporary:
        previous = p.OUT_DIR
        try:
            p.OUT_DIR = temporary
            for save, _, _ in families:
                save(p, execution, instances)
        finally:
            p.OUT_DIR = previous
        result = export_pictures(Path(temporary), output_dir or data_dir / "tikzpictures")
        count = 0
        for _, source, family in families:
            destination = data_dir / "plot-data" / family
            destination.mkdir(parents=True, exist_ok=True)
            for csv in (Path(temporary) / source).glob("*.csv"):
                shutil.copyfile(csv, destination / csv.name)
                count += 1
        result["audit-csvs"] = count
    return result


def main():
    import postprocess as p

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    execution = p.load_json(args.data_dir / "execution-data.json")
    instances = p.load_json(args.data_dir / "benchmark-data.json")
    # Cached data may predate the current study's configuration selection.
    p.process_meta_configs(execution, instances)
    print(generate_plots(p, execution, instances, args.data_dir, args.output_dir))


if __name__ == "__main__":
    main()
