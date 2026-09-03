import sys, os, json, csv, copy, math, re, itertools, html

from collections import Counter, OrderedDict
import benchmarks
from tools import *

OUT_DIR = "data"

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
                    style_classes = dict(TO="timeout", ERR="error", INC="incorrect", MO="memout", NS="unsupported")
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



def save_latex(table_data, cols, header, path, grid=False):
    with open(path, 'w') as latex_file:
        latex_file.write(r"""
\renewcommand{\tabcolsep}{4.5pt}
\begin{tabular}{@{}""")
        latex_file.write(cols)
        latex_file.write("@{}}\n\n")
        latex_file.write("\\hline\n" if grid else "\\toprule\n")
        latex_file.write(header + ("\\\\ \\hline\n" if grid else "\\\\ \\midrule\n"))
        for row in table_data[1:]:
            latex_file.write("\t&\t".join(row) + ("\\\\ \\hline\n" if grid else "\\\\\n"))
        if not grid:
            latex_file.write(" \\bottomrule\n")
        latex_file.write("\\end{tabular}\n")

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
    if any(data.get(key, False) for key in ["timeout", "memout", "execution-error", "expected-error", "not-supported"]):
        return False
    return maxtime is None or data["wallclock-time"] <= maxtime

def expected_bound_relation(cfgbase, benchmark):
    direction = benchmark["property"]["dir"]
    if cfgbase in ["cut", "clip"]: # under-approximation
        return "≥" if direction == "max" else "≤"
    if cfgbase == "discr": # over-approximation
        return "≤" if direction == "max" else "≥"
    return None

def result_selection_score(data, expected_relation):
    relation, result = parse_result_value(data["result"])
    if relation == "=":
        # Every exact result is preferable to a bound. Exact results for one
        # benchmark are expected to agree, so use runtime as the tie-breaker.
        return (1, 0, -data["wallclock-time"])
    if expected_relation is not None and relation != expected_relation:
        raise ValueError(f"Expected a '{expected_relation}' bound, got '{data['result']}'")
    quality = result if relation == "≥" else -result
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

    # modify logfile
    NOTES_HEADING = "\n" + "#"*30 + " Notes " + "#"*30 + "\n"
    posEnd = log.find(NOTES_HEADING)
    if posEnd >= 0: log = log[:posEnd]
    if len(execution_json["notes"]) > 0: log += NOTES_HEADING + "\n".join(execution_json["notes"]) + "\n"
    with open(execution_json["log"], 'w') as logfile:
        logfile.write(log)

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

    for logdir_input in logdirs:
        logdir = os.path.expanduser(logdir_input)
        if not os.path.isdir(logdir):
            print("Error: Directory '{}' does not exist.".format(logdir))

        print("\nGathering execution data for logfiles in {} ...".format(logdir))
        json_files = [ f for f in os.listdir(logdir) if f.endswith(".json") and os.path.isfile(os.path.join(logdir, f)) ]
        i = 0
        for execution_json in [ load_json(os.path.join(logdir, f)) for f in json_files ]:
            benchmark = execution_json["benchmark-id"]
            if benchmarks.from_id(benchmark) is None:
                print(f"WARN: Ignoring data for unknown benchmark {benchmark}")
                continue
            i += 1
            tool = execution_json["tool"]
            config = execution_json["configuration-id"]
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
            process_benchmark_instance_data(benchmark_instances, execution_json)

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
        for metacfg in TOOL_NAMES[tool].META_CONFIGS:
            benchmark_data = OrderedDict()
            for benchmark in benchmark_instances:
                best_cfg_id = None
                expected_relation = expected_bound_relation(metacfg["cfgbase"], benchmarks.from_id(benchmark))
                for cfg_id in exec_data[tool]:
                    if cfg_id in [c["id"] for c in TOOL_NAMES[tool].META_CONFIGS]: continue
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

def latex_number(value):
    value = float(value)
    formatted = f"{value:.3g}"
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))[eE]([+-]?\d+)", formatted)
    if match is not None:
        return r"{}{{\cdot}}10^{{{}}}".format(match.group(1), int(match.group(2)))
    return formatted

