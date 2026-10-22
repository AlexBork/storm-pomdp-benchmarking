import sys, os, json, csv, copy, math, re, itertools, html

from collections import Counter, OrderedDict
import benchmarks
from tools import *

OUT_DIR = "data"
TABLE_DIR = os.path.join(OUT_DIR, "tables-general")
OVERAPPROX_TABLE_DIR = os.path.join(TABLE_DIR, "overapprox")
UNDERAPPROX_TABLE_DIR = os.path.join(TABLE_DIR, "underapprox")
LATEX_TABLE_FONT_SIZE = "scriptsize"
RESULT_COMPARISON_DECIMALS = 6
LATEX_HIGHLIGHT_COLOR = "RWTHblue25"
LATEX_SHADED_HIGHLIGHT_COLOR = "RWTHblue25!80!gray"

LATEX_MODEL_ABBREVIATIONS = {
    "grid-avoid": "grid-av",
    "grid-large-30-5": "grid-l",
    "samplerocks": "rocks",
    "network-priorities2": "netw-p2",
    "network-priorities3": "netw-p3",
    "lanes-100": "lanes",
    "network2": "netw2",
    "network3": "netw3",
}

def strip_benchmark_set_prefix(inst_id):
    return inst_id.split("_", 1)[1] if "_" in inst_id else inst_id

def load_json(path : str):
    with open(path, 'r', encoding='utf-8-sig') as json_file:
        return json.load(json_file, object_pairs_hook=OrderedDict)

def save_json(json_data, path : str):
    with open(path, 'w') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent='\t')

def load_csv(path : str, delim='\t'):
    with open(path, 'r') as csv_file:
        return list(csv.reader(csv_file, delimiter=delim))

def save_csv(csv_data, path : str, delim='\t'):
    with open(path, 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=delim)
        writer.writerows(csv_data)

def latex_plot_table(table):
    """Format inline PGFPlots data with explicit row separators."""
    return "\n" + "\n".join(
        " ".join("nan" if value == "" else str(value) for value in row) + r" \\"
        for row in table
    ) + "\n"


# Match the PGFPlots appearance of storm-rew-bounded-benchmarking.
LATEX_PLOT_BEGIN = r"""% Preamble requires \usepackage{pgfplots} and \pgfplotsset{compat=1.18}.
\begingroup
\providecommand{\config}[1]{\textsc{#1}}
\definecolor{plotcut}{cmyk}{0.35,0,1,0}
\definecolor{plotclip}{cmyk}{0.25,1,0.7,0.2}
\definecolor{plotdiscr}{cmyk}{1,0.5,0,0}
"""
LATEX_PLOT_OPTIONS = r"""axis x line=bottom,axis y line=left,
filter discard warning=false,
x label style={font=\small,yshift=4pt},y label style={font=\small,yshift=-2pt},
yticklabel style={font=\small},xticklabel style={font=\small},
legend columns=-1,legend cell align=left,
legend style={at={(0.5,1)},anchor=south,yshift=4pt,
    nodes={scale=0.75,transform shape},inner sep=1pt,column sep=0.5em,row sep=0.2ex},
/pgfplots/legend image code/.code={\draw[mark repeat=2,mark phase=2,#1] plot coordinates {(0cm,0cm) (0.3cm,0cm)};},
every axis plot/.append style={thick},
"""
# Square comparison panels, following Figures 3 and 6 of arXiv:2301.10197.
LATEX_SCATTER_OPTIONS = r"""scale only axis,
width=\linewidth,height=\linewidth,
grid=major,major grid style={draw=black!15,line width=0.25pt},
tick align=outside,tick style={line width=0.3pt},
xticklabel style={font=\footnotesize},yticklabel style={font=\footnotesize},
axis line style={line width=0.4pt},
every axis plot/.append style={thin},
x label style={font=\small,yshift=0pt},y label style={font=\small,yshift=0pt},
legend style={draw=black,fill=white,line width=0.3pt},
/pgfplots/legend image code/.code={\draw[#1] plot coordinates {(0.15cm,0cm)};},
"""
def scatter_log_minor_ticks(lower, numeric_end, major_ticks=()):
    """Keep base-ten subdivisions throughout the numeric region, outside N/A."""
    ticks = []
    for exponent in range(math.floor(math.log10(lower)), math.ceil(math.log10(numeric_end)) + 1):
        for multiplier in range(1, 10):
            value = multiplier * 10 ** exponent
            if lower < value < numeric_end and not any(
                math.isclose(value, major) for major in major_ticks
            ):
                ticks.append(f"{value:g}")
    positions = ",".join(ticks)
    return f"minor xtick={{{positions}}},minor ytick={{{positions}}},"


def scatter_log_ticks(lower, upper, failure=None):
    """Label every decade and reserve an unticked strip for unavailable values."""
    exponents = range(math.ceil(math.log10(lower)), math.floor(math.log10(upper)) + 1)
    ticks = [10 ** exponent for exponent in exponents]
    labels = [f"${tick:g}$" for tick in ticks]
    if not any(math.isclose(upper, tick) for tick in ticks):
        ticks.append(upper)
        labels.append(f"${upper:g}$")
    options = scatter_log_minor_ticks(lower, upper, ticks)
    if failure is not None:
        ticks.append(failure)
        labels.append("n/a")
    for axis in ("x", "y"):
        options += "".join((axis, "tick={", ",".join(map(str, ticks)), "},",
                            axis, "ticklabels={", ",".join(labels), "},"))
    return options


def scatter_na_limits(lower, upper, logarithmic=False, gap_fraction=0.10):
    """Place N/A beyond the numeric boundary by a configurable panel fraction."""
    padding_fraction = 0.03
    numeric_fraction = 1 - gap_fraction - padding_fraction
    if logarithmic:
        span = math.log10(upper / lower) / numeric_fraction
        return (upper * 10 ** (gap_fraction * span),
                upper * 10 ** ((gap_fraction + padding_fraction) * span))
    span = (upper - lower) / numeric_fraction
    return (upper + gap_fraction * span,
            upper + (gap_fraction + padding_fraction) * span)


def style_latex_plot(plot):
    for old, new in [("RWTHmaygreen", "plotcut"), ("RWTHbordeaux", "plotclip"), ("RWTHblue", "plotdiscr")]:
        plot = plot.replace(old, new)
    for environment in ("axis", "groupplot"):
        plot = re.sub(r"\\begin\{" + environment + r"\}\[\s*", lambda match: r"\begin{" + environment + "}[" + "\n" + LATEX_PLOT_OPTIONS, plot)
    return LATEX_PLOT_BEGIN + plot + r"\endgroup" + "\n"


