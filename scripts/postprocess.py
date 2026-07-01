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



def save_latex(table_data, cols, header, path):
    with open(path, 'w') as latex_file:
        latex_file.write(r"""
\renewcommand{\tabcolsep}{4.5pt}
\begin{tabular}{@{}""")
        latex_file.write(cols)
        latex_file.write(r"""@{}}

\toprule
""")
        latex_file.write(header + "\\\\ \\midrule\n")
        for row in table_data[1:]:
            latex_file.write("\t&\t".join(row) + "\\\\\n")
        latex_file.write(r""" \bottomrule
\end{tabular}
""")

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
    if "lvl-width" in execution_json["benchmark"]["model"]:
        bench_data["lvl-width"] = execution_json["benchmark"]["model"]["lvl-width"]
    if "bnd-thresholds" in execution_json["benchmark"]["model"]:
        bench_data["bnd-thresholds"] = execution_json["benchmark"]["model"]["bnd-thresholds"]
    bench_data["par"] = "_".join(bench_id.split("_")[3:])
    bench_data["property"] = execution_json["benchmark"]["property"]["type"]
    bench_data["dim"] = execution_json["benchmark"]["property"].get("num-bnd-rew-assignments", 0)
    bench_data["states"] = execution_json["input-model"]["states"]
    if execution_json["benchmark"]["model"]["type"] != "dtmc":
        bench_data["choices"] = execution_json["input-model"]["choices"]
    if execution_json["benchmark"]["model"]["type"] == "pomdp":
        bench_data["observations"] = execution_json["input-model"]["observations"]
    bench_data["transitions"] = execution_json["input-model"]["transitions"]
    if "num-epochs" in execution_json and "result" in execution_json:
        bench_data["num-epochs"] = execution_json["num-epochs"]
    if "unfolding-pomdp" in execution_json and "states" in execution_json["unfolding-pomdp"]:
        if "--reward-aware" in " ".join(execution_json["commands"]):
            bench_data["caunf-states"] = execution_json["unfolding-pomdp"]["states"]
        else:
            bench_data["unf-states"] = execution_json["unfolding-pomdp"]["states"]
    bench_data["invocations"] = [execution_json["id"]]

    # incorporate into existing data
    if not bench_id in benchmark_instances:
        benchmark_instances[bench_id] = bench_data
    else:
        # ensure consistency
        for key in ["id", "name", "formalism", "type", "par", "property", "dim", "states", "choices", "observations", "transitions", "num-epochs", "unf-states", "caunf-states"]:
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
                for cfg_id in exec_data[tool]:
                    if cfg_id in [c["id"] for c in TOOL_NAMES[tool].META_CONFIGS]: continue
                    if not cfg_id.startswith(metacfg["cfgbase"]): continue
                    if benchmark not in  exec_data[tool][cfg_id]: continue
                    data = exec_data[tool][cfg_id][benchmark]
                    if "maxtime" in metacfg and data["wallclock-time"] > metacfg["maxtime"]: continue
                    if not "result" in data: continue
                    result_str = data["result"]
                    if best_cfg_id is None:
                        best_cfg_id = cfg_id
                        continue
                    best_result_str = exec_data[tool][best_cfg_id][benchmark]["result"]
                    assert result_str[0] in ["≥", "≤"], f"Unexpected result string: {result_str}"
                    assert result_str[0] == best_result_str[0], f"inconsistent result strings: {result_str} vs. {best_result_str}"
                    result_value = float(result_str[1:])
                    best_result_value = float(best_result_str[1:])
                    if result_value == best_result_value:
                        if data["wallclock-time"] < exec_data[tool][best_cfg_id][benchmark]["wallclock-time"]:
                            best_cfg_id = cfg_id
                            continue
                    if result_str[0] == "≥" and result_value > best_result_value: best_cfg_id = cfg_id
                    elif result_str[0] == "≤" and result_value < best_result_value: best_cfg_id = cfg_id
                if best_cfg_id is not None: benchmark_data[benchmark] = copy.deepcopy(exec_data[tool][best_cfg_id][benchmark])
            exec_data[tool][metacfg["id"]] = benchmark_data