def latex_result(result, bold=False):
    relation, value = parse_result_value(result)
    relation_latex = {"=": "", "≤": r"\le ", "≥": r"\ge "}[relation]
    value_latex = latex_number(value)
    if bold:
        value_latex = rf"\mathbf{{{value_latex}}}"
    return f"${relation_latex}{value_latex}$"

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
            threshold = r"\mathrm{heur.}" if match.group(1) == "00" else f"2^{{{int(match.group(1))}}}"
            return f"$c={threshold}$"
    elif cfgbase == "clip":
        match = re.fullmatch(r"clip(\d{2})res(\d{2})", cfg_id)
        if match is not None:
            threshold = r"\mathrm{heur.}" if match.group(1) == "00" else f"2^{{{int(match.group(1))}}}"
            return fr"$c={threshold},\resolution={int(match.group(2))}$"
    elif cfgbase == "discr":
        match = re.fullmatch(r"discr(\d{3})([sd])", cfg_id)
        if match is not None:
            mode = r"\mathrm{static}" if match.group(2) == "s" else r"\mathrm{dyn.}"
            return fr"$\resolution={int(match.group(1))},\ {mode}$"
    return cfg_id.replace("_", r"\_")

def unavailable_result_cell(exec_data, config_ids, inst_id):
    runs = [get_result(exec_data, storm.NAME, cfg_id, inst_id) for cfg_id in config_ids]
    runs = [run for run in runs if run is not None]
    if len(runs) == 0:
        return "--"

    resource_limit_statuses = []
    if any(run.get("timeout", False) for run in runs):
        resource_limit_statuses.append("TO")
    if any(run.get("memout", False) for run in runs):
        resource_limit_statuses.append("MO")
    if len(resource_limit_statuses) > 0:
        return " / ".join(resource_limit_statuses)

    statuses = []
    if any(run.get("execution-error", False) or run.get("expected-error", False) or
           (not run.get("timeout", False) and not run.get("memout", False) and "result" not in run)
           for run in runs):
        statuses.append("ERR")
    return " / ".join(statuses) if len(statuses) > 0 else "ERR"

def is_resource_limit_status(status):
    return len(status.split(" / ")) > 0 and all(
        item in ["TO", "MO"] for item in status.split(" / ")
    )

def resource_limit_cell(status):
    return r"\shortstack[c]{{{}}}".format(status)

def dissertation_cell(result, runtime=None, parameter=None, highlight=False):
    if runtime is None and parameter is None and is_resource_limit_status(result):
        return resource_limit_cell(result)
    runtime_line = "--" if runtime is None else f"{latex_time(runtime)}s"
    parameter_line = "--" if parameter is None else parameter
    cell = r"\shortstack[r]{{{}\\{}\\{}}}".format(result, runtime_line, parameter_line)
    return (r"\cellcolor{RWTHblue25}" if highlight else "") + cell

def dissertation_result_cell(exec_data, inst_id, cfgbase, timelimit, highlight=False):
    metacfg_id = f"{cfgbase}-best-in-{timelimit}s"
    result = get_result(exec_data, storm.NAME, metacfg_id, inst_id)
    if result is None:
        config_ids = [cfg["id"] for cfg in storm.CONFIGS if cfg["id"].startswith(cfgbase)]
        return dissertation_cell(unavailable_result_cell(exec_data, config_ids, inst_id))
    parameter = latex_configuration_parameter(cfgbase, result["configuration-id"])
    return dissertation_cell(
        latex_result(result["result"], highlight),
        result["wallclock-time"],
        parameter,
        highlight,
    )

def dissertation_property(instance):
    property_symbol = "P" if instance["property"] == "prb" else "R"
    base_id = instance["property"] + instance["property-dir"]
    qualifier = instance["property-id"][len(base_id):]
    qualifier_latex = "" if qualifier == "" else rf"^{{\mathrm{{{qualifier}}}}}"
    return rf"${property_symbol}_\mathrm{{{instance['property-dir']}}}{qualifier_latex}$"

def dissertation_parameters(instance):
    crypt_sizes = {"crypt": "2", "crypt4": "4", "crypt6": "6"}
    if instance["benchmark-set"] in crypt_sizes:
        return crypt_sizes[instance["benchmark-set"]]
    return instance["par"].replace("_", r"\_")

def dissertation_model(instance, finite_belief_mdp=False):
    model = f"\\model{{{instance['name']}}}"
    if finite_belief_mdp:
        model += "$^*$"
    parameters = dissertation_parameters(instance)
    return model if parameters == "" else rf"\shortstack{{{model}\\{parameters}}}"

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

