#!/bin/bash

# python3 -m pip install --user --upgrade setuptools wheel twine

VERSION=$(python3 -c "import setup ; print(setup.VERSION)")

git push origin master && git tag $VERSION -m "$*" && git push --tags origin master

rm dist/*
python3 setup.py sdist bdist_wheel
twine upload --repository testpypi dist/*
twine upload --repository pypi dist/*