def save_html(table_data, num_tool_configs, path):
    SHOW_UNSUPPORTED = True # Also add entries for benchmarks that are known to be unsupported
    LOGS_SUBDIR = "logs"
    if not os.path.exists(os.path.join(path, LOGS_SUBDIR)): os.makedirs(os.path.join(path, LOGS_SUBDIR))

    # Aux function for writing in files with proper indention
    def write_line(file, indention, content):
        file.write("\t"*indention + content + "\n")

    # Generates an html log page for the given result within path/LOGS_SUBDIR/
    def create_log_page(result_json):
        with open(result_json["log"], 'r') as logfile:
            log = logfile.read()
        f_path = os.path.join(LOGS_SUBDIR, os.path.basename(result_json["log"])[:-4] + ".html")
        with open(os.path.join(path, f_path), 'w') as f:
            indention = 0
            write_line(f, indention, "<!DOCTYPE html>")
            write_line(f, indention, "<html>")
            write_line(f, indention, "<head>")
            indention += 1
            write_line(f, indention, '<meta charset="UTF-8">')
            write_line(f, indention, "<title>{}.{} - {}</title>".format(result_json["tool"], result_json["configuration-id"], result_json["benchmark-id"]))
            write_line(f, indention, '<link rel="stylesheet" type="text/css" href=../style.css>')
            indention -= 1
            write_line(f, indention, '</head>')
            write_line(f, indention, '<body>')
            write_line(f, indention, '<h1>{}.{}</h1>'.format(result_json["tool"],result_json["configuration-id"]))

            write_line(f, indention, '<div class="box">')
            indention += 1
            write_line(f, indention, '<div class="boxlabelo"><div class="boxlabelc">Benchmark</div></div>')
            write_line(f, indention, '<table style="margin-bottom: 0.75ex;">')
            indention += 1
            write_line(f, indention, '<tr><td>id:</td><td>{} ({})</td></tr>'.format(result_json["benchmark-id"], result_json["benchmark"]["model"]["type"].upper()))
            indention -= 1
            write_line(f, indention, "</table>")
            indention -= 1
            write_line(f, indention, "</div>")

            write_line(f, indention, '<div class="box">')
            indention += 1
            write_line(f, indention, '<div class="boxlabelo"><div class="boxlabelc">Invocation ({})</div></div>'.format(result_json["configuration-id"]))
            f.write('\t' * indention + '<pre style="overflow: auto; padding-bottom: 1.5ex; padding-top: 1ex; font-size: 15px; margin-bottom: 0ex;  margin-top: 0ex;">')
            commands_str = "\n".join(result_json["commands"])
            f.write(commands_str)
            f.write('</pre>\n')
            write_line(f, indention, result_json["invocation-note"])
            indention -= 1
            write_line(f, indention, "</div>")

            write_line(f, indention, '<div class="box">')
            indention += 1
            write_line(f, indention, '<div class="boxlabelo"><div class="boxlabelc">Execution</div></div>')
            write_line(f, indention, '<table style="margin-bottom: 0.75ex;">')
            indention += 1
            if result_json["timeout"]:
                write_line(f, indention, '<tr><td>Walltime:</td><td style="color: red;">&gt {}s (Timeout)</td></tr>'.format(result_json["time-limit"]))
            else:
                write_line(f, indention, '<tr><td>Walltime:</td><td style="tt">{}s</td></tr>'.format(result_json["wallclock-time"]))
                if "model-checking-time" in result_json:
                    write_line(f, indention, '<tr><td>Model Checking Walltime:</td><td style="tt">{}s</td></tr>'.format(result_json["model-checking-time"]))
                return_codes = []
                if "return-codes" in result_json:
                    return_codes = result_json["return-codes"]
                if result_json["execution-error"]:
                    write_line(f, indention, '<tr><td>Return code:</td><td style="tt; color: red;">{}</td></tr>'.format(", ".join([str(rc) for rc in return_codes])))
                else:
                    write_line(f, indention, '<tr><td>Return code:</td><td style="tt">{}</td></tr>'.format(", ".join([str(rc) for rc in return_codes])))
            first = True
            for note in result_json["notes"]:
                write_line(f, indention, '<tr><td>{}</td><td>{}</td></tr>'.format("Note(s):" if first else "", note))
                first = False
            indention -= 1
            write_line(f, indention, "</table>")
            indention -= 1
            write_line(f, indention, "</div>")

            pos1 = log.find("\n", log.find("Output:\n")) + 1
            pos2 = log.find("##############################Output to stderr##############################\n")
            pos_end = pos2 if pos2 >= 0 else len(log)
            log_str = log[pos1:pos_end].strip()
            if len(log_str) != 0:
                write_line(f, indention, '<div class="box">')
                indention += 1
                write_line(f, indention, '<div class="boxlabelo"><div class="boxlabelc">Log</div></div>')
                f.write("\t" * indention + '<pre style="overflow:auto; padding-bottom: 1.5ex">')
                f.write(log_str)
                write_line(f, indention, '</pre>')
                indention -= 1
                write_line(f, indention, "</div>")
            if pos2 >= 0:
                pos2 = log.find("\n", pos2) + 1
                write_line(f, indention, '<div class="box">')
                indention += 1
                write_line(f, indention, '<div class="boxlabelo"><div class="boxlabelc">STDERR</div></div>')
                f.write("\t" * indention + '<pre style="overflow:auto; padding-bottom: 1.5ex">')
                f.write(log[pos2:].strip())
                write_line(f, indention, '</pre>')
                indention -= 1
                write_line(f, indention, "</div>")
            write_line(f, indention, "</body>")
            write_line(f, indention, "</html>")
        return f_path

    num_cols = len(table_data[0])
    first_tool_col = num_cols - num_tool_configs

    with open (os.path.join(path, "table.html"), 'w') as tablefile:
        tablefile.write(r"""<!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Benchmark results</title>
      <link rel="stylesheet" type="text/css" href="style.css">
      <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.13/css/jquery.dataTables.min.css">
      <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.2.4/css/buttons.dataTables.min.css">
      <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/fixedheader/3.1.2/css/fixedHeader.dataTables.min.css">

      <script type="text/javascript" language="javascript" charset="utf8" src="https://code.jquery.com/jquery-1.12.4.js"></script>
      <script type="text/javascript" language="javascript" charset="utf8" src="https://cdn.datatables.net/1.10.13/js/jquery.dataTables.min.js"></script>
      <script type="text/javascript" language="javascript" charset="utf8" src="https://cdn.datatables.net/fixedheader/3.1.2/js/dataTables.fixedHeader.min.js"></script>
      <script type="text/javascript" language="javascript" charset="utf8" src="https://cdn.datatables.net/buttons/1.2.4/js/dataTables.buttons.min.js"></script>
      <script type="text/javascript" language="javascript" charset="utf8" src="https://cdn.datatables.net/buttons/1.2.4/js/buttons.colVis.min.js"></script>

      <script>
        $(document).ready(function() {
          // Set correct file
          $("#content").load("data.html");
        } );

        function updateBest(table) {
          // Remove old best ones
          table.cells().every( function() {
            $(this.node()).removeClass("best");
          });
          table.rows().every( function ( rowIdx, tableLoop, rowLoop ) {
              var bestValue = -1
              var bestIndex = -1
              $.each( this.data(), function( index, value ){
                if (index >= """ + str(first_tool_col) + """ && table.column(index).visible()) {
    			    var text = $(value).text()
    	            if (["TO", "ERR", "INC", "MO", "NS", ""].indexOf(text) < 0) {
    				    var number = parseFloat(text);
    	                if (bestValue == -1 || bestValue > number) {
    	                  // New best value
    	                  bestValue = number;
    	                  bestIndex = index;
    	                }
    				  }
    			  }
              });
              // Set new best
              if (bestIndex >= 0) {
                $(table.cell(rowIdx, bestIndex).node()).addClass("best");
              }
          } );
      }
      </script>
    </head>
    """)
        indention = 0
        write_line(tablefile, indention, "<body>")
        write_line(tablefile, indention, "<div>")
        indention +=1
        write_line(tablefile, indention, '<table id="table" class="display">')
        indention += 1
        write_line(tablefile, indention, '<thead>')
        indention += 1
        write_line(tablefile, indention, '<tr>')
        indention += 1
        for head in table_data[0]:
            write_line(tablefile, indention, '<th>{}</th>'.format(head))
        indention -= 1
        write_line(tablefile, indention, '</tr>')
        indention -= 1
        write_line(tablefile, indention, '</thead>')
        write_line(tablefile, indention, '<tbody>')
        indention += 1

        for row in table_data[1:]:
            for cell_content in row:
                if not SHOW_UNSUPPORTED and (type(cell_content) == list and cell_content[0] == "NS") or (cell_content == "NS"):
                    cell_content = ""
                elif type(cell_content) == list:
                    logpage = create_log_page(cell_content[1])
                    style_classes = dict(TO="timeout", ERR="error", INC ="incorrect", MO="memout", NS="unsupported")
                    link_attributes = "class='{}'".format(style_classes[cell_content[0]]) if cell_content[0] in style_classes else ""
                    cell_content = "<a href='{}' {}>{}</a>".format(logpage, link_attributes, cell_content[0])
                write_line(tablefile, indention, f'<td>{cell_content}</td>')
            indention -= 1
            write_line(tablefile, indention, '</tr>')
        indention -= 1
        write_line(tablefile, indention, '</tbody>')
        indention -= 1
        indention -= 1
        write_line(tablefile, indention, '</table>')
        write_line(tablefile, indention, "<script>")
        indention +=1
        write_line(tablefile, indention, 'var table = $("#table").DataTable( {')
        indention += 1
        write_line(tablefile, indention, '"paging": false,')
        write_line(tablefile, indention, '"autoWidth": false,')
        write_line(tablefile, indention, '"info": false,')
        write_line(tablefile, indention, 'fixedHeader: {')
        indention += 1
        write_line(tablefile, indention, '"header": true,')
        indention -= 1
        write_line(tablefile, indention, '},')
        write_line(tablefile, indention, '"dom": "Bfrtip",')
        write_line(tablefile, indention, 'buttons: [')
        indention += 1
        for columnIndex in range(first_tool_col, num_cols):
            write_line(tablefile, indention, '{')
            indention += 1
            write_line(tablefile, indention, 'extend: "columnsToggle",')
            write_line(tablefile, indention, 'columns: [{}],'.format(columnIndex))
            indention -= 1
            write_line(tablefile, indention, "},")
        tool_columns = [i for i in range(first_tool_col, num_cols)]
        for text, show, hide in zip(["Show all", "Hide all"], [tool_columns, []], [[], tool_columns]):
            write_line(tablefile, indention, '{')
            indention += 1
            write_line(tablefile, indention, 'extend: "colvisGroup",')
            write_line(tablefile, indention, 'text: "{}",'.format(text))
            write_line(tablefile, indention, 'show: {},'.format(show))
            write_line(tablefile, indention, 'hide: {}'.format(hide))
            indention -= 1
            write_line(tablefile, indention, "},")
        indention -= 1
        write_line(tablefile, indention, "],")
        indention -= 1
        write_line(tablefile, indention, "});")
        indention -= 1
        write_line(tablefile, indention, "")
        indention += 1
        write_line(tablefile, indention, 'table.on("column-sizing.dt", function (e, settings) {')
        indention += 1
        write_line(tablefile, indention, "updateBest(table);")
        indention -= 1
        write_line(tablefile, indention, "} );")
        indention -= 1
        write_line(tablefile, indention, "")
        indention += 1
        write_line(tablefile, indention, "updateBest(table);")
        indention -= 1
        write_line(tablefile, indention, "</script>")
        indention -= 1
        write_line(tablefile, indention, "</div>")
        write_line(tablefile, indention, "</body>")
        write_line(tablefile, indention, "</html>")

    with open (os.path.join(path, "style.css"), 'w') as stylefile:
        stylefile.write(r"""

    .best {
        background-color: lightgreen;
    }
    .error {
    	font-weight: bold;
    	background-color: lightcoral;
    }
    .incorrect {
        background-color: orange;
    	font-weight: bold;
    }
    .timeout {
        background-color: lightgray;
    }
    .memout {
        background-color: lightgray;
    }
    .unsupported {
        background-color: yellow;
    }
    .ignored {
        background-color: blue;
    }

    h1 {
    	font-size: 28px; font-weight: bold;
    	color: #000000;
    	padding: 1px; margin-top: 20px; margin-bottom: 1ex;
    }

    tt, .tt {
    	font-family: 'Courier New', monospace; line-height: 1.3;
    }

    .box {
    	margin: 2.5ex 0ex 1ex 0ex; border: 1px solid #D0D0D0; padding: 1.6ex 1.5ex 1ex 1.5ex; position: relative;
    }

    .boxlabelo {
    	position: absolute; pointer-events: none; margin-bottom: 0.5ex;
    }

    .boxlabel {
    	position: relative; top: -3.35ex; left: -0.5ex; padding: 0px 0.5ex; background-color: #FFFFFF; display: inline-block;
    }
    .boxlabelc {
    	position: relative; top: -3.17ex; left: -0.5ex; padding: 0px 0.5ex; background-color: #FFFFFF; display: inline-block;
    }
    """)