def save_dissertation_tables(exec_data, benchmark_instances, timelimit=1800):
    benchmark_headers = [
        "Model",
        r"$|S|$",
        r"$|Act|$",
        r"$|Z|$",
    ]
    result_headers = [
        "Model",
        "Property",
        r"Cut-Off ($c$)",
        r"Clipping ($c,\resolution$)",
        r"Discretisation ($\resolution$)",
        "MDP",
    ]

    benchmark_rows = [[]]
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
        benchmark_rows.append([
            dissertation_model(instance, model_identity in finite_models),
            str(instance["states"]),
            str(instance["choices"]),
            str(instance["observations"]),
        ])
    save_latex(benchmark_rows, "|c|r|r|r|", "\n& ".join(benchmark_headers), os.path.join(OUT_DIR, "tablebenchmarks.tex"), grid=True)

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
                    latex_result(mdp["result"], mdp_highlighted),
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
                dissertation_result_cell(exec_data, inst_id, "discr", timelimit, discr_id in overapproximation_highlights),
                mdp_cell,
            ])
        save_latex(rows, "|c|c|r|r|r|r|", "\n& ".join(result_headers), os.path.join(OUT_DIR, filename), grid=True)

def dissertation_value_cell(exec_data, inst_id, config_id, bold=False, configuration=None):
    result = get_result(exec_data, storm.NAME, config_id, inst_id)
    belief_states = "--"
    if result is not None and "belief-mdp" in result and "states" in result["belief-mdp"]:
        belief_states = rf"$|S|={result['belief-mdp']['states']}$"
    if is_successful_result(result):
        lines = [latex_result(result["result"], bold), f"{latex_time(result['wallclock-time'])}s", belief_states]
        if configuration is not None:
            lines.append(configuration)
        return r"\shortstack[r]{{{}}}".format(r"\\".join(lines))
    status = unavailable_result_cell(exec_data, [config_id], inst_id)
    if is_resource_limit_status(status):
        return resource_limit_cell(status)
    lines = [status, "--", belief_states]
    if configuration is not None:
        lines.append(configuration)
    return r"\shortstack[r]{{{}}}".format(r"\\".join(lines))

def best_approximation_configs(exec_data, inst_id, config_ids, direction, approximation="over", maxtime=None):
    candidates = {}
    for config_id in config_ids:
        result = get_result(exec_data, storm.NAME, config_id, inst_id)
        if is_successful_result(result, maxtime):
            _, value = parse_result_value(result["result"])
            candidates[config_id] = (float(f"{value:.3g}"), result["wallclock-time"])
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

def save_overapproximation_table(exec_data, benchmark_instances):
    shown_resolutions = [4, 7, 12]
    all_resolutions = list(range(2, 13))
    first_header = "\n& ".join(
        ["Model", "Property"] +
        [rf"\multicolumn{{2}}{{c|}}{{$\resolution={resolution}$}}" for resolution in shown_resolutions] +
        ["Best discr.", "MDP"]
    )
    second_header = "\n& ".join(
        ["", ""] +
        [mode for _ in shown_resolutions for mode in ["static", "dyn."]] +
        ["", ""]
    )
    header = first_header + r"\\ \hline" + "\n" + second_header

    column_spec = "|c|c|" + "r|" * (2 * len(shown_resolutions) + 2)
    objective_tables = [
        ("prb", "min", "tableoverapproxprbmin.tex"),
        ("prb", "max", "tableoverapproxprbmax.tex"),
        ("rew", "min", "tableoverapproxrewmin.tex"),
        ("rew", "max", "tableoverapproxrewmax.tex"),
    ]
    for property_type, direction, filename in objective_tables:
        rows = [[]]
        for benchmark in benchmarks.INSTANCES:
            if benchmark["property"]["type"] != property_type or benchmark["property"]["dir"] != direction:
                continue
            inst_id = benchmark["id"]
            if inst_id not in benchmark_instances:
                continue
            instance = benchmark_instances[inst_id]
            all_discretization_ids = [
                f"discr{resolution:03}{mode}"
                for resolution in all_resolutions for mode in ["s", "d"]
            ]
            best_discretization_ids = best_approximation_configs(
                exec_data, inst_id, all_discretization_ids, instance["property-dir"]
            )
            best_discretization_id = next(
                config_id for config_id in all_discretization_ids
                if config_id in best_discretization_ids
            )
            highlighted_ids = best_approximation_configs(
                exec_data, inst_id, [best_discretization_id, "mdp"], instance["property-dir"]
            )
            row = [dissertation_model(instance), dissertation_property(instance)]
            for resolution in shown_resolutions:
                row += [
                    dissertation_value_cell(exec_data, inst_id, f"discr{resolution:03}s"),
                    dissertation_value_cell(exec_data, inst_id, f"discr{resolution:03}d"),
                ]
            row += [
                dissertation_value_cell(
                    exec_data,
                    inst_id,
                    best_discretization_id,
                    best_discretization_id in highlighted_ids,
                    latex_configuration_parameter("discr", best_discretization_id),
                ),
                dissertation_value_cell(exec_data, inst_id, "mdp", "mdp" in highlighted_ids),
            ]
            rows.append(row)
        save_latex(rows, column_spec, header, os.path.join(OUT_DIR, filename), grid=True)


