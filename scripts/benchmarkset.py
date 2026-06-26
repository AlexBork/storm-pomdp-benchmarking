from collections import OrderedDict

import itertools

def create_property_info(identifier : str,  file_name : str):
    """
    Creates a dictionary with the information of a property.
    @param identifier: The identifier of the property. The first three letters yield the type of the property.
                        The next three letters encode the optimization direction (min or max)
                        If the seventh character is numeric, it encodes the number of different reward assignments involved in reward bounds
    @param file_name: The name of the file containing the property
    """
    assert len(identifier) >= 3, f"Invalid identifier for property: {identifier}"
    info = OrderedDict()
    info["id"] = identifier
    info["file"] = file_name
    info["type"] = identifier[:3]
    info["dir"] = identifier[3:6]
    assert info["dir"] in ["min", "max"], f"Unknown optimization direction for property {info['dir']}"
    if len(identifier) >= 7 and identifier[6].isnumeric():
        assert info["type"] in ["rbr"], f"Unknown extra information for property type {info['type']}"
        info["num-bnd-rew-assignments"] = int(identifier[6])
    else:
        assert info["type"] not in ["rbr"], f"Missing extra information for property of type {info['type']}"
    return info

def create_parameter_assignment(parameter_names, parameter_value_list):
    if type(parameter_value_list) is not list:
        return create_parameter_assignment(parameter_names, [parameter_value_list])
    return OrderedDict(zip(parameter_names, parameter_value_list))


def get_parameter_zero_padding(par_values):
    max_lengths = [0] * len(par_values[0]) if len(par_values) > 0 else []
    for p in par_values:
        for i in range(len(p)):
            max_lengths[i] = max(max_lengths[i], len(str(p[i])))
    return max_lengths


def create_inst_ids(bset_name, model_name, property_id, par_names = None, par_values_list = None):
    # instance IDs shall not include "_" or "."
    assert "_" not in bset_name and "_" not in model_name and "_" not in property_id, f"Invalid character '_' in model name or property id: {model_name}, {property_id}"
    if par_names is None:
        return [f"{bset_name}_{model_name}_{property_id}_"]
    par_fill = get_parameter_zero_padding(par_values_list)

    create_par_string = lambda par_val: "-".join([f"{n}{v:0{f}}" for n,v,f in zip(par_names, par_val, par_fill)])
    result = [f"{bset_name}_{model_name}_{property_id}_{create_par_string(p)}" for p in par_values_list]
    return result

def create_instance(inst_id, benchmark_root, bset_name, model_name, property_id, file_parameter_names = None, open_parameter_names = None, instance_par_values = None,  model_filename = None, property_filename = None):
    inst = OrderedDict()
    inst["id"] = inst_id
    inst["benchmark-root"] = benchmark_root
    inst["benchmark-set"] = bset_name
    inst["name"] = model_name
    inst["model"] = OrderedDict()
    if file_parameter_names is not None:
        inst["model"]["file-parameters"] = create_parameter_assignment(file_parameter_names, instance_par_values[:len(file_parameter_names)])
    if open_parameter_names is not None:
        inst["model"]["open-parameters"] = create_parameter_assignment(open_parameter_names, instance_par_values[-len(open_parameter_names):])
        lvl_width = [v for k,v in inst["model"]["open-parameters"].items() if k.startswith("__lvl")]
        if len(lvl_width) > 0:
            inst["model"]["lvl-width"] = lvl_width
        bnd_thresholds = [v for k,v in inst["model"]["open-parameters"].items() if k in [f"B{i}" for i in range(1,10)]] # detect bound thresholds by parameter name B1, B2, ...
        if len(bnd_thresholds) > 0:
            inst["model"]["bnd-thresholds"] = bnd_thresholds
    inst["model"]["file"] = f"{model_name}/{model_name}.prism" if model_filename is None else model_filename
    inst["model"]["formalism"] = "prism"
    inst["model"]["type"] = "pomdp"
    inst["property"] = create_property_info(property_id, file_name=f"{model_name}/{model_name}.props" if property_filename is None else property_filename)
    assert inst["property"].get("num-bnd-rew-assignments", 0) == len(inst["model"].get("bnd-thresholds", [])), f"Inconsistent dimension of reward bound for instance {inst_id}."
    return inst