def save_latex(
    table_data,
    cols,
    header,
    path,
    grid=False,
    tabcolsep="3pt",
    font_size=LATEX_TABLE_FONT_SIZE,
    alternating_rows=False,
    family_lines=False,
    arraystretch=None,
):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as latex_file:
        latex_file.write("\n")
        if arraystretch is not None:
            latex_file.write(r"\begingroup" + "\n")
            latex_file.write(rf"\renewcommand{{\arraystretch}}{{{arraystretch}}}" + "\n")
        latex_file.write(rf"\renewcommand{{\tabcolsep}}{{{tabcolsep}}}" + "\n")
        latex_file.write(rf"\{font_size}" + "\n")
        latex_file.write(r"\begin{tabular}{@{}")
        latex_file.write(cols)
        latex_file.write("@{}}\n\n")
        latex_file.write(r"\toprule" + "\n")
        latex_file.write(header + "\\\\\\midrule\n")
        previous_family = None
        for row_index, row in enumerate(table_data[1:]):
            model_cell = row[0]
            family = model_cell[0] if isinstance(model_cell, (list, tuple)) else model_cell
            row_span = max(
                (len(cell) if isinstance(cell, (list, tuple)) else 1)
                for cell in row
            )
            if family_lines and previous_family is not None and family != previous_family:
                latex_file.write(r"\midrule" + "\n")
            previous_family = family
            for line_index in range(row_span):
                line = []
                for cell in row:
                    if isinstance(cell, (list, tuple)):
                        if line_index < len(cell):
                            line.append(cell[line_index])
                        else:
                            color = re.match(r"(\\cellcolor\{[^}]+\})", cell[0]) if cell else None
                            line.append(color.group(1) if color is not None else "")
                    elif row_span == 1:
                        line.append(cell)
                    else:
                        if alternating_rows:
                            line.append(
                                rf"\multirow{{-{row_span}}}{{*}}{{{cell}}}"
                                if line_index == row_span - 1 else ""
                            )
                        else:
                            line.append(
                                rf"\multirow{{{row_span}}}{{*}}{{{cell}}}"
                                if line_index == 0 else ""
                            )
                row_color = (
                    r"\rowcolor{gray!20}"
                    if alternating_rows and row_index % 2 == 1 else ""
                )
                if row_color:
                    line = [
                        cell.replace(
                            rf"\cellcolor{{{LATEX_HIGHLIGHT_COLOR}}}",
                            rf"\cellcolor{{{LATEX_SHADED_HIGHLIGHT_COLOR}}}",
                        )
                        for cell in line
                    ]
                latex_file.write(row_color + "\t" + "\t&\t".join(line) + "\\\\\n")
        latex_file.write(r"\bottomrule" + "\n")
        latex_file.write("\\end{tabular}\n")
        if arraystretch is not None:
            latex_file.write(r"\endgroup" + "\n")

def fixed_latex_column(alignment, width):
    declarations = {
        "center": r"\centering",
        "right": r"\raggedleft",
        "left": r"\raggedright",
    }
    return rf">{{{declarations[alignment]}\arraybackslash}}p{{{width}}}"

def parse_result_value(result):
    """Return (relation, value), where relation is '=', '≤', or '≥'."""
    number_pattern = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    scalar_match = re.fullmatch(
        rf"\s*([≤≥])?\s*({number_pattern})\s*",
        str(result),
    )
    if scalar_match is not None:
        return scalar_match.group(1) or "=", float(scalar_match.group(2))

    interval_match = re.fullmatch(
        rf"\s*\[\s*({number_pattern})\s*,\s*({number_pattern})\s*\]"
        rf"(?:\s*\(width\s*=\s*({number_pattern})\))?\s*",
        str(result),
    )
    if interval_match is not None:
        lower = float(interval_match.group(1))
        upper = float(interval_match.group(2))
        if math.isclose(lower, upper, rel_tol=1e-12, abs_tol=1e-15):
            return "=", (lower + upper) / 2
        raise ValueError(f"Non-degenerate interval result is not supported: {result}")

    raise ValueError(f"Unexpected result string: {result}")

def is_successful_result(data, maxtime=None):
    if data is None or "result" not in data:
        return False
    if any(data.get(key, False) for key in ["timeout", "memout", "numerical-error", "execution-error", "expected-error", "not-supported"]):
        return False
    return maxtime is None or data["wallclock-time"] <= maxtime

def expected_bound_relation(cfgbase, benchmark):
    direction = benchmark["property"]["dir"]
    if cfgbase in ["cut", "clip"]: # under-approximation
        return "≥" if direction == "max" else "≤"
    if cfgbase == "discr": # over-approximation
        return "≤" if direction == "max" else "≥"
    return None

def comparison_value(value):
    return round(float(value), RESULT_COMPARISON_DECIMALS)

def result_selection_score(data, expected_relation):
    relation, result = parse_result_value(data["result"])
    if relation == "=":
        # Every exact result is preferable to a bound. Exact results for one
        # benchmark are expected to agree, so use runtime as the tie-breaker.
        return (1, 0, -data["wallclock-time"])
    if expected_relation is not None and relation != expected_relation:
        raise ValueError(f"Expected a '{expected_relation}' bound, got '{data['result']}'")
    quality = comparison_value(result)
    quality = quality if relation == "≥" else -quality
    return (0, quality, -data["wallclock-time"])

def parse_tool_output(execution_json):
    with open(execution_json["log"], 'r') as logfile:
        log = logfile.read()
    execution_json["notes"] = [execution_json["invocation-note"]]
    execution_json["benchmark"] = benchmarks.from_id(execution_json["benchmark-id"])

    assert execution_json["tool"] in TOOL_NAMES, "Error: Unknown tool '{}'".format(execution_json["tool"])
    tool = TOOL_NAMES[execution_json["tool"]]
    execution_json["configuration"] = tool.config_from_id(execution_json["configuration-id"])
    tool.parse_logfile(log, execution_json)

    # Notes are exported in parsed metadata; keep the measured source log intact.

