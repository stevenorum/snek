import os

def get_repo_name(directory=None):
    here = directory if directory else os.getcwd()
    subdirs = os.listdir(here)
    while len(here) > 1 and '.git' not in subdirs:
        here = os.path.dirname(here)
        subdirs = os.listdir(here)
    if '.git' not in subdirs:
        return None
    return os.path.basename(here)