def create_model_instances(benchmark_root, bset_name, model_name, property_id, file_parameter_names = [], open_parameter_names = [], par_values_list = None, model_filename = None, property_filename = None):
    par_names = file_parameter_names + open_parameter_names
    if len(par_names) == 0:
        assert par_values_list is None
        ids = create_inst_ids(bset_name, model_name, property_id)
        assert len(ids) == 1
        return [create_instance(ids[0], benchmark_root, bset_name, model_name, property_id, model_filename=model_filename, property_filename=property_filename)]
    else:
        assert par_values_list is not None
        assert len(par_values_list) > 0
        assert len(par_names) == len(par_values_list[0])
        par_values_list = [p if type(p) is list else [p] for p in par_values_list] # ensure list of lists
        ids = create_inst_ids(bset_name, model_name, property_id, par_names, par_values_list)
        assert len(par_values_list) == len(ids)
        return [create_instance(id, benchmark_root, bset_name, model_name, property_id, file_parameter_names, open_parameter_names, par_val, model_filename, property_filename) for id,par_val in zip(ids, par_values_list)]

def create_reward_bounded_instances():
    instances = []

    name = "clean"
    open_parameters = ["N", "B1", "B2", "__lvl1", "__lvl2"]
    par_val_list = [[6,60,5,1,0], [12,120,11,1,0]]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax", open_parameter_names=open_parameters[:1], par_values_list = [[n_val] for n_val in set([p[0] for p in par_val_list])])

    # instances for bnds experiments
    par_val_list = [[6,b,5,1,0] for b in range(25,100,5)]
    instances += create_model_instances("reward-bounded", "rb-bnds", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list)
    # instances for lvls experiments
    par_val_list = [[6,60,5,l,0] for l in [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60]]
    instances += create_model_instances("reward-bounded", "rb-lvls", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list)

    name = "incline"
    open_parameters = ["B1", "B2"]
    par_val_list = [[75,20]] # also interesting: [25,15], [75,15],
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax")

    name = "obstcl"
    open_parameters = ["B1", "B2"]
    par_val_list = [[25,7]]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax")

    name = "resrc"
    open_parameters = ["B1", "B2", "B3"]
    B1_values = [5,15] #[1,5,10,15,20,30,40,50]
    MULTIPLIERS = [12]
    par_val_list = [[b1,b1,b1*stepmul] for b1,stepmul in itertools.product(B1_values,MULTIPLIERS)]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax3", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax")

    name = "rover"
    open_parameters = ["B1", "B2", "B3"]
    MULTIPLIERS = [20,60]
    par_val_list = [[10*m,18*m,10*m] for m in MULTIPLIERS]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax3", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax")

    name = "serv"
    open_parameters = ["B1"]
    par_val_list = [[570], [1000]]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax1", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax")

    name = "walk"
    open_parameters = ["N", "B1"]
    par_val_list = [[40,80],[120,80]]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax1", open_parameter_names=open_parameters, par_values_list=par_val_list)
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax", open_parameter_names=open_parameters[:1], par_values_list = [[n_val] for n_val in set([p[0] for p in par_val_list])])

    name = "water"
    open_parameters = ["B1", "B2"]
    par_val_list = [[590,50],[1790,150]]
    instances += create_model_instances("reward-bounded", "rb-main", name, "rbrmax2", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="water/water_grid_repeat.prism")
    instances += create_model_instances("reward-bounded", "rb-unb", name, "unrmax", model_filename="water/water_grid_repeat.prism")

    return instances