# stores benchmark-instance specific data from the execution. Reports inconsistencies with other executions on the same instance
def process_benchmark_instance_data(benchmark_instances, execution_json):
    # gather data from this execution
    bench_id = execution_json["benchmark"]["id"]
    bench_data = OrderedDict()
    bench_data["id"] = execution_json["benchmark"]["id"]
    bench_data["benchmark-set"] = execution_json["benchmark"]["benchmark-set"]
    bench_data["name"] = execution_json["benchmark"]["name"]
    bench_data["formalism"] = execution_json["benchmark"]["model"]["formalism"]
    bench_data["type"] = execution_json["benchmark"]["model"]["type"]
    bench_data["par"] = "_".join(bench_id.split("_")[3:])
    bench_data["property"] = execution_json["benchmark"]["property"]["type"]
    bench_data["property-dir"] = execution_json["benchmark"]["property"]["dir"]
    bench_data["property-id"] = execution_json["benchmark"]["property"]["id"]
    bench_data["dim"] = execution_json["benchmark"]["property"].get("num-bnd-rew-assignments", 0)
    bench_data["states"] = execution_json["input-model"]["states"]
    if execution_json["benchmark"]["model"]["type"] != "dtmc":
        bench_data["choices"] = execution_json["input-model"]["choices"]
    if execution_json["benchmark"]["model"]["type"] == "pomdp":
        bench_data["observations"] = execution_json["input-model"]["observations"]
    bench_data["transitions"] = execution_json["input-model"]["transitions"]
    bench_data["invocations"] = [execution_json["id"]]

    # incorporate into existing data
    if not bench_id in benchmark_instances:
        benchmark_instances[bench_id] = bench_data
    else:
        # ensure consistency
        for key in ["id", "name", "formalism", "type", "par", "property", "property-dir", "property-id", "dim", "states", "choices", "observations", "transitions"]:
            if key in bench_data:
                if key in benchmark_instances[bench_id]:
                    if benchmark_instances[bench_id][key] != bench_data[key]:
                        print("WARN: Inconsistency with field {}: '{}' vs '{}'  between any of \n\t{}\nand\t{}".format(key,benchmark_instances[bench_id][key], bench_data[key], benchmark_instances[bench_id]["invocations"], bench_data["invocations"]))
                else:
                    benchmark_instances[bench_id][key] = bench_data[key]
        # append data
        for key in ["invocations"]:
            if key in bench_data:
                if key in benchmark_instances[bench_id]:
                    benchmark_instances[bench_id][key] += bench_data[key]
                else:
                    benchmark_instances[bench_id][key] = bench_data[key]

def gather_execution_data(logdirs, silent=False):
    exec_data = OrderedDict() # Tool -> Config -> Benchmark -> Data
    benchmark_instances = OrderedDict() # ID -> data
    known_benchmark_ids = {benchmark["id"] for benchmark in benchmarks.INSTANCES}

    for logdir_input in logdirs:
        logdir = os.path.expanduser(logdir_input)
        if not os.path.isdir(logdir):
            print("Error: Directory '{}' does not exist.".format(logdir))

        print("\nGathering execution data for logfiles in {} ...".format(logdir))
        json_files = [ f for f in os.listdir(logdir) if f.endswith(".json") and os.path.isfile(os.path.join(logdir, f)) ]
        ignored_benchmarks = Counter()
        ignored_configurations = Counter()
        i = 0
        for execution_json in [ load_json(os.path.join(logdir, f)) for f in json_files ]:
            benchmark = execution_json["benchmark-id"]
            if benchmark not in known_benchmark_ids:
                ignored_benchmarks[benchmark] += 1
                continue
            tool = execution_json["tool"]
            config = execution_json["configuration-id"]
            if config in getattr(TOOL_NAMES.get(tool), "RETIRED_CONFIG_IDS", ()):
                ignored_configurations[config] += 1
                continue
            i += 1
            exec_data.setdefault(tool, OrderedDict())
            exec_data[tool].setdefault(config, OrderedDict())
            assert benchmark not in exec_data[tool][config], "Error: Multiple result files found for {}.{}.{}".format(tool,config,benchmark)
            execution_json["log"] = os.path.join(logdir, execution_json["log"])
            try:
                parse_tool_output(execution_json)
            except AssertionError as e:
                print("Error when parsing logfile {}:\n{}".format(execution_json["log"], e))
                continue
            exec_data[tool][config][benchmark] = execution_json
            if "input-model" in execution_json:
                process_benchmark_instance_data(benchmark_instances, execution_json)
            else:
                print(f"WARN: No input-model statistics in failed execution {execution_json['id']}")

        for benchmark, count in sorted(ignored_benchmarks.items()):
            print(f"WARN: Ignoring {count} result file(s) for removed benchmark {benchmark}")
        for config, count in sorted(ignored_configurations.items()):
            print(f"Ignoring {count} archived result file(s) for retired configuration {config}")

    # warn for missing configs:
    if not silent:
        for t in TOOL_NAMES:
            if t not in list(exec_data.keys()) + []: print(f"WARN: no data for tool '{t}'") # no warning for tools in the given list
            else:
                for cfg in TOOL_NAMES[t].CONFIGS:
                    if cfg["id"] not in list(exec_data[t].keys()) + ["split"]: print(f"WARN: no data for {t} config '{cfg['id']}'") #no warning for configs in the given list
    return exec_data, benchmark_instances

def process_meta_configs(exec_data, benchmark_instances):
    # gather data for meta-configurations
    for tool in exec_data:
        active_config_ids = {cfg["id"] for cfg in TOOL_NAMES[tool].CONFIGS}
        for metacfg in TOOL_NAMES[tool].META_CONFIGS:
            benchmark_data = OrderedDict()
            for benchmark in benchmark_instances:
                best_cfg_id = None
                expected_relation = expected_bound_relation(metacfg["cfgbase"], benchmarks.from_id(benchmark))
                for cfg_id in exec_data[tool]:
                    if cfg_id not in active_config_ids: continue
                    if not cfg_id.startswith(metacfg["cfgbase"]): continue
                    if benchmark not in  exec_data[tool][cfg_id]: continue
                    data = exec_data[tool][cfg_id][benchmark]
                    if not is_successful_result(data, metacfg.get("maxtime")): continue
                    if best_cfg_id is None:
                        try:
                            result_selection_score(data, expected_relation)
                            best_cfg_id = cfg_id
                        except ValueError as e:
                            print(f"WARN: {e} in {data['id']}")
                        continue
                    try:
                        if result_selection_score(data, expected_relation) > result_selection_score(exec_data[tool][best_cfg_id][benchmark], expected_relation):
                            best_cfg_id = cfg_id
                    except ValueError as e:
                        print(f"WARN: {e} in {data['id']}")
                if best_cfg_id is not None: benchmark_data[benchmark] = copy.deepcopy(exec_data[tool][best_cfg_id][benchmark])
            exec_data[tool][metacfg["id"]] = benchmark_data

def get_result(exec_data, tool, config, inst_id):
        if tool in exec_data and config in exec_data[tool] and inst_id in exec_data[tool][config]:
            return exec_data[tool][config][inst_id]

def get_result_if_supported(exec_data, tool, config, inst_id):
        res = get_result(exec_data, tool, config, inst_id)
        if res is not None and not res["not-supported"]:
            return res

def latex_number(value, decimal_places=None):
    value = float(value)
    if value != 0 and abs(value) >= 10**5:
        exponent = math.floor(math.log10(abs(value)))
        coefficient = round(value / 10**exponent, decimal_places or 2)
        if abs(coefficient) >= 10:
            coefficient /= 10
            exponent += 1
        coefficient_format = (
            f"{coefficient:.{decimal_places}f}"
            if decimal_places is not None else f"{coefficient:.3g}"
        )
        return rf"{coefficient_format}{{\cdot}}10^{{{exponent}}}"

    if decimal_places is not None:
        return f"{value:.{decimal_places}f}"

    # Keep three significant digits without letting Python switch to
    # scientific notation for values below 10^5.
    if value == 0:
        return "0"
    decimal_places = 2 - math.floor(math.log10(abs(value)))
    rounded = round(value, decimal_places) if decimal_places < 0 else value
    formatted = f"{rounded:.{max(0, decimal_places)}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted

def latex_size(value):
    value = int(value)
    if abs(value) < 1_000_000:
        return str(value)
    exponent = math.floor(math.log10(abs(value)))
    coefficient = round(value / 10**exponent, 2)
    if abs(coefficient) >= 10:
        coefficient /= 10
        exponent += 1
    return rf"{coefficient:.2f}{{\cdot}}10^{{{exponent}}}"

def latex_belief_mdp_size(result):
    if result is None:
        return ""
    states = result.get("belief-mdp", {}).get("states")
    return "" if states is None else rf"${latex_size(states)}$"

def latex_result(result, bold=False, decimal_places=None):
    relation, value = parse_result_value(result)
    relation_latex = {"=": "", "≤": r"\le ", "≥": r"\ge "}[relation]
    value_latex = latex_number(value, decimal_places)
    if bold:
        value_latex = rf"\mathbf{{{value_latex}}}"
    return f"${relation_latex}{value_latex}$"

def latex_mdp_bound(result, direction, bold=False, decimal_places=None):
    _, value = parse_result_value(result)
    relation = "≥" if direction == "min" else "≤"
    return latex_result(f"{relation}{value}", bold, decimal_places)

def latex_time(value):
    if value < 1.0:
        return r"\textless 1"
    if value < 100:
        return f"{value:.1f}"
    return f"{value:.0f}"

def latex_configuration_parameter(cfgbase, cfg_id):
    if cfgbase == "cut":
        match = re.fullmatch(r"cut(\d{2})", cfg_id)
        if match is not None:
            threshold = r"\mathrm{def.}" if match.group(1) == "00" else f"2^{{{int(match.group(1))}}}"
            return f"$\\sizethreshold{{=}}{threshold}$"
    elif cfgbase == "clip":
        match = re.fullmatch(r"clip(\d{2})res(\d{2})", cfg_id)
        if match is not None:
            threshold = r"\mathrm{def.}" if match.group(1) == "00" else f"2^{{{int(match.group(1))}}}"
            return fr"$\sizethreshold{{=}}{threshold},\resolution{{=}}{int(match.group(2))}$"
    elif cfgbase == "discr":
        match = re.fullmatch(r"discr(\d{3})s", cfg_id)
        if match is not None:
            return fr"$\resolution{{=}}{int(match.group(1))}$"
    return cfg_id.replace("_", r"\_")