def underapproximation_value_cell(exec_data, inst_id, config_id, bold=False):
    result = get_result(exec_data, storm.NAME, config_id, inst_id)
    belief_states = "--"
    if result is not None and "belief-mdp" in result and "states" in result["belief-mdp"]:
        belief_states = rf"$|S|={result['belief-mdp']['states']}$"
    if is_successful_result(result):
        return r"\shortstack[r]{{{}\\{}s\\{}}}".format(
            latex_result(result["result"], bold),
            latex_time(result["wallclock-time"]),
            belief_states,
        )
    status = unavailable_result_cell(exec_data, [config_id], inst_id)
    if is_resource_limit_status(status):
        return resource_limit_cell(status)
    return r"\shortstack[r]{{{}\\--\\{}}}".format(
        status,
        belief_states,
    )


def underapproximation_rows(exec_data, benchmark_instances, property_type, direction, config_ids):
    rows = [[]]
    for benchmark in benchmarks.INSTANCES:
        if benchmark["property"]["type"] != property_type or benchmark["property"]["dir"] != direction:
            continue
        inst_id = benchmark["id"]
        if inst_id not in benchmark_instances:
            continue
        best_ids = best_approximation_configs(
            exec_data, inst_id, config_ids, direction, approximation="under"
        )
        rows.append([
            dissertation_model(benchmark_instances[inst_id]),
            dissertation_property(benchmark_instances[inst_id]),
        ] + [
            underapproximation_value_cell(exec_data, inst_id, config_id, config_id in best_ids)
            for config_id in config_ids
        ])
    return rows


def save_underapproximation_tables(exec_data, benchmark_instances):
    objective_tables = [
        ("prb", "min", "prbmin"),
        ("prb", "max", "prbmax"),
        ("rew", "min", "rewmin"),
        ("rew", "max", "rewmax"),
    ]

    cutoff_exponents = [0] + list(range(8, 33))
    cutoff_ids = [f"cut{exponent:02}" for exponent in cutoff_exponents]
    cutoff_headers = [
        r"$c=\mathrm{heur.}$" if exponent == 0 else rf"$c=2^{{{exponent}}}$"
        for exponent in cutoff_exponents
    ]
    cutoff_header = "\n& ".join(["Model", "Property"] + cutoff_headers)
    cutoff_column_spec = "|c|c|" + "r|" * len(cutoff_ids)

    clipping_thresholds = [0, 8, 12, 16]
    clipping_resolutions = list(range(2, 6))
    clipping_ids = [
        f"clip{threshold:02}res{resolution:02}"
        for threshold in clipping_thresholds
        for resolution in clipping_resolutions
    ]
    clipping_first_header = "\n& ".join(
        ["Model", "Property"] + [
            rf"\multicolumn{{{len(clipping_resolutions)}}}{{c|}}{{{r'$c=\mathrm{heur.}$' if threshold == 0 else rf'$c=2^{{{threshold}}}$'}}}"
            for threshold in clipping_thresholds
        ]
    )
    clipping_second_header = "\n& ".join(
        ["", ""] + [
            rf"$\resolution={resolution}$"
            for _ in clipping_thresholds
            for resolution in clipping_resolutions
        ]
    )
    clipping_header = clipping_first_header + r"\\ \hline" + "\n" + clipping_second_header
    clipping_column_spec = "|c|c|" + "r|" * len(clipping_ids)

    for property_type, direction, filename_suffix in objective_tables:
        save_latex(
            underapproximation_rows(
                exec_data, benchmark_instances, property_type, direction, cutoff_ids
            ),
            cutoff_column_spec,
            cutoff_header,
            os.path.join(OUT_DIR, f"tablecut{filename_suffix}.tex"),
            grid=True,
        )
        save_latex(
            underapproximation_rows(
                exec_data, benchmark_instances, property_type, direction, clipping_ids
            ),
            clipping_column_spec,
            clipping_header,
            os.path.join(OUT_DIR, f"tableclip{filename_suffix}.tex"),
            grid=True,
        )


