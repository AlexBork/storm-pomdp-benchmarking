import os, copy, itertools, json
from collections import OrderedDict

import benchmarks

def const_def_string(inst):
    if "open-parameters" in inst["model"]:
        pars = inst["model"]["open-parameters"]
        values = [f"{p}={pars[p]}" for p in pars if not p.startswith("__lvl")]
        if len(values) != 0: return ",".join(values)

def lvl_width_string(inst):
    if "open-parameters" in inst["model"]:
        pars = inst["model"]["open-parameters"]
        values = [f"{pars[p]}" for p in pars if p.startswith("__lvl")]
        if len(values) != 0: return ",".join(values)

def get_command_line_args(cfg, inst = None):
    out = []
    lvl_def = None
    if inst is not None:
        assert inst["model"]["formalism"] == "prism", f"Unhandled model formalism {inst['model']['formalism']} for storm."
        out.append(f"--prism {benchmarks.get_full_model_filename(inst)}")
        out.append(f"--prop {benchmarks.get_full_property_filename(inst)} {inst['property']['id']}")
        c = const_def_string(inst)
        if c is not None:
            out.append(f"-const {c}")
        lvl_def = lvl_width_string(inst)
    out += cfg["cmd"]
    if lvl_def is not None and "--reward-aware" in cfg["cmd"] and "--check-fully-observable" not in cfg["cmd"]:
        out[out.index("--reward-aware")] = f"--reward-aware {lvl_def}"
    return " ".join(out)
        
NAME = "storm"
DESCRIPTION = ["storm-pomdp"]
default_executable = "$BENCH_HOME/bin/storm-pomdp"

# Configuration data
# IDs shall not have a "_" or "."
CONFIGS = []

base_cfg = OrderedDict()
base_cfg["tool"] = NAME
base_cfg["cmd"] = ["--timemem", "--statistics"]
base_cfg["notes"] = ["Storm-pomdp"]
base_cfg["supported-obj-types"] = ["rbr"] # the default is to only support reward bounded reachability
base_cfg["supported-model-types"] = ["pomdp"]
base_cfg["supported-model-formalisms"] = ["prism"]

regular_base_cfg = copy.deepcopy(base_cfg)
regular_base_cfg["supported-obj-types"] = ["prb", "rew"]

for i in range(2, 13):
    for mode in ["static", "dynamic"]:
        reg_d_cfg = copy.deepcopy(regular_base_cfg)
        reg_d_cfg["id"] = f"regd{i:02}{mode[0]}"
        reg_d_cfg["cmd"] += ["--belief-exploration discretize", f"--resolution {i}", f"--triangulationmode {mode}"]
        reg_d_cfg["notes"] += [f"Regular over-approximation with discretization, resolution {i}, triangulation mode {mode}"]
        CONFIGS.append(reg_d_cfg)

for i in range(8,33):
    reg_c_cfg = copy.deepcopy(regular_base_cfg)
    reg_c_cfg["id"] = f'regbelseqc{i:02}'
    reg_c_cfg["cmd"] += ["--belief-exploration unfold", f"--size-threshold {2**i}"]
    reg_c_cfg["notes"] += [f"Regular sequential approach, with cutoffs and size threshold 2^{i}"]
    CONFIGS.append(reg_c_cfg)

    reg_d_cfg = copy.deepcopy(regular_base_cfg)
    reg_d_cfg["id"] = f'regbelseqd{i:02}'
    reg_d_cfg["cmd"] += ["--belief-exploration discretize", f"--resolution {i}", "--triangulationmode static"]
    reg_d_cfg["notes"] += [f"Regular sequential approach, with discretization and resolution {i}"]
    CONFIGS.append(reg_d_cfg)

    seq_c_cfg = copy.deepcopy(base_cfg) # sequential approach with cutoffs (always reward aware)
    seq_c_cfg["id"] = f'belseqc{i:02}'
    seq_c_cfg["cmd"] += ["--reward-aware", "--belief-exploration unfold", f"--size-threshold {2**i}"]
    seq_c_cfg["notes"] += [f"Sequential approach, cost aware, with cutoffs and size threshold 2^{i}"]
    CONFIGS.append(seq_c_cfg)
    unr_c_cfg = copy.deepcopy(base_cfg) # unfolding approach with cutoffs and reward awareness
    unr_c_cfg["id"] = f'caunfc{i:02}'
    unr_c_cfg["cmd"] += ["--reward-aware", "--unfold-reward-bound", "--belief-exploration unfold", f"--size-threshold {2**i}"]
    unr_c_cfg["notes"] += [f"Unfolds cost bounds, cost aware, with cutoffs and size threshold 2^{i}"]
    CONFIGS.append(unr_c_cfg)
    uns_c_cfg = copy.deepcopy(base_cfg) # unfolding approach with cutoffs and no reward awareness
    uns_c_cfg["id"] = f'unfc{i:02}'
    uns_c_cfg["cmd"] += ["--unfold-reward-bound", "--belief-exploration unfold", f"--size-threshold {2**i}"]
    uns_c_cfg["notes"] += [f"Unfolds cost bounds, not cost-aware, with cutoffs and size threshold 2^{i}"]
    CONFIGS.append(uns_c_cfg)
    unb_c_cfg = copy.deepcopy(base_cfg) # discarding reward bounds, with cutoffs and no reward awareness
    unb_c_cfg["id"] = f'unbc{i:02}'
    unb_c_cfg["supported-obj-types"] = ["unr"] # only apply this config for unbounded reachability
    unb_c_cfg["cmd"] += ["--belief-exploration unfold", f"--size-threshold {2**i}"]
    unb_c_cfg["notes"] += [f"Discards the reward bounds, not cost-aware, with cutoffs and size threshold 2^{i}"]
    # CONFIGS.append(unb_c_cfg)

