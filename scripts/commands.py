import os, copy, itertools, json, copy
from collections import OrderedDict
from datetime import date

import benchmarks
import tools
from input import *
from executing import *

def check_execution(command):
    command_repl = replace_placeholders_in_cmd_string(command)
    print(f"\tTesting execution of {command_repl} ... ", end="")
    try:
        test_out, test_time, test_code = execute_command_line(command_repl, 10)
        if test_code == 0:
            print("success!")
            return True
        else:
            print(f"WARN: Non-zero return code '{test_code}'. Output:\n{'-'*80}\n{test_out}{'-'*80}")
    except KeyboardInterrupt:
        print("Aborted.")
    except Exception as e:
        print(f"WARN: unable to execute:\n\t\t{e}")
    return ask_user_yn("Continue?")

def is_supported(inst, cfg):
    if inst["model"]["formalism"] not in cfg["supported-model-formalisms"]: return False
    if inst["model"]["type"] not in cfg["supported-model-types"]: return False
    if inst["property"]["type"] not in cfg["supported-obj-types"]: return False
    return True

def get_invocation_id(inst, cfg):
    return f"{cfg['tool']}.{cfg['id']}.{inst['id']}"

    
def get_command_lines(tool_binaries, cfg, inst = None):
    return [f"{tool_binaries[cfg['tool']]} {tools.get_command_line_args(cfg, inst)}"]
    
def create_invocations():
    tool_options = OrderedDict([[t.NAME, t.DESCRIPTION] for t in tools.TOOLS])
    tool_selection = input_selection("Tools", tool_options)
    tool_configs = []
    tool_binaries = dict()
    cfgs = []
    for t in tool_selection:
        tool_binaries[t] = ask_user_for_info(f"Enter path to {t} binary:", tools.TOOL_NAMES[t].default_executable, check_execution)
        tool_configs += tools.TOOL_NAMES[t].CONFIGS

    cfg_options = OrderedDict([[c["id"], c["notes"]] for c in tool_configs])
    cfg_selection = input_selection("Tool Configurations", cfg_options)
    cfgs = [c for c in tool_configs if c["id"] in cfg_selection]
    print(f"Selected {len(cfgs)} Tool configurations.")
    for cfg in cfgs:
        for cmd in get_command_lines(tool_binaries, cfg):
            if not check_execution(cmd): exit(-1)

    bset_selection = input_selection("Benchmark Sets", benchmarks.BENCHMARK_SETS)
    invocations = [OrderedDict(id=get_invocation_id(inst,cfg), instance=inst, configuration=cfg) for inst,cfg in itertools.product(benchmarks.INSTANCES, cfgs) if is_supported(inst, cfg) and inst["benchmark-set"] in bset_selection]
    print(f"Selected {len(invocations)} invocations.")

    time_limit = int(ask_user_for_info(f"Enter a time limit (in seconds):", "1800", lambda usr_in : usr_in.isdigit()))
    log_dir = ask_user_for_info(f"Enter a logfile directory ", f"logs{date.today()}")
    if not os.path.exists(log_dir): os.makedirs(log_dir)
    inv_name = ask_user_for_info(f"Enter a file for storing the invocation information ", f"inv{date.today()}.json", ask_user_overwrite_file)
    print(f"Storing information for {len(invocations)} invocations ... ", end="")
    invocations_json = []
    for inv in invocations:
        inv_json = OrderedDict()
        inv_json["id"] = inv["id"]
        inv_json["benchmark-id"] = inv["instance"]["id"]
        inv_json["tool"] = inv["configuration"]["tool"]
        inv_json["configuration-id"] = inv["configuration"]["id"]
        inv_json["invocation-note"] = ". ".join(inv["configuration"]["notes"])        
        inv_json["commands"] = get_command_lines(tool_binaries, inv["configuration"], inv["instance"])
        inv_json["time-limit"] = time_limit
        inv_json["log-dir"] = log_dir
        inv_json["log"] = f"{inv['id']}.log"
        invocations_json.append(inv_json)
    with open(inv_name, 'w') as json_file:
        json.dump(invocations_json, json_file, ensure_ascii=False, indent='\t')
    print("done.")
    

    
    