def unavailable_result_cell(exec_data, config_ids, inst_id):
    runs = [get_result(exec_data, storm.NAME, cfg_id, inst_id) for cfg_id in config_ids]
    runs = [run for run in runs if run is not None]
    if len(runs) == 0:
        return ""

    statuses = set()
    for run in runs:
        # A killed process is also recorded as an execution error by the runner.
        # Classify each execution by its most specific cause so that a memory-out
        # is not additionally reported as a generic error.
        if run.get("timeout", False):
            statuses.add("TO")
        elif run.get("memout", False):
            statuses.add("MO")
        elif (run.get("execution-error", False) or run.get("expected-error", False)
              or run.get("not-supported", False) or "result" not in run):
            statuses.add("ERR")

    status_order = ["TO", "MO", "ERR"]
    return " / ".join(status for status in status_order if status in statuses) or "ERR"

def is_failure_status(status):
    return len(status.split(" / ")) > 0 and all(
        item in ["TO", "MO", "ERR"] for item in status.split(" / ")
    )

def failure_status_cell(status):
    return status


def highlighted_cell_lines(lines, highlight=False):
    if not highlight:
        return lines
    return [rf"\cellcolor{{{LATEX_HIGHLIGHT_COLOR}}}" + line for line in lines]

def result_time_lines(result, runtime=None):
    if runtime is None:
        return [result]
    return [result, f"{latex_time(runtime)}s"]

def dissertation_cell(result, runtime=None, parameter=None, highlight=False):
    if runtime is None and parameter is None and is_failure_status(result):
        return failure_status_cell(result)
    lines = result_time_lines(result, runtime)
    if parameter is not None:
        lines.append(parameter)
    return highlighted_cell_lines(lines, highlight)

def dissertation_result_cell(exec_data, inst_id, cfgbase, timelimit, highlight=False):
    metacfg_id = f"{cfgbase}-best-in-{timelimit}s"
    result = get_result(exec_data, storm.NAME, metacfg_id, inst_id)
    if result is None:
        config_ids = [cfg["id"] for cfg in storm.CONFIGS if cfg["id"].startswith(cfgbase)]
        return dissertation_cell(unavailable_result_cell(exec_data, config_ids, inst_id))
    parameter = latex_configuration_parameter(cfgbase, result["configuration-id"])
    return dissertation_cell(
        latex_result(
            result["result"], highlight, dissertation_result_decimal_places(inst_id)
        ),
        result["wallclock-time"],
        parameter,
        highlight,
    )

def dissertation_property(instance):
    property_symbol = "P" if instance["property"] == "prb" else "R"
    base_id = instance["property"] + instance["property-dir"]
    qualifier = instance["property-id"][len(base_id):]
    qualifier = {"packets": "pack"}.get(qualifier, qualifier)
    qualifier_latex = "" if qualifier == "" else rf"^{{\mathrm{{{qualifier}}}}}"
    return rf"${property_symbol}_\mathrm{{{instance['property-dir']}}}{qualifier_latex}$"

def dissertation_result_decimal_places(inst_id):
    return None if benchmarks.from_id(inst_id)["property"]["type"] == "prb" else 2

def dissertation_parameters(instance):
    crypt_sizes = {"crypt": "2", "crypt4": "4", "crypt6": "6"}
    if instance["benchmark-set"] in crypt_sizes:
        return crypt_sizes[instance["benchmark-set"]]
    parameters = instance["par"].replace("_", r"\_")
    return "sl0" if re.fullmatch(r"sl0+", parameters) else parameters

def latex_model_name(name):
    return LATEX_MODEL_ABBREVIATIONS.get(name, name)

def dissertation_model(instance, finite_belief_mdp=False):
    model = f"\\model{{{latex_model_name(instance['name'])}}}"
    if finite_belief_mdp:
        model += "$^*$"
    parameters = dissertation_parameters(instance)
    return model if parameters == "" else [model, f"\\model{{{parameters}}}"]

def dissertation_model_identity(benchmark):
    model = benchmark["model"]
    return (
        model["file"],
        tuple(model.get("file-parameters", {}).items()),
        tuple(model.get("open-parameters", {}).items()),
    )

def finite_belief_mdp_models(exec_data, benchmark_instances):
    finite_models = set()
    cutoff_ids = [cfg["id"] for cfg in storm.CONFIGS if cfg["id"].startswith("cut")]
    for benchmark in benchmarks.INSTANCES:
        inst_id = benchmark["id"]
        if inst_id not in benchmark_instances:
            continue
        for config_id in cutoff_ids:
            result = get_result(exec_data, storm.NAME, config_id, inst_id)
            if (is_successful_result(result) and
                    "belief-mdp" in result and
                    "states" in result["belief-mdp"] and
                    not result.get("belief-mdp-incomplete", False) and
                    parse_result_value(result["result"])[0] == "="):
                finite_models.add(dissertation_model_identity(benchmark))
                break
    return finite_models

def save_dissertation_tables(exec_data, benchmark_instances, timelimit=None):
    if timelimit is None:
        timelimit = storm.META_CONFIG_TIMELIMITS[0]
    model_column = fixed_latex_column("center", "16mm")
    objective_column = fixed_latex_column("center", "10mm")
    result_column = fixed_latex_column("right", "21.5mm")
    benchmark_headers = [
        "Model",
        "Parameters",
        r"States",
        r"Choices",
        r"Observations",
    ]
    result_headers = [
        "Model",
        "Obj.",
        r"\config{cut}",
        r"\config{clip}",
        r"\config{mdp}",
        r"\config{discr}",
    ]

    benchmark_rows = [[]]
    benchmark_families = OrderedDict()
    seen_models = set()
    finite_models = finite_belief_mdp_models(exec_data, benchmark_instances)
    for benchmark in benchmarks.INSTANCES:
        if benchmark["id"] not in benchmark_instances:
            continue
        model_identity = dissertation_model_identity(benchmark)
        if model_identity in seen_models:
            continue
        seen_models.add(model_identity)
        instance = benchmark_instances[benchmark["id"]]
        benchmark_families.setdefault(instance["name"], []).append((instance, model_identity))

    for family_name, parameterisations in benchmark_families.items():
        family_cell = f"\\model{{{latex_model_name(family_name)}}}"
        parameters = []
        states = []
        choices = []
        observations = []
        for instance, model_identity in parameterisations:
            parameter = dissertation_parameters(instance)
            parameter_cell = "" if parameter == "" else f"\\model{{{parameter}}}"
            if model_identity in finite_models:
                if parameter == "":
                    family_cell += "$^*$"
                else:
                    parameter_cell += "$^*$"
            parameters.append(parameter_cell)
            states.append(str(instance["states"]))
            choices.append(str(instance["choices"]))
            observations.append(str(instance["observations"]))
        benchmark_rows.append([
            family_cell,
            parameters,
            states,
            choices,
            observations,
        ])
    save_latex(benchmark_rows, "c c | r r r", "\n& ".join(benchmark_headers), os.path.join(TABLE_DIR, "tablebenchmarks.tex"), grid=True, font_size="small", family_lines=True)

    objective_tables = [
        ("prb", "min", "tableprbmin.tex"),
        ("prb", "max", "tableprbmax.tex"),
        ("rew", "min", "tablerewmin.tex"),
        ("rew", "max", "tablerewmax.tex"),
    ]

    for property_type, direction, filename in objective_tables:
        instance_ids = [
            inst["id"] for inst in benchmarks.INSTANCES
            if inst["id"] in benchmark_instances and
               inst["property"]["type"] == property_type and
               inst["property"]["dir"] == direction
        ]
        rows = [[]]
        for inst_id in instance_ids:
            instance = benchmark_instances[inst_id]
            cut_id = f"cut-best-in-{timelimit}s"
            clip_id = f"clip-best-in-{timelimit}s"
            discr_id = f"discr-best-in-{timelimit}s"
            underapproximation_highlights = best_approximation_configs(
                exec_data, inst_id, [cut_id, clip_id], direction, "under", timelimit
            )
            overapproximation_highlights = best_approximation_configs(
                exec_data, inst_id, [discr_id, "mdp"], direction, "over", timelimit
            )
            mdp = get_result(exec_data, storm.NAME, "mdp", inst_id)
            if is_successful_result(mdp, timelimit):
                mdp_highlighted = "mdp" in overapproximation_highlights
                mdp_cell = dissertation_cell(
                    latex_mdp_bound(
                        mdp["result"], direction, mdp_highlighted,
                        dissertation_result_decimal_places(inst_id),
                    ),
                    mdp["wallclock-time"],
                    highlight=mdp_highlighted,
                )
            else:
                mdp_cell = dissertation_cell(unavailable_result_cell(exec_data, ["mdp"], inst_id))
            rows.append([
                dissertation_model(instance),
                dissertation_property(instance),
                dissertation_result_cell(exec_data, inst_id, "cut", timelimit, cut_id in underapproximation_highlights),
                dissertation_result_cell(exec_data, inst_id, "clip", timelimit, clip_id in underapproximation_highlights),
                mdp_cell,
                dissertation_result_cell(exec_data, inst_id, "discr", timelimit, discr_id in overapproximation_highlights),
            ])
        result_column_spec = (
            rf"{model_column}@{{\hspace{{0.5pt}}}}{objective_column} | "
            + " | ".join([result_column] * 4)
        )
        save_latex(
            rows,
            result_column_spec,
            "\n& ".join(result_headers),
            os.path.join(TABLE_DIR, filename),
            grid=True,
            tabcolsep="1pt",
            alternating_rows=True,
        )