for i in sorted(set([i*j for i,j in itertools.product([1,2,3,4,5,6,7],[1,2,3,4,5,6,7])])):
    seq_d_cfg = copy.deepcopy(base_cfg)
    seq_d_cfg["id"] = f'belseqd{i:02}'
    seq_d_cfg["cmd"] += ["--reward-aware", "--belief-exploration discretize", f"--resolution {i}", "--triangulationmode static"]
    seq_d_cfg["notes"] += [f"Sequential approach, cost aware, with discretization and resolution {i}"]
    CONFIGS.append(seq_d_cfg)
    unr_d_cfg = copy.deepcopy(base_cfg)
    unr_d_cfg["id"] = f'caunfd{i:02}'
    unr_d_cfg["cmd"] += ["--reward-aware", "--unfold-reward-bound", "--belief-exploration discretize", f"--resolution {i}", "--triangulationmode static"]
    unr_d_cfg["notes"] += [f"Unfolds cost bounds, cost aware, with discretization and resolution {i}"]
    CONFIGS.append(unr_d_cfg)
    uns_d_cfg = copy.deepcopy(base_cfg)
    uns_d_cfg["id"] = f'unfd{i:02}'
    uns_d_cfg["cmd"] += ["--unfold-reward-bound", "--belief-exploration discretize", f"--resolution {i}", "--triangulationmode static"]
    uns_d_cfg["notes"] += [f"Unfolds cost bounds, not cost aware, with discretization and resolution {i}"]
    CONFIGS.append(uns_d_cfg)
    unb_d_cfg = copy.deepcopy(base_cfg)
    unb_d_cfg["id"] = f'unbd{i:02}'
    unb_d_cfg["supported-obj-types"] = ["unr"] # only apply this config for unbounded reachability
    unb_d_cfg["cmd"] += ["--belief-exploration discretize", f"--resolution {i}", "--triangulationmode static"]
    unb_d_cfg["notes"] += [f"Discards the reward bounds, not cost-aware, with discretization and resolution {i}"]
    # CONFIGS.append(unb_d_cfg)

# Check fully observable models (not relevant)
seq_fully_obs = copy.deepcopy(base_cfg)
seq_fully_obs["id"] = "mdpseq"
seq_fully_obs["cmd"] += ["--check-fully-observable", "--reward-aware"]
seq_fully_obs["notes"] += ["Sequential approach on the underlying (fully observable) observable MDP"]
CONFIGS.append(seq_fully_obs)

# unf_fully_obs = copy.deepcopy(base_cfg)
# unf_fully_obs["id"] = "funf"
# unf_fully_obs["cmd"] += ["--check-fully-observable", "--unfold-reward-bound"]
# unf_fully_obs["notes"] += ["Unfolding approach with fully observable  MDP"]
# CONFIGS.append(unf_fully_obs)

CONFIGS = sorted(CONFIGS, key=lambda x: x["id"])

META_CONFIG_TIMELIMITS = [1800]
BASE_CONFIGS = ["unfc", "unfd", "caunfc", "caunfd", "belseqc", "belseqd"] #, "unbc", "unbd"]
REG_BASE_CONFIGS = ["regd", "regbelseqc", "regbelseqd"]
META_CONFIGS = []
for timelimit in META_CONFIG_TIMELIMITS:
    for cfgbase in BASE_CONFIGS:
        metacfg = OrderedDict()
        metacfg["id"] = f"{cfgbase}-best-in-{timelimit}s"
        metacfg["cfgbase"] = cfgbase
        metacfg["maxtime"] = timelimit
        META_CONFIGS.append(metacfg)

def config_from_id(identifier):
    for c in CONFIGS + META_CONFIGS:
        if c["id"] == identifier: return c
    assert False, f"Configuration identifier {identifier} is not known for {NAME}."
    
# LOGFILE Parsing
def contains_any_of(log, msg): 
    for m in msg:
        if m in log: return True
    return False

