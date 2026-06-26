import os, re
from collections import OrderedDict

def ask_user_for_info(description, default = None, validation = None):
    if default is None:
        resp = input(f"{description}: ")
    else:
        resp = input(f"{description} [{default}]: ")
        if resp == "": resp = default
    if validation is not None and not validation(resp):
        return ask_user_for_info(description, default, validation)
    return resp

def ask_user_yn(description):
    return ask_user_for_info(description + " (type 'y' or 'n')", validation=lambda usr_input : usr_input in ["y", "n"]) == "y"

def ask_user_overwrite_file(filename):
    if os.path.isfile(filename): 
        return ask_user_yn(f"File {filename} exists. Overwrite?")
    return True

def input_selection(item : str, options, single_choice = False, group_options = None, group_descriptions = None):
    if not single_choice:
        if "a" in options: raise AssertionError("options should not include key 'a'")
        if "d" in options: raise AssertionError("options should not include key 'd'")
        if "c" in options: raise AssertionError("options should not include key 'c'")
    if len(options) == 0: raise AssertionError("options should not be empty.")
    if group_options is None:
        group_options = OrderedDict()
    if group_descriptions is None:
        group_descriptions = OrderedDict()
    for key in group_options:
        if key in options: raise AssertionError(f"group option '{key}' should not overlap with a regular option key")
        if key in ["a", "c", "d"]: raise AssertionError(f"group option '{key}' should not use a reserved key")

    def normalize_descriptions(descriptions):
        return descriptions if type(descriptions) is list else [descriptions]

    option_descs = [normalize_descriptions(options[key]) for key in options]
    group_descs = [normalize_descriptions(group_descriptions[key]) if key in group_descriptions else [f"All {key} benchmarks"] for key in group_options]
    longest_option_descriptions = []
    longest_option_descriptions.append(max([len(key) for key in list(options.keys()) + list(group_options.keys())] + [4]) + 4)
    i = 0
    while True:
        longest = -1
        for descriptions in option_descs + group_descs:
            if i < len(descriptions):
                longest = max(longest, len(descriptions[i]))
        if longest >= 0:
            longest_option_descriptions.append(longest + 4)
        else:
            break
        i += 1
        
    selected_keys = []      
    while True:
        keys = []
        print("Select {}.".format(item))
        print("    Option" + " " * (longest_option_descriptions[0] - len("Option")) + "Description")
        print("----" + "-" * sum(longest_option_descriptions))
        for key, descriptions in zip(options.keys(), option_descs):
            keys.append(key)
            description = ""
            for i in range(len(descriptions)):
                description += "{}{}".format(descriptions[i], " " * (longest_option_descriptions[i+1] - len(descriptions[i])))
            print("{}{}{}".format("[X] " if key in selected_keys else "[ ] ", key + " " * (longest_option_descriptions[0] - len(key)), description))
        if len(group_options) > 0:
            print("----" + "-" * sum(longest_option_descriptions))
            print("Groups:")
        for key, descriptions in zip(group_options.keys(), group_descs):
            keys.append(key)
            description = ""
            for i in range(len(descriptions)):
                description += "{}{}".format(descriptions[i], " " * (longest_option_descriptions[i+1] - len(descriptions[i])))
            group_selected = all(member in selected_keys for member in group_options[key])
            print("{}{}{}".format("[X] " if group_selected else "[ ] ", key + " " * (longest_option_descriptions[0] - len(key)), description))
        if not single_choice:
            keys.append("a")
            print("    {}Select all".format("a" + " " * (longest_option_descriptions[0] - 1)))
        if not single_choice and len(selected_keys) > 0:
            keys.append("c")
            print("    {}Clear selection".format("c" + " " * (longest_option_descriptions[0] - 1)))
            keys.append("d")
            print("    {}done".format("d" + " " * (longest_option_descriptions[0] - 1)))
        selection = input("Enter option: ")
        if selection in keys:            
            if selection in options:
                if selection not in selected_keys:
                    selected_keys.append(selection)
                if single_choice:
                    break
            elif selection in group_options:
                for key in group_options[selection]:
                    if key not in selected_keys:
                        selected_keys.append(key)
            elif selection == "a":
                selected_keys = keys[:len(options)]
                break
            elif selection == "d":
                break
            elif selection == "c":
                selected_keys = []
        else:
            matching_keys = [key for key in options if re.fullmatch(selection, key)]
            if len(matching_keys) == 0:
                print ("Invalid selection. Enter any of {} or press Ctrl+C to abort.".format(keys))
            else:
                selected_keys += matching_keys
    print("Selected {}: {}".format(item,selected_keys))
    return selected_keys