def dissertation_value_cell(
    exec_data, inst_id, config_id, bold=False, configuration=None, bound_direction=None
):
    result = get_result(exec_data, storm.NAME, config_id, inst_id)
    belief_states = latex_belief_mdp_size(result)
    if is_successful_result(result):
        formatted_result = (
            latex_mdp_bound(
                result["result"], bound_direction, bold,
                dissertation_result_decimal_places(inst_id),
            )
            if bound_direction is not None else latex_result(
                result["result"], bold, dissertation_result_decimal_places(inst_id)
            )
        )
        lines = result_time_lines(formatted_result, result["wallclock-time"])
        lines.append(belief_states)
        if configuration is not None:
            lines.append(configuration)
        return lines
    status = unavailable_result_cell(exec_data, [config_id], inst_id)
    if is_failure_status(status):
        return failure_status_cell(status)
    lines = [status, belief_states]
    if configuration is not None:
        lines.append(configuration)
    return lines

def best_approximation_configs(exec_data, inst_id, config_ids, direction, approximation="over", maxtime=None):
    candidates = {}
    for config_id in config_ids:
        result = get_result(exec_data, storm.NAME, config_id, inst_id)
        if is_successful_result(result, maxtime):
            _, value = parse_result_value(result["result"])
            candidates[config_id] = (comparison_value(value), result["wallclock-time"])
    if len(candidates) == 0:
        return set()
    select_value = max if (approximation == "over") == (direction == "min") else min
    best_value = select_value(value for value, _ in candidates.values())
    best_value_candidates = {
        config_id: runtime for config_id, (value, runtime) in candidates.items()
        if value == best_value
    }
    best_runtime = min(best_value_candidates.values())
    return {config_id for config_id, runtime in best_value_candidates.items() if runtime == best_runtime}

def fastest_discretisation_matching_mdp(exec_data, inst_id, config_ids, direction):
    """Select by run wall time, comparing bounds at precision 10^-6."""
    mdp = get_result(exec_data, storm.NAME, "mdp", inst_id)
    if not is_successful_result(mdp):
        return None
    mdp_value = comparison_value(parse_result_value(mdp["result"])[1])
    candidates = {}
    for config_id in config_ids:
        result = get_result(exec_data, storm.NAME, config_id, inst_id)
        if not is_successful_result(result):
            continue
        value = comparison_value(parse_result_value(result["result"])[1])
        if (value >= mdp_value if direction == "min" else value <= mdp_value):
            candidates[config_id] = result["wallclock-time"]
    return min(candidates, key=candidates.get, default=None)


def save_overapproximation_table(exec_data, benchmark_instances):
    summary_model_column = fixed_latex_column("center", "20mm")
    summary_objective_column = fixed_latex_column("center", "12mm")
    summary_result_column = fixed_latex_column("right", "26.9mm")
    all_discretization_ids = [cfg["id"] for cfg in storm.CONFIGS
                              if cfg.get("family") == "discretisation"]
    summary_header = "\n& ".join([
        "Model", "Obj.", r"\config{mdp}",
        r"\config{discr} -- Fastest Matching",
        r"\config{discr} -- Tightest",
    ])
    objective_tables = [
        ("prb", "min", "tableoverapproxprbmin.tex"),
        ("prb", "max", "tableoverapproxprbmax.tex"),
        ("rew", "min", "tableoverapproxrewmin.tex"),
        ("rew", "max", "tableoverapproxrewmax.tex"),
    ]
    for property_type, direction, filename in objective_tables:
        summary_rows = [[]]
        for benchmark in benchmarks.INSTANCES:
            if (benchmark["property"]["type"] != property_type or
                    benchmark["property"]["dir"] != direction):
                continue
            inst_id = benchmark["id"]
            if inst_id not in benchmark_instances:
                continue
            instance = benchmark_instances[inst_id]
            best_discretization_ids = best_approximation_configs(
                exec_data, inst_id, all_discretization_ids, instance["property-dir"]
            )
            best_discretization_id = next(
                (config_id for config_id in all_discretization_ids
                 if config_id in best_discretization_ids), None
            )
            fastest_id = fastest_discretisation_matching_mdp(
                exec_data, inst_id, all_discretization_ids, direction
            )
            highlighted_ids = best_approximation_configs(
                exec_data, inst_id, [best_discretization_id, "mdp"], instance["property-dir"]
            )
            def selected_cell(config_id):
                if config_id is None:
                    return r"\textemdash"
                return dissertation_value_cell(
                    exec_data, inst_id, config_id, config_id in highlighted_ids,
                    latex_configuration_parameter("discr", config_id),
                )

            summary_rows.append([
                dissertation_model(instance),
                dissertation_property(instance),
                dissertation_value_cell(
                    exec_data, inst_id, "mdp", "mdp" in highlighted_ids,
                    bound_direction=direction,
                ),
                selected_cell(fastest_id),
                selected_cell(best_discretization_id),
            ])
        summary_column_spec = (
            rf"{summary_model_column}@{{\hspace{{0.5pt}}}}{summary_objective_column}"
            + f" | {summary_result_column}" * 3
        )
        save_latex(summary_rows, summary_column_spec, summary_header,
                   os.path.join(OVERAPPROX_TABLE_DIR, filename), grid=True,
                   tabcolsep="1pt", alternating_rows=True, arraystretch="0.95")


def underapproximation_summary_cell(exec_data, inst_id, config_id):
    result = get_result(exec_data, storm.NAME, config_id, inst_id)
    if is_successful_result(result):
        lines = result_time_lines(
            latex_result(
                result["result"], decimal_places=dissertation_result_decimal_places(inst_id)
            ),
            result["wallclock-time"],
        )
        lines.append(latex_belief_mdp_size(result))
        return lines
    status = unavailable_result_cell(exec_data, [config_id], inst_id)
    return failure_status_cell(status) if is_failure_status(status) else status


def underapproximation_summary_best_cell(
    exec_data, inst_id, cfgbase, timelimit, highlight=False
):
    metacfg_id = f"{cfgbase}-best-in-{timelimit}s"
    result = get_result(exec_data, storm.NAME, metacfg_id, inst_id)
    if result is None:
        config_ids = [cfg["id"] for cfg in storm.CONFIGS if cfg["id"].startswith(cfgbase)]
        return dissertation_cell(unavailable_result_cell(exec_data, config_ids, inst_id))
    lines = result_time_lines(
        latex_result(
            result["result"], highlight, dissertation_result_decimal_places(inst_id)
        ),
        result["wallclock-time"],
    )
    lines.extend([
        latex_belief_mdp_size(result),
        latex_configuration_parameter(cfgbase, result["configuration-id"]),
    ])
    return highlighted_cell_lines(lines, highlight)