def try_parse(log, start, before, after, out_dict, out_key, out_type):
    pos1 = log.find(before, start)
    if pos1 >= 0:
        pos1 += len(before)
        pos2 = log.find(after, pos1)
        if pos2 >= 0:
            out_dict[out_key] = out_type(log[pos1:pos2])
            return pos2 + len(after)
    return start

def parse_logfile(log, inv):
    unsupported_messages = [] # add messages that indicate that the invocation is not supported
    inv["not-supported"] = contains_any_of(log, unsupported_messages)
    memout_messages = [] # add messages that indicate that the invocation is not supported
    memout_messages.append("An unexpected exception occurred and caused Storm to terminate. The message of this exception is: std::bad_alloc")
    memout_messages.append("Return code:\t-9")
    inv["memout"] = contains_any_of(log, memout_messages)
    known_error_messages = [] # add messages that indicate a "known" error, i.e., something that indicates that no warning should be printed
    inv["expected-error"] = contains_any_of(log, known_error_messages)
    if inv["not-supported"] or inv["expected-error"]: return
    if len(inv["return-codes"]) != 1 or inv["return-codes"][0] != 0:
        if not inv["timeout"] and not inv["memout"]: print("WARN: Unexpected return code(s): {} in {}".format(inv["return-codes"], inv["id"]))

    pos = try_parse(log, 0, "Time for model construction: ", "s.", inv, "model-building-time", float)
    if pos == 0: 
        assert inv["timeout"] or inv["memout"], "WARN: unable to get model construction time for {}".format(inv["id"])
        return
    inv["input-model"] = OrderedDict()
    pos = try_parse(log, pos, "States: \t", "\n", inv["input-model"], "states", int)
    pos = try_parse(log, pos, "Transitions: \t", "\n", inv["input-model"], "transitions", int)
    pos = try_parse(log, pos, "Choices: \t", "\n", inv["input-model"], "choices", int)
    pos = try_parse(log, pos, "Observations: \t", "\n", inv["input-model"], "observations", int)

    pos = log.find("Analyzing property ", pos)
    if pos < 0:
        assert inv["memout"] or inv["timeout"], "Unable to find query output in {}".format(inv["id"])
        return

    if "Analyzing property 'Pmax=? [F true]'" in log: # todo this is to catch the trivial case
        inv["result"] = "≥1.0"
        inv["total-chk-time"] = "0.0"

    posUnf = log.find("Perform explicit unfolding of reward bounds.", pos)
    if posUnf >= 0:
        pos = posUnf
        inv["unfolding-pomdp"] = OrderedDict()
        pos = try_parse(log, pos, "States: \t", "\n", inv["unfolding-pomdp"], "states", int)
        pos = try_parse(log, pos, "Transitions: \t", "\n", inv["unfolding-pomdp"], "transitions", int)
        pos = try_parse(log, pos, "Choices: \t", "\n", inv["unfolding-pomdp"], "choices", int)
        pos = try_parse(log, pos, "Observations: \t", "\n", inv["unfolding-pomdp"], "observations", int)

    if "Exploration stopped before all beliefs were explored" in log:
        inv["belief-mdp-incomplete"] = True

    posBel = log.find("Constructing the belief MDP...", pos)
    if posBel>=0:
        pos=posBel
        inv["belief-mdp"] = OrderedDict()
        pos = try_parse(log, pos, "States: \t", "\n", inv["belief-mdp"], "states", int)
        pos = try_parse(log, pos, "Transitions: \t", "\n", inv["belief-mdp"], "transitions", int)
        pos = try_parse(log, pos, "Choices: \t", "\n", inv["belief-mdp"], "choices", int)
        pos = try_parse(log, pos, "Time for exploring beliefs: ", "s.", inv["belief-mdp"], "expl-time", float)
        pos = try_parse(log, pos, "Time for building the belief MDP: ", "s.", inv["belief-mdp"], "build-time", float)
        pos = try_parse(log, pos, "Time for analyzing the belief MDP: ", "s.", inv["belief-mdp"], "chk-time", float)

    # intentionally, this is now only parsed if the belief MDP is *not* constructed.
    # this is because the belief MDP might be incomplete and thus the reported number of checked epochs might be lower
    pos = try_parse(log, pos, "#checked epochs: ", ".\n", inv, "num-epochs", int)

    pos = try_parse(log, pos, "\nResult: ", "\n", inv, "result", str)
    pos = try_parse(log, pos, "Time for POMDP analysis: ", "s.", inv, "total-chk-time", float)

    assert inv["memout"] or inv["timeout"] or ("result" in inv and "total-chk-time" in inv), "Unable to find result or total-chk-time in {}".format(inv["id"]);

if __name__ == "__main__":
    print(f"{len(CONFIGS)} config(s) for {NAME}")
    print(json.dumps(CONFIGS,indent='\t'))
