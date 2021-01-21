#!/usr/bin/env python3

import os
from setuptools import setup

MAJOR_VERSION='0'
MINOR_VERSION='0'
PATCH_VERSION='27'

VERSION = "{}.{}.{}".format(MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION)

packages = ['sneks','sneks.sam','sneks.ddb']
package_dir = {p: 'src/' + p.replace('.','/') for p in packages}

scriptdir = "scripts"
script_files = [os.path.join(scriptdir, f) for f in os.listdir(scriptdir) if f[-1] not in "~#" and f[0] not in "~#."]
scripts = [f for f in script_files if os.access(f, os.X_OK)]

def main():
    setup(
        name = 'sneks',
        packages = packages,
        package_dir = package_dir,
        version = VERSION,
        description = 'Basic python utilities.',
        author = 'Steve Norum',
        author_email = 'sn@drunkenrobotlabs.org',
        url = 'https://github.com/stevenorum/sneks',
        download_url = 'https://github.com/stevenorum/sneks/archive/{}.tar.gz'.format(VERSION),
        keywords = ['python'],
        classifiers = [],
        install_requires=[
            'beautifulsoup4',
            'boto3',
            'jinja2'
        ],
        scripts = scripts,
        test_suite = 'tests'
    )

if __name__ == "__main__":
    main()