def time_result_plot_series(exec_data, inst_id, cfgbase, start_time=0.01, end_time=3600):
    benchmark = benchmarks.from_id(inst_id)
    expected_relation = expected_bound_relation(cfgbase, benchmark)
    increasing = expected_relation == "≥"
    data = []
    for config in storm.CONFIGS:
        if not config["id"].startswith(cfgbase):
            continue
        result = get_result(exec_data, storm.NAME, config["id"], inst_id)
        if not is_successful_result(result):
            continue
        relation, value = parse_result_value(result["result"])
        if relation not in ["=", expected_relation]:
            raise ValueError(
                f"Expected a '{expected_relation}' bound, got '{result['result']}' in {result['id']}"
            )
        data.append((result["wallclock-time"], value))

    data.sort()
    if len(data) == 0:
        return []

    if benchmark["property"]["type"] == "prb":
        # Probability objectives have a trivial bound that is available before
        # any configuration finishes.
        initial_value = 0.0 if increasing else 1.0
        series = [(start_time, initial_value)]
        remaining_data = data
    else:
        # Do not make the first reward bound appear available before the run
        # that computed it has finished.
        first_runtime, first_value = data[0]
        series = [(first_runtime, first_value)]
        remaining_data = data[1:]

    for runtime, value in remaining_data:
        previous_value = series[-1][1]
        if increasing and previous_value >= value:
            continue
        if not increasing and previous_value <= value:
            continue
        # Keep the incumbent result until the improving run finishes, then
        # change vertically to the newly available result.
        series.append((runtime, previous_value))
        series.append((runtime, value))
    series.append((end_time, series[-1][1]))
    return series


def save_time_result_csv(exec_data, benchmark_instances):
    header = []
    series_contents = []
    for cfgbase in ["cut", "clip", "discr"]:
        for benchmark in benchmarks.INSTANCES:
            inst_id = benchmark["id"]
            if inst_id not in benchmark_instances:
                continue
            series_name = f"{cfgbase}.{inst_id}"
            header.extend([f"{series_name}.time", f"{series_name}.result"])
            series_contents.append(time_result_plot_series(exec_data, inst_id, cfgbase))

    table = [header]
    num_rows = max((len(series) for series in series_contents), default=0)
    for row_index in range(num_rows):
        row = []
        for series in series_contents:
            row.extend(series[row_index] if row_index < len(series) else ["", ""])
        table.append(row)
    save_csv(table, os.path.join(OUT_DIR, "time_result.csv"))

    with open(os.path.join(OUT_DIR, "time_result_plots.tex"), "w") as plot_file:
        plot_file.write("% Generated by scripts/postprocess.py.\n")
        plot_count = 0
        for benchmark in benchmarks.INSTANCES:
            inst_id = benchmark["id"]
            if inst_id not in benchmark_instances:
                continue
            if plot_count > 0 and plot_count % 9 == 0:
                plot_file.write("\\clearpage\n")
            command = (
                "\\defaulttimeresplot" if benchmark["property"]["type"] == "prb"
                else "\\defaulttimeresplotauto"
            )
            plot_count += 1
            plot_file.write(f"{command}{{{inst_id}}}{{0.01}}{{3600}}%\n")
            plot_file.write("\\par\\medskip\n" if plot_count % 3 == 0 else "\\hfill\n")


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
            v = f"\\model{{{value}}}"
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
            elif res["expected-error"]:
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
            save_latex(cells, latex_col_aligns, latex_header, os.path.join(OUT_DIR, "{}table{}.tex".format(prefix, kind[len("latex"):])))
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
    def get_benchmark_subset(subset):
        return {b_id: b_data for b_id, b_data in benchmark_instances.items() if b_data["benchmark-set"] in subset}


    export_kinds = ["default", "scatter", "quantile", "html", "latexbenchmarks"] + [f"latext{t}" for t in storm.META_CONFIG_TIMELIMITS]
    #export_data(exec_data, get_benchmark_subset(["drone"]), export_kinds, prefix="drone-")
    #export_data(exec_data, get_benchmark_subset(["network2"]), export_kinds, prefix="netw2-")
    #export_data(exec_data, get_benchmark_subset(["network-priorities2"]), export_kinds, prefix="netwp2-")
    save_dissertation_tables(exec_data, benchmark_instances, storm.META_CONFIG_TIMELIMITS[0])
    save_overapproximation_table(exec_data, benchmark_instances)
    save_underapproximation_tables(exec_data, benchmark_instances)
    save_time_result_csv(exec_data, benchmark_instances)
