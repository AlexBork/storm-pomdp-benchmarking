import os, copy, itertools, json
from collections import OrderedDict

import benchmarks

def const_def_string(inst):
    if "open-parameters" in inst["model"]:
        pars = inst["model"]["open-parameters"]
        values = [f"{p}={pars[p]}" for p in pars if not p.startswith("__lvl")]
        if len(values) != 0: return ",".join(values)

def get_command_line_args(cfg, inst = None):
    out = []
    if inst is not None:
        assert inst["model"]["formalism"] == "prism", f"Unhandled model formalism {inst['model']['formalism']} for storm."
        out.append(f"--prism {benchmarks.get_full_model_filename(inst)}")
        out.append(f"--prop {benchmarks.get_full_property_filename(inst)} {inst['property']['id']}")
        c = const_def_string(inst)
        if c is not None:
            out.append(f"-const {c}")
    out += cfg["cmd"]
    return " ".join(out)
        
NAME = "storm"
DESCRIPTION = ["storm-pomdp"]
default_executable = "$BENCH_HOME/bin/storm-pomdp"

# Configuration data
# IDs shall not have a "_" or "."
CONFIGS = []

base_cfg = OrderedDict()
base_cfg["tool"] = NAME
base_cfg["cmd"] = ["--timemem", "--statistics", "--sound"]
base_cfg["notes"] = ["Storm-pomdp"]
base_cfg["supported-obj-types"] = ["prb", "rew"]
base_cfg["supported-model-types"] = ["pomdp"]
base_cfg["supported-model-formalisms"] = ["prism"]

for i in range(2, 13):
    for mode in ["static", "dynamic"]:
        discr_cfg = copy.deepcopy(base_cfg)
        discr_cfg["id"] = f"discr{i:02}{mode[0]}"
        discr_cfg["cmd"] += ["--belief-exploration discretize", f"--resolution {i}", f"--triangulationmode {mode}"]
        discr_cfg["notes"] += [f"Over-approximation with discretization, resolution {i}, triangulation mode {mode}"]
        CONFIGS.append(discr_cfg)

for i in range(8,33):
    cutoff_cfg = copy.deepcopy(base_cfg)
    cutoff_cfg["id"] = f'cut{i:02}'
    cutoff_cfg["cmd"] += ["--belief-exploration unfold", f"--size-threshold {2**i}"]
    cutoff_cfg["notes"] += [f"Under-Approximation with cut-offs, size threshold 2^{i}"]
    CONFIGS.append(cutoff_cfg)
    for j in range(2, 7):
        clip_cfg = copy.deepcopy(base_cfg)
        clip_cfg["id"] = f"clip{i:02}res{j:02}"
        clip_cfg["cmd"] += ["--belief-exploration unfold", f"--size-threshold {2**i}", f"--use-clipping", f"--clip-resolution {j}"]
        clip_cfg["notes"] += [f"Under-Approximation with clipping, size threshold 2^{i}, clipping resolution {j}"]
        CONFIGS.append(clip_cfg)

cutoff_default_cfg = copy.deepcopy(base_cfg)
cutoff_default_cfg["id"] = f'cut00'
cutoff_default_cfg["cmd"] += ["--belief-exploration unfold", f"--size-threshold 0"]
cutoff_default_cfg["notes"] += [f"Under-Approximation with cut-offs, heuristic size threshold"]
CONFIGS.append(cutoff_default_cfg)


# Check fully observable models (not relevant)
fully_obs = copy.deepcopy(base_cfg)
fully_obs["id"] = "mdp"
fully_obs["cmd"] += ["--check-fully-observable"]
fully_obs["notes"] += ["Underlying (fully observable) observable MDP"]
CONFIGS.append(fully_obs)

# unf_fully_obs = copy.deepcopy(base_cfg)
# unf_fully_obs["id"] = "funf"
# unf_fully_obs["cmd"] += ["--check-fully-observable", "--unfold-reward-bound"]
# unf_fully_obs["notes"] += ["Unfolding approach with fully observable  MDP"]
# CONFIGS.append(unf_fully_obs)

CONFIGS = sorted(CONFIGS, key=lambda x: x["id"])
META_CONFIG_TIMELIMITS = [1800]
BASE_CONFIGS = ["discr", "cut", "clip"] #, "unbc", "unbd"]
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

    if "Exploration stopped before all beliefs were explored" in log:
        inv["belief-mdp-incomplete"] = True

    pos_bel = log.find("Constructing the belief MDP...", pos)
    if pos_bel>=0:
        pos=pos_bel
        inv["belief-mdp"] = OrderedDict()
        pos = try_parse(log, pos, "States: \t", "\n", inv["belief-mdp"], "states", int)
        pos = try_parse(log, pos, "Transitions: \t", "\n", inv["belief-mdp"], "transitions", int)
        pos = try_parse(log, pos, "Choices: \t", "\n", inv["belief-mdp"], "choices", int)
        pos = try_parse(log, pos, "Time for exploring beliefs: ", "s.", inv["belief-mdp"], "expl-time", float)
        pos = try_parse(log, pos, "Time for building the belief MDP: ", "s.", inv["belief-mdp"], "build-time", float)
        pos = try_parse(log, pos, "Time for analyzing the belief MDP: ", "s.", inv["belief-mdp"], "chk-time", float)

    pos = try_parse(log, pos, "\nResult: ", "\n", inv, "result", str)
    pos = try_parse(log, pos, "Time for POMDP analysis: ", "s.", inv, "total-chk-time", float)

    assert inv["memout"] or inv["timeout"] or ("result" in inv and "total-chk-time" in inv), "Unable to find result or total-chk-time in {}".format(inv["id"]);

if __name__ == "__main__":
    print(f"{len(CONFIGS)} config(s) for {NAME}")
    print(json.dumps(CONFIGS,indent='\t'))
