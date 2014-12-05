import os
import sys
import argparse
import json
import re
import tempfile
import subprocess

ENV_REGEX = r"(.+)\[(.+)\]"

parser = argparse.ArgumentParser(description="underling task worker")
parser.add_argument("--config", type=unicode, default="underling.json")
parser.add_argument("--env", type=unicode, default="")
parser.add_argument("--watch", type=bool, default=False)
parser.add_argument("command", type=unicode)


def locate_task(task_dirs, task_name):
    for task_dir in task_dirs:
        full_path = os.path.join(task_dir, task_name)

        if os.path.exists(full_path):
            return full_path
    return ""

def expand_globs(inputs):
    pass

def replace_constants(string, constants):
    for constant in constants:
        if isinstance(constants[constant], list):
            string = string.replace("{" + constant + "}", " ".join(constants[constant]))
        else:
            string = string.replace("{" + constant + "}", constants[constant])

    return string

def run_command(config, command, namespace=""):
    task_roots = config.get("__task_dirs__", [])

    constants = {}
    constants["PROJECT_ROOT"] = os.getcwd()

    new_constants = config.get("__constants__", {})
    for const in new_constants:
        if isinstance(new_constants[const], list):
            new_constants[const] = [ replace_constants(x, constants) for x in new_constants[const] ]
        else:
            new_constants[const] = replace_constants(new_constants[const], constants)

    constants.update(new_constants)

    task_roots = [ replace_constants(x, constants) for x in task_roots ]

    commands = config.get("__commands__", {})

    if command not in commands:
        print("Unrecognized command: %s" % command)
        print("Available commands: \n%s" % "\n\n".join(commands.keys()))
        sys.exit(1)

    for dependency in commands[command]:
        if dependency.startswith("file://"):
            print("Unhandled dependency type: %s" % dependency)
            sys.exit(1)

        dependency_name = dependency
        dependency = config.get(dependency_name)
        if not dependency:
            print("Unrecognized dependency: %s" % dependency_name)
            sys.exit(1)

        inputs = ""
        for task in dependency:
            if not isinstance(task, dict):
                print("Pipeline %s should be a list of tasks (dictionaries)" % dependency_name)

            task_name = task.get("task")
            has_env = re.match(ENV_REGEX, task_name)
            if has_env and not has_env.group(2).startswith(namespace):
                continue # Ignore tasks that don't have this namespace

            if has_env:
                task_name = has_env.group(1)

            inputs = replace_constants(task.get("input", ""), constants).split(" ") or inputs
            inputs = expand_globs(inputs)

            if inputs:
                constants["INPUT_FILES"] = inputs

            output_file = task.get("output")
            if not output_file: # No explicit output? Then generate a temporary file
                _, output_file = tempfile.mkstemp()


            task = locate_task(task_roots, task_name)

            if not task:
                print("Unable to find task: %s" % task_name)
                sys.exit(1)


            final_command = [ task, "--output=%s" % output_file ]
            for input_file in inputs:
                final_command.append("--input=%s" % input_file)

            print subprocess.check_output(final_command)

            inputs = output_file

def load_config(config):
    with open(config, "r") as f:
        config = json.loads(f.read())

    return config

def main():
    args = parser.parse_args()
    config = load_config(args.config)

    run_command(config, args.command)
    return 0


if __name__ == '__main__':
    sys.exit(main())