def create_regular_instances():
    instances = []

    open_parameters = ["sl"]
    par_val_list = [[0.1], [0.3]]
    instances += create_model_instances("regular", "reg-main", "grid", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="grid/4x4grid-sl.prism", property_filename="grid/grid.props")
    instances += create_model_instances("regular", "reg-main", "grid", "prbmax", open_parameter_names=open_parameters, par_values_list=[[0]], model_filename="grid/4x4grid-sl.prism", property_filename="grid/grid.props")

    open_parameters = ["sl"]
    par_val_list = [[0], [0.1], [0.3]]
    instances += create_model_instances("regular", "reg-main", "grid-avoid", "prbmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="grid-avoid/4x4grid-avoid-sl.prism", property_filename="grid-avoid/grid-avoid.props")
    instances += create_model_instances("regular", "reg-main", "grid-avoid", "prbmaxgoal", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="grid-avoid/4x4grid-avoid-sl.prism", property_filename="grid-avoid/grid-avoid.props")

    open_parameters = ["N"]
    par_val_list = [[8], [12], [16]]
    instances += create_model_instances("regular", "reg-main", "samplerocks", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="samplerocks/samplerocks.prism", property_filename="samplerocks/samplerocks.props")

    open_parameters = ["N", "R"]
    par_val_list = [[4, 1], [4, 2], [5, 1], [5, 3]]
    instances += create_model_instances("regular", "reg-main", "drone", "prbmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="drone/drone.prism", property_filename="drone/drone.props")

    instances += create_model_instances("regular", "reg-main", "lanes-100", "rewmin", model_filename="lanes-100/lanes-100.prism", property_filename="lanes-100/lanes100.props")
    instances += create_model_instances("regular", "reg-main", "grid-large-30-5", "rewmin", model_filename="grid-large-30-5/grid-large-30-5.prism", property_filename="grid-large-30-5/grid-large-30-5.props")

    open_parameters = ["T", "K"]
    par_val_list = [[8, 20]]
    instances += create_model_instances("regular", "reg-main", "network2", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network/network2.prism", property_filename="network/network.props")
    par_val_list = [[5, 2], [8, 20]]
    instances += create_model_instances("regular", "reg-main", "network3", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network/network3.prism", property_filename="network/network.props")
    par_val_list = [[8, 20]]
    instances += create_model_instances("regular", "reg-main", "network2", "rewmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network/network2.prism", property_filename="network/network.props")
    par_val_list = [[5, 2], [8, 20]]
    instances += create_model_instances("regular", "reg-main", "network3", "rewmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network/network3.prism", property_filename="network/network.props")

    open_parameters = ["T", "K"]
    par_val_list = [[8, 20]]
    instances += create_model_instances("regular", "reg-main", "network-priorities2", "rewmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities2.prism", property_filename="network-priorities/network-priorities.props")
    instances += create_model_instances("regular", "reg-main", "network-priorities2", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities2.prism", property_filename="network-priorities/network-priorities.props")
    instances += create_model_instances("regular", "reg-main", "network-priorities2", "rewmaxpackets", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities2.prism", property_filename="network-priorities/network-priorities.props")
    par_val_list = [[5, 2], [8, 20]]
    instances += create_model_instances("regular", "reg-main", "network-priorities3", "rewmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities3.prism", property_filename="network-priorities/network-priorities.props")
    instances += create_model_instances("regular", "reg-main", "network-priorities3", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities3.prism", property_filename="network-priorities/network-priorities.props")
    instances += create_model_instances("regular", "reg-main", "network-priorities3", "rewmaxpackets", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="network-priorities/network-priorities3.prism", property_filename="network-priorities/network-priorities.props")

    instances += create_model_instances("regular", "reg-main", "maze-concise", "rewmin", model_filename="maze-concise/maze-concise.prism", property_filename="maze-concise/maze-concise.props")

    open_parameters = ["sl"]
    par_val_list = [[0.1], [0.3]]
    instances += create_model_instances("regular", "reg-main", "maze2", "rewmin", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="maze2/maze2-sl.prism", property_filename="maze2/maze2.props")

    instances += create_model_instances("regular", "reg-main", "crypt", "prbmin", model_filename="crypt/crypt_small.prism", property_filename="crypt/crypt.props")
    instances += create_model_instances("regular", "reg-main", "crypt", "prbmax", model_filename="crypt/crypt_small.prism", property_filename="crypt/crypt.props")

    open_parameters = ["N"]
    par_val_list = [[3], [4], [5], [6]]
    instances += create_model_instances("regular", "reg-main", "newgrid", "prbmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="newgrid/newgrid.prism", property_filename="newgrid/newgrid.props")

    open_parameters = ["K"]
    par_val_list = [[8]]
    instances += create_model_instances("regular", "reg-main", "nrp", "prbmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="nrp/nrp.prism", property_filename="nrp/nrp.props")

    open_parameters = ["N"]
    par_val_list = [[6], [8], [10]]
    instances += create_model_instances("regular", "reg-main", "refuel", "prbmax", open_parameter_names=open_parameters, par_values_list=par_val_list, model_filename="refuel/refuel.prism", property_filename="refuel/refuel.props")

    return instances

def create_all_instances():
    return create_regular_instances() + create_reward_bounded_instances()