def save_underapproximation_tables(
    exec_data, benchmark_instances, timelimit=storm.META_CONFIG_TIMELIMITS[0]
):
    summary_model_column = fixed_latex_column("center", "14mm")
    summary_objective_column = fixed_latex_column("center", "9mm")
    summary_result_column = fixed_latex_column("right", "15mm")
    objective_tables = [
        ("prb", "min", "prbmin"),
        ("prb", "max", "prbmax"),
        ("rew", "min", "rewmin"),
        ("rew", "max", "rewmax"),
    ]

    summary_clipping_resolutions = [2, 3, 4]
    heuristic_cutoff_id = "cut00"
    heuristic_clipping_ids = [
        f"clip00res{resolution:02}" for resolution in summary_clipping_resolutions
    ]
    summary_first_header = "\n& ".join([
        r"\multirow{2}{*}{Model}",
        r"\multirow{2}{*}{Obj.}",
        r"\multicolumn{2}{c|}{\config{cut}}",
        rf"\multicolumn{{{len(summary_clipping_resolutions) + 1}}}{{c}}{{\config{{clip}}}}",
    ])
    summary_second_header = "\n& ".join(
        ["", "", r"$\sizethreshold_\mathrm{heur.}$", "Tightest"]
        + [rf"$\resolution={resolution}$" for resolution in summary_clipping_resolutions]
        + ["Tightest"]
    )
    summary_header = summary_first_header + r"\\" + "\n" + summary_second_header
    summary_column_spec = (
        rf"{summary_model_column}@{{\hspace{{0.5pt}}}}{summary_objective_column}"
        + f" | {summary_result_column}" * 6
    )

    for property_type, direction, filename_suffix in objective_tables:
        summary_rows = [[]]
        for benchmark in benchmarks.INSTANCES:
            if (benchmark["property"]["type"] != property_type or
                    benchmark["property"]["dir"] != direction):
                continue
            inst_id = benchmark["id"]
            if inst_id not in benchmark_instances:
                continue
            cut_best_id = f"cut-best-in-{timelimit}s"
            clip_best_id = f"clip-best-in-{timelimit}s"
            best_ids = best_approximation_configs(
                exec_data,
                inst_id,
                [cut_best_id, clip_best_id],
                direction,
                approximation="under",
                maxtime=timelimit,
            )
            summary_rows.append([
                dissertation_model(benchmark_instances[inst_id]),
                dissertation_property(benchmark_instances[inst_id]),
                underapproximation_summary_cell(
                    exec_data, inst_id, heuristic_cutoff_id
                ),
                underapproximation_summary_best_cell(
                    exec_data, inst_id, "cut", timelimit, cut_best_id in best_ids
                ),
                *[
                    underapproximation_summary_cell(exec_data, inst_id, config_id)
                    for config_id in heuristic_clipping_ids
                ],
                underapproximation_summary_best_cell(
                    exec_data, inst_id, "clip", timelimit, clip_best_id in best_ids
                ),
            ])
        save_latex(
            summary_rows,
            summary_column_spec,
            summary_header,
            os.path.join(
                UNDERAPPROX_TABLE_DIR, f"tableunderapprox{filename_suffix}.tex"
            ),
            grid=True,
            tabcolsep="1pt",
            alternating_rows=True,
            arraystretch="0.72",
        )


