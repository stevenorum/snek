#!/bin/bash

# Copy everything over to the build/ directory so it can be bundled up.

SCRIPTS="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

if [ -e build ] ; then
    rm -rf build/
fi
mkdir -p build

cp -r src/* build/

# Not required that we copy this over,
# but if you have to later debug it from the source bundle,
# this makes it easier.
cp SamTemplate.json build/

if [ -e static ] ; then
    bash ${SCRIPTS}/upload_static_assets.sh build/static_config.json
    cp -r static build/
fi

if [ -e jinja_templates ] ; then
    cp -r jinja_templates build/
fi

if [ -e requirements.txt ] ; then
    pip3 install -t build/ -r requirements.txt
fi
