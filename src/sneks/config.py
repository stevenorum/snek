from argparse import ArgumentParser, Namespace
import boto3
import json
import os
from sneks.git import get_repo_name

SNEKS_CONFIG = {}

class SneksParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument("-f", "--filename",
                          help="Filename of the config file.  Defaults to 'sneks.json'",
                          dest="filename",
                          default=None)
    def parse_args(self, *args, **kwargs):
        args = super().parse_args(*args, **kwargs)
        sneks_config = load_config(args.filename)
        return Namespace(sneks_config=sneks_config, **vars(args))

def load_config(filename=None):
    global SNEKS_CONFIG
    _filename = filename if filename else "sneks.json"
    if not os.path.exists(_filename) or not os.path.isfile(_filename):
        if filename:
            raise RuntimeError("Conf file '{}' doesn't exist!\n".format(filename))
    else:
        with open(_filename) as f:
            SNEKS_CONFIG.update(json.load(f))
    SNEKS_CONFIG["AWS_REGION"] = SNEKS_CONFIG.get("AWS_REGION") if SNEKS_CONFIG.get("AWS_REGION") else "us-east-1"
    SNEKS_CONFIG["AWS_PROFILE"] = SNEKS_CONFIG.get("AWS_PROFILE") if SNEKS_CONFIG.get("AWS_PROFILE") else "default"
    boto3.setup_default_session(region_name=SNEKS_CONFIG["AWS_REGION"], profile_name=SNEKS_CONFIG["AWS_PROFILE"])
    return SNEKS_CONFIG

def load_stack_info():
    global SNEKS_CONFIG
    repo_name = get_repo_name()
    cf = boto3.client("cloudformation")
    stacks = cf.describe_stacks()["Stacks"]
    build_stack_name = SNEKS_CONFIG.get("BUILD_STACK_NAME", repo_name + "-build")
    build_stack = [s for s in stacks if s["StackName"] == build_stack_name][0]
    build_stack_params = {x["ParameterKey"]:x["ParameterValue"] for x in build_stack["Parameters"]}
    deploy_stack_name = build_stack_params.get("ChildStackName")
    if not deploy_stack_name:
        deploy_stack_name = "{PackageName}-{PackageBranch}".format(**build_stack_params)
    deploy_stack = [s for s in stacks if s["StackName"] == deploy_stack_name][0]
    return {
        "build_stack_name":build_stack["StackName"],
        "deploy_stack_name":deploy_stack_name,
        "build_stack":build_stack,
        "deploy_stack":deploy_stack,
        "build_stack_outputs":{x['OutputKey']:x['OutputValue'] for x in build_stack.get("Outputs",[])},
        "deploy_stack_outputs":{x['OutputKey']:x['OutputValue'] for x in deploy_stack.get("Outputs",[])},
    }