def plot_quantile(values, probability):
    """Linearly interpolate an empirical quantile, as in the improvement plot."""
    values = sorted(values)
    position = probability * (len(values) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def prepared_boxplot(values, position, color):
    """Use min/max whiskers, retaining all successful observations."""
    if not values:
        return ""
    return (
        r"\addplot[draw=" + color + ",fill=" + color + r"!20,forget plot,"
        + r"boxplot/draw direction=y,boxplot/box extend=0.24,boxplot prepared={"
        + f"draw position={position},lower whisker={min(values)},"
        + f"lower quartile={plot_quantile(values, 0.25)},median={plot_quantile(values, 0.5)},"
        + f"upper quartile={plot_quantile(values, 0.75)},upper whisker={max(values)}"
        + r"}] coordinates {};" + "\n"
    )


def export_data(exec_data, benchmark_instances, export_kinds, prefix=""):
    SCATTER_MIN_VALUE, SCATTER_MAX_VALUE = 1, 1000
    QUANTILE_MIN_VALUE = 1

    def scatter_special_value(i): return round(SCATTER_MAX_VALUE * (math.sqrt(2)**i))


    def get_instances_num_supported(cfgs):
        res = Counter()
        for b_id in benchmark_instances:
            res[b_id] = len([c for c in cfgs if get_result_if_supported(exec_data, c[0], c[1], b_id) is not None])
        return res

    def get_instances_supported_by_some(cfgs):
        return [i[0] for i in get_instances_num_supported(cfgs).items() if i[1] > 0]

    def get_instances_supported_by_all(cfgs):
        return [i[0] for i in get_instances_num_supported(cfgs).items() if i[1] == len(cfgs)]

    def to_html(text):
        return html.escape(str(text))

    def to_latex(value, data_kind = None):
        if data_kind == "time":
            if value < 1.0: v = r"\textless 1"
            elif value < 100: v = f"{value:.1f}"
            else: v = f"{value:.0f}"
        elif type(value) == int:
            v = f"{value:.4g}"
            if "e+" in v: v = "{} {{\\cdot}} 10^{{{}}}".format(round(float(v[:v.find("e+")])), int(v[v.find("e+")+2:]))
        elif type(value) == bool:
            v = "yes" if value else "no"
        elif type(value) == list:
            if all(type(e) == int for e in value):
                if min(value) == max(value):
                    v = to_latex(min(value))
                else:
                    v = "{}..{}".format(to_latex(min(value)), to_latex(max(value)))
        elif type(value) == str and value.startswith("(") and value.endswith(")"):
            v = "{}".format(value[1:-1])
        elif type(value) == str and data_kind == "result":
            v = latex_result(value)
            data_kind = None # latex_result already formats the relation
        elif type(value) == str and data_kind == "name":
            value = value.replace("resources", "resrc").replace("obstacle", "obstcl").replace("service", "serv")
            v = f"\\model{{{latex_model_name(value)}}}"
        elif type(value) == str and data_kind == "par":
            v = value.replace("_", r"\_")
        elif type(value) == float:
            v = f"{value:.3g}"
            if "e+" in v: v = "{}{{$\\cdot$}}10$^\\text{{{}}}$".format(round(float(v[:v.find("e+")])), int(v[v.find("e+")+2:]))
            if "e-" in v: v = "{}{{$\\cdot$}}10$^\\text{{-{}}}$".format(round(float(v[:v.find("e-")])), int(v[v.find("e-")+2:]))
        else:
            v = value
        return v if data_kind is None or data_kind == "time" else f"${v}$"

    def get_cell_content(column, inst, kind):
        assert kind in export_kinds, f"Invalid kind for cell content: {kind}"
        value = None
        # first check if the column refers to a tool config
        tool = column[0]
        if tool in TOOL_NAMES: # the column is assumed to be a [tool, config, data_key] list, where data_key is the cell content key
            res = get_result_if_supported(exec_data, tool, column[1], inst)
            if res is None:
                if kind in ["default", "html"]:
                    value = "NS"
                elif kind in ["scatter"]:
                    value = scatter_special_value(2)
                elif kind.startswith("latex"):
                    value = "-"
                elif kind in ["quantile"]:
                    value = math.inf
            elif res["timeout"] == True:
                if kind in ["default", "html"]:
                    value = "TO"
                elif kind.startswith("latex"):
                    value = "TO"
                elif kind in ["scatter"]:
                    value = scatter_special_value(1) # TO
                elif kind in ["quantile"]:
                    value = math.inf
            elif res["memout"]:
                if kind in ["default", "html"]:
                    value = "MO"
                elif kind.startswith("latex"):
                    value = "MO"
                elif kind in ["scatter"]:
                    value = scatter_special_value(1)
                elif kind in ["quantile"]:
                    value = math.inf
            elif res["expected-error"] or res.get("execution-error", False):
                if kind in ["default", "html"]:
                    value = "ERR"
                elif kind.startswith("latex"):
                    value = "ERR"
                elif kind in ["scatter"]:
                    value = scatter_special_value(1)
                elif kind in ["quantile"]:
                    value = math.inf
            elif "result" in res:
                value = res[column[2]]
                if "time" in column[2]:
                    if kind in ["html"]:
                        value = f"{value:.1f}"
                    elif kind.startswith("latex"):
                        value = to_latex(value, "time")
                    elif kind in ["scatter"]:
                        value = max(SCATTER_MIN_VALUE, min(SCATTER_MAX_VALUE, value))
                    elif kind in ["quantile"]:
                        value = max(QUANTILE_MIN_VALUE, value)
                elif column[2] == "result" and kind.startswith("latex"):
                    value = to_latex(value, "result")
            if kind == "html":
                res = get_result(exec_data, tool, column[1], inst)
                if res is not None:
                    value = [value, res]
                    if "result" in res:
                        value[0] = to_html("{} / {}".format(res["result"], value[0]))
            elif kind.startswith("latex"):
                res = get_result(exec_data, tool, column[1], inst)
                if res is None or "result" not in res:
                    value = r"\multicolumn{1}{c}{-}"
                elif not is_successful_result(res):
                    pass # Keep the TO/MO/ERR marker selected above.
                else:
                    relation, result_number = parse_result_value(res["result"])
                    if relation != "=" and result_number == (1.0 if relation == "≤" else 0.0):
                        value = r"\multicolumn{1}{c}{-}"
                        return value
                    asterisk = ""
                    if "--belief-exploration unfold" in res["commands"][0] and "belief-mdp-incomplete" not in res:
                        asterisk = "$^*$"
                    value = "{} ({}s){}".format(latex_result(res["result"]), value, asterisk)
        else: # column[0] is a key in benchmark_instances, column[1] is either not present or a function that applies a transformation
            if column[0] in benchmark_instances[inst]:
                value = benchmark_instances[inst][column[0]]
            else: # info not available
                if kind in ["scatter", "quantile"]:
                    value = "nan"
                else:
                    value = "?"
            if len(column) > 1:
                value = column[1](value)
            elif kind.startswith("latex"):
                value = to_latex(value, column[0])
            elif kind in ["scatter"] and type(value) == list:
                if len(value) == 0: value = "nan"
                else: value = sum(value) / len(value) # average
            if type(value) == Counter:
                value = ", ".join([f"{k}: {v}" for k,v in value.items()])
            value = f"{value}"
        assert value is not None, f"No value found for column {column}, and instance {inst} (kind {kind})"
        return value

    def create_cells(columns, cfgs, kind, latex_highlight_best_col_indices = None):
        if kind == "quantile":
            rows = get_instances_supported_by_all(cfgs)
            header = ["i"] + [f"{c[0]}.{c[1]}" for c in columns[-len(cfgs):]]
            cells = [header] + [[i+1] for i in range(len(rows))]
            for c in columns[-len(cfgs):]:
                c_runtimes = sorted([get_cell_content(c, inst, kind) for inst in rows])
                for j in range(len(c_runtimes)):
                    cells[j+1].append(c_runtimes[j] if c_runtimes[j] != math.inf else "nan")
            return cells
        else:
            header = [c[0] for c in columns[:-len(cfgs)]]
            if len(cfgs) > 0: header += [f"{c[0]}.{c[1]}" for c in columns[-len(cfgs):]]
            rows = [i["id"] for i in benchmarks.INSTANCES if i["id"] in benchmark_instances]
            cells = [header]
            for inst in rows:
                cells.append([])
                for c in columns:
                    cells[-1].append(get_cell_content(c, inst, kind))
                if kind.startswith("latex") and latex_highlight_best_col_indices is not None:
                    # mark the best results
                    best_lower_indices, best_upper_indices = [], []
                    best_lower_result, best_upper_result = None, None
                    # first find the ones with the best bounds
                    for j in latex_highlight_best_col_indices:
                        execdata_j = get_result(exec_data, columns[j][0], columns[j][1], inst)
                        if execdata_j is None or "result" not in execdata_j: continue
                        res_j = execdata_j["result"]
                        if res_j[:2] not in ["≤ ", "≥ "]: continue
                        is_upper = res_j[:2] == "≤ "
                        if float(res_j[2:]) == (1.0 if is_upper else 0.0): continue
                        if is_upper and len(best_upper_indices) == 0:
                            best_upper_indices = [j]
                            best_upper_result = res_j
                        elif not is_upper and len(best_lower_indices) == 0:
                            best_lower_indices = [j]
                            best_lower_result = res_j
                        else:
                            res_best = best_upper_result if is_upper else best_lower_result
                            assert res_best[:2] ==  res_j[:2], f"Unexpected result bound type: {res_best} vs. {res_j}"
                            res_j = float(res_j[2:])
                            res_best = float(res_best[2:])
                            if is_upper and res_j < res_best:
                                best_upper_indices = [j]
                                best_upper_result = res_j
                            elif not is_upper and res_j > res_best:
                                best_lower_indices = [j]
                                best_lower_result = res_j
                            elif res_j == res_best:
                                if is_upper: best_upper_indices.append(j)
                                else: best_lower_indices.append(j)
                    # now filter to find the best runtimes
                    for indices in [best_lower_indices, best_upper_indices]:
                        best_time = None
                        best_indices = []
                        for j in indices:
                            time_j = get_cell_content(columns[j], inst, "default")
                            assert(type(time_j) == float), f"Unexpected content for time cell: {time_j}"
                            if best_time is None:
                                best_time = time_j
                                best_indices = [j]
                            elif to_latex(time_j, "time") == to_latex(best_time, "time"):
                                best_indices.append(j)
                            elif time_j < best_time:
                                best_time = time_j
                                best_indices = [j]
                        for j in best_indices:
                            cells[-1][j] = f"\\textbf{{{cells[-1][j]}}}"

            return cells

    def merge_cells_latex(cells, merge_cols):
        cols_to_remove = [r for l,r in merge_cols]
        new_cells = [cells[0]]
        for row in cells[1:]: # skip header
            row_cpy = copy.deepcopy(row)
            for l,r in merge_cols:
                lower = row_cpy[l]
                upper = row_cpy[r]
                if lower == "-": result = upper
                elif upper == "-": result = lower
                else:
                    assert r"$\ge$" in lower, f"Unexpected content for result cell: {lower}"
                    assert r"$\le$" in upper, f"Unexpected content for result cell: {upper}"
                    result = "[{},~{}]".format(lower.replace(r"$\ge$", ""), upper.replace(r"$\le$", ""))
                row_cpy[l] = result
            new_cells.append([row_cpy[i] for i in range(len(row_cpy)) if i not in cols_to_remove])
        return new_cells

    def export_data_for_kind(kind):
        # get the columns relevant for this kind
        if kind.startswith("latex"):
            if kind.startswith("latext"):
                cols = [["name"], ["num-epochs"], ["unf-states"]]
                timelimit = kind[len("latext"):]
                cfgs = [ [storm.NAME, f"{cfgbase}-best-in-{timelimit}s"] for cfgbase in storm.BASE_CONFIGS[:6] ]
                cols += [[c[0], c[1], "wallclock-time"] for c in cfgs]
                latex_cols = [r"\multicolumn{1}{c}{Model}", r"\multicolumn{1}{c}{$|\epochs|$}", r"\multicolumn{1}{c}{$|S_\mathsf{un}|$}", r"\multicolumn{2}{c}{\config{unfold}: \config{cut} / \config{discr}}", r"\multicolumn{2}{c}{\config{ca-unfold}: \config{cut} / \config{discr}}", r"\multicolumn{2}{c}{\config{ca-bel-seq}: \config{cut} / \config{discr}}"]
                latex_col_aligns = "c@{}" + "r" * (len(cols)-1)
                cells = create_cells(cols, cfgs, kind, None)
                # cells = merge_cells_latex(cells, [[5,6],[7,8],[9,10]])
            else:
                cols = [["name"], ["states"], ["choices"], ["observations"], ["dim"], ["num-epochs"]]
                latex_cols = [r"Model", r"$|S|$", r"$|Act|$", r"$|Z|$", r"$k$", r"$|\epochs|$"]
                latex_col_aligns = "crrrrr"
                cfgs = []
                cells = create_cells(cols, cfgs, kind)
            latex_header = "\n& ".join(latex_cols)
            save_latex(cells, latex_col_aligns, latex_header, os.path.join(TABLE_DIR, "{}table{}.tex".format(prefix, kind[len("latex"):])))
        else:
            cols = [["name"], ["par"], ["states"], ["choices"], ["observations"], ["property"]]
            cfgs = [ [tool.NAME, c["id"]] for tool in TOOLS  for c in tool.CONFIGS + tool.META_CONFIGS ]
            cols += [[c[0], c[1], "wallclock-time"] for c in cfgs]
            # create and export different kinds of data
            cells = create_cells(cols, cfgs, kind)
            if kind in ["default", "scatter", "quantile"]:
                save_csv(cells, os.path.join(OUT_DIR, f"{prefix}{kind}.csv"))
            elif kind == "html":
                save_html(cells, len(cfgs), os.path.join(OUT_DIR, f"{prefix}table"))
            else:
                assert False, f"Unhandled kind: {kind}"

    # invoke generation for all kinds
    if len(benchmark_instances) == 0: return
    for kind in export_kinds: export_data_for_kind(kind)
if __name__ == "__main__":
    print("Benchmarking tool.")
    print("This script gathers data of executions and exports them in various ways.")
    print("Usages:")
    print("python3 {} path/to/first/logfiles/ path/to/second/logfiles/ ...    reads from multiple log file directories '".format(sys.argv[0]))
    print("")
    if (len(sys.argv) == 2 and sys.argv[1] in ["-h", "-help", "--help"]):
        exit(1)

    logdirs = sys.argv[1:]

    print("Selected log dir(s): {}".format(", ".join(logdirs)))
    print("")

    exec_data, benchmark_instances = gather_execution_data(logdirs)
    benchmark_instances = OrderedDict(sorted(benchmark_instances.items(), key=lambda item: item[0]))
    process_meta_configs(exec_data, benchmark_instances)

    if not os.path.exists(OUT_DIR): os.makedirs(OUT_DIR)
    save_json(exec_data, os.path.join(OUT_DIR, "execution-data.json"))
    save_json(benchmark_instances, os.path.join(OUT_DIR, "benchmark-data.json"))

    print("Found Data for {} benchmarks".format(len(benchmark_instances)))

    for b_id, b_data in benchmark_instances.items():
        if "benchmark-set" not in b_data: print(b_data.keys())
    save_dissertation_tables(exec_data, benchmark_instances, storm.META_CONFIG_TIMELIMITS[0])
    save_overapproximation_table(exec_data, benchmark_instances)
    save_underapproximation_tables(exec_data, benchmark_instances)
    from export_tikzpictures import generate_plots
    generate_plots(sys.modules[__name__], exec_data, benchmark_instances, OUT_DIR)
    from html_results import save_results as save_html_results
    save_html_results(sys.modules[__name__], exec_data, benchmark_instances, logdirs)
