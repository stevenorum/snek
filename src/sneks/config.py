from argparse import ArgumentParser, Namespace
import boto3
import json
import os
from sneks.git import get_repo_name

class SneksParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument("-f", "--filename",
                          help="Filename of the config file.  Defaults to 'sneks.json'",
                          dest="filename",
                          default="sneks.json")
    def parse_args(self, *args, **kwargs):
        args = super().parse_args(*args, **kwargs)
        sneks_config = load_config(args.filename)
        return Namespace(sneks_config=sneks_config, **vars(args))

def load_config(filename):
    if not os.path.exists(filename) or not os.path.isfile(filename):
        raise RuntimeError("Conf file '{}' doesn't exist!\n".format(filename))
    with open(filename) as f:
        conf = json.load(f)
    if "AWS_REGION" in conf and "AWS_PROFILE" in conf:
        boto3.setup_default_session(region_name=conf["AWS_REGION"], profile_name=conf["AWS_PROFILE"])
    return conf

def load_stack_info():
    repo_name = get_repo_name()
    cf = boto3.client("cloudformation")
    stacks = cf.describe_stacks()["Stacks"]
    build_stack = [s for s in stacks if s["StackName"].startswith(repo_name + "-build")][0]
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
        "build_stack_outputs":{x['OutputKey']:x['OutputValue'] for x in build_stack["Outputs"]},
        "deploy_stack_outputs":{x['OutputKey']:x['OutputValue'] for x in deploy_stack["Outputs"]},
    }

# def load_build_stack_outputs():
#     repo_name = get_repo_name()
#     cf = boto3.client("cloudformation")
#     stacks = cf.describe_stacks()["Stacks"]
#     build_stack = [s for s in stacks if s["StackName"].startswith(repo_name + "-build")][0]
#     build_stack_params = {x["ParameterKey"]:x["ParameterValue"] for x in build_stack["Parameters"]}
#     deploy_stack_name = build_stack_params.get("ChildStackName")
#     if not deploy_stack_name:
#         deploy_stack_name = "{PackageName}-{PackageBranch}".format(**build_stack_params)
#     deploy_stack = [s for s in stacks if s["StackName"] == deploy_stack_name][0]
#     build_outputs = build_stack["Outputs"]
#     build_outputs = {x['OutputKey']:x['OutputValue'] for x in build_stack["Outputs"]}
#     if "DeployStackName" not in build_outputs:
#         build_outputs["DeployStackName"] = deploy_stack["StackName"]
#     return build_outputs

# def load_deploy_stack_outputs():
#     repo_name = get_repo_name()
#     cf = boto3.client("cloudformation")
#     stacks = cf.describe_stacks()["Stacks"]
#     build_stack = [s for s in stacks if s["StackName"].startswith(repo_name + "-build")][0]
#     deploy_stack = [s for s in stacks if s["StackName"].startswith(repo_name) and not s["StackName"] == build_stack["StackName"]][0]
#     deploy_outputs = deploy_stack["Outputs"]
#     deploy_outputs = {x['OutputKey']:x['OutputValue'] for x in deploy_outputs}
#     return deploy_outputs