def get_result(exec_data, tool, config, inst_id):
        if tool in exec_data and config in exec_data[tool] and inst_id in exec_data[tool][config]:
            return exec_data[tool][config][inst_id]

def get_result_if_supported(exec_data, tool, config, inst_id):
        res = get_result(exec_data, tool, config, inst_id)
        if res is not None and not res["not-supported"]:
            return res


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
        elif type(value) == str and data_kind == "result" and value[:2] in ["≤ ", "≥ "]:
            v = r"$\{}$ {}".format("le" if value[0] == "≤" else "ge", to_latex(float(value[2:]), ))
            data_kind = None # do not add $ for the value
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
                if res is None or "result" not in res or res["result"] in ["≥ 0", "≤ 1"]:
                    value = r"\multicolumn{1}{c}{-}"
                else:
                    assert res["result"][:2] in ["≤ ", "≥ "]
                    asterisk = ""
                    if "--belief-exploration unfold" in res["commands"][0] and "belief-mdp-incomplete" not in res:
                        asterisk = "$^*$"
                    value = "{} ({}s){}".format(to_latex(float(res["result"][2:])), value, asterisk)
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

    def get_time_result_list_for_plot(cfgbase, inst_id):
        datalist = []
        is_increasing = False
        is_decreasing = False
        for cfg in [c for c in storm.CONFIGS if c["id"].startswith(cfgbase)]:
            res = get_result_if_supported(exec_data, storm.NAME, cfg["id"], inst_id)
            if res is not None and "result" in res:
                assert res["result"][:2] in ["≤ ", "≥ "], f"Unexpected result string: {res['result']}"
                is_increasing = is_increasing or res["result"][:2] == "≥ " # lower bounds should be increasing over time
                is_decreasing = is_decreasing or res["result"][:2] == "≤ " # upper bounds should be decreasing over time
                assert not is_increasing or not is_decreasing, f"Unexpected result string: {res['result']}"
                datalist.append((res["wallclock-time"], float(res["result"][2:])))
        datalist = sorted(datalist)
        if len(datalist) == 0: return []
        result = [(0.01, 0.0 if is_increasing else 1.0)]
        for t,r in datalist:
            prev_r = result[-1][1]
            # discard bounds that are worse than what is already known
            if is_increasing and prev_r > r: continue
            if is_decreasing and prev_r < r: continue
            result.append((t,prev_r)) # results in a 'stair' form for the plot
            result.append((t,r))
        result.append((3600, result[-1][1]))
        return result

    def create_time_result_csv():
        header = []
        column_contents = []
        cfgbases = storm.BASE_CONFIGS + getattr(storm, "REG_BASE_CONFIGS", [])
        for cfgbase, inst_id in itertools.product(cfgbases, benchmark_instances.keys()):
            header += [f"{cfgbase}.{strip_benchmark_set_prefix(inst_id)}.{postfix}" for postfix in ["time", "result"]]
            column_contents.append(get_time_result_list_for_plot(cfgbase, inst_id))

        table = [header]
        num_rows = max([len(c) for c in column_contents])
        for row_index in range(num_rows):
            row = []
            for col in column_contents:
                if row_index < len(col):
                    row += [col[row_index][0], col[row_index][1]]
                else:
                    row += ["", ""]
            table.append(row)

        save_csv(table, os.path.join(OUT_DIR, f"{prefix}time_result.csv"))
        with open(os.path.join(OUT_DIR, f"{prefix}time_result.tex"), 'w') as f:
            for inst in benchmark_instances.keys():
                f.write("\\defaulttimeresplot{{{}}}{{0.1}}{{3600}}\n".format(strip_benchmark_set_prefix(inst).replace("_", r"\_")))


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
                cells = create_cells(cols, cfgs, kind, [5,6,7,8])
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
            cols = [["name"], ["par"], ["states"], ["choices"], ["observations"], ["property"], ["dim"], ["num-epochs"], ["unf-states"], ["caunf-states"]]
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
    create_time_result_csv()


def get_lvlbnd_result_list_for_plot(cfg_id, instances, kind):
    min_kind_value = 0
    max_kind_value = 300 if kind == "lvls" else 300 # TODO
    datalist = []
    is_increasing = False
    is_decreasing = False
    for inst_id in instances:
        res = get_result_if_supported(exec_data, storm.NAME, cfg_id, inst_id)
        if res is not None and "result" in res:
            assert res["result"][:2] in ["≤ ", "≥ "], f"Unexpected result string: {res['result']}"
            is_increasing = is_increasing or res["result"][:2] == "≥ " # lower bounds should be increasing over time
            is_decreasing = is_decreasing or res["result"][:2] == "≤ " # upper bounds should be decreasing over time
            assert not is_increasing or not is_decreasing, f"Unexpected result string: {res['result']}"
            if kind == "lvls":
                kind_value = benchmark_instances[inst_id]["bnd-thresholds"][0] / benchmark_instances[inst_id]["lvl-width"][0] # TODO: only looks at first value, discard other lvl widths
            else:
                kind_value = benchmark_instances[inst_id]["bnd-thresholds"][0]
            datalist.append((kind_value, float(res["result"][2:])))
    datalist = sorted(datalist)
    if len(datalist) == 0: return []
    result = [(min_kind_value, 0.0 if is_increasing else 1.0)]
    for t,r in datalist:
        prev_r = result[-1][1]
        # discard bounds that are worse than what is already known TODO: check if this is necessary
        # if is_increasing and prev_r > r: continue
        # if is_decreasing and prev_r < r: continue
        result.append((t,prev_r)) # results in a 'stair' form for the plot TODO: check if this is what we want
        result.append((t,r))
    result.append((max_kind_value, result[-1][1]))
    result = result[1:]
    return result


def create_lvlbnd_result_csv(exec_data, instances, kind, prefix=""):
    if len(instances) == 0: return
    assert kind in ["lvls", "bnds"]
    instance_names =  set([b["name"] for b in instances.values()])
    header = []
    column_contents = []
    for cfg, inst_name in itertools.product(storm.META_CONFIGS, instance_names):
        header += [f"{cfg['id']}.{inst_name}.{postfix}" for postfix in [kind, "result"]]
        instance_subset = {b_id: b_data for b_id, b_data in instances.items() if b_data["name"] == inst_name}
        column_contents.append(get_lvlbnd_result_list_for_plot(cfg["id"], instance_subset,  kind))

    table = [header]
    num_rows = max([len(c) for c in column_contents])
    for row_index in range(num_rows):
        row = []
        for col in column_contents:
            if row_index < len(col):
                row += [col[row_index][0], col[row_index][1]]
            else:
                row += ["", ""]
        table.append(row)

    save_csv(table, os.path.join(OUT_DIR, f"{prefix}{kind}_result.csv"))
    with open(os.path.join(OUT_DIR, f"{prefix}{kind}_result.tex"), 'w') as f:
        for inst in instance_names:
            f.write(r"\begin{figure}[t]" + "\\default{}resplot{{{}}}{{0.1}}{{3600}}\\caption{{{}}}".format(kind,inst, inst.replace("_", r"\_")) + r"\end{figure}" + "\n")



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
    export_data(exec_data, get_benchmark_subset(["reg-main"]), export_kinds, prefix="reg-")
    export_data(exec_data, get_benchmark_subset(["rb-main"]), export_kinds, prefix="rb-")
    export_data(exec_data, get_benchmark_subset(["rb-lvls"]), ["html"], prefix="rb-lvls-")
    export_data(exec_data, get_benchmark_subset(["rb-bnds"]), ["html"], prefix="rb-bnds-")
    # export_data(exec_data, get_benchmark_subset(["rb-unb"]), export_kinds)
    create_lvlbnd_result_csv(exec_data,  get_benchmark_subset(["rb-lvls"]), "lvls", prefix="rb-")
    create_lvlbnd_result_csv(exec_data,  get_benchmark_subset(["rb-bnds"]), "bnds", prefix="rb-")
