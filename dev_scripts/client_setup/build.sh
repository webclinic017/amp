#!/bin/bash
#
# Build a thin virtual environment to run workflows on the dev machine.
#

# TODO(gp): Use python 3.9 and keep this in sync with
# devops/docker_build/pyproject.toml

set -e

echo "which python="$(which python 2>&1)
echo "python -v="$(python --version 2>&1)
echo "which python3="$(which python3)
echo "python3 -v="$(python3 --version)

# Keep this in sync with `dev_scripts/setenv_amp.sh`
# TODO(gp): VENV_DIR should be shared among the scripts through a file.
VENV_DIR="$HOME/src/venv/amp.client_venv"
echo "# VENV_DIR=$VENV_DIR"

if [[ -d $VENV_DIR ]]; then
    echo "# Deleting old virtual environment in '$VENV_DIR'"
    rm -rf $VENV_DIR
fi;
echo "# Creating virtual environment in '$VENV_DIR'"
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install packages.
# TODO(gp): Switch to poetry.
python3 -m pip install --upgrade pip
pip3 install -r dev_scripts/client_setup/requirements.txt

AWS_VER=$(aws --version)
echo "# aws=$AWS_VER"
INVOKE_VER=$(invoke --version)
echo "# invoke=$INVOKE_VER"
POETRY_VER=$(poetry --version)
echo "# poetry=$POETRY_VER"
DOCKER_COMPOSE_VER=$(docker-compose --version)
echo "# docker-compose=$DOCKER_COMPOSE_VER"

DOCKER_VER=$(docker --version)
echo "# docker=$DOCKER_VER"

# TODO(gp): Install this only on Mac.

if [[ $(uname) == "Darwin" ]]; then
    # Update brew.
    brew update
    BREW_VER=$(brew --version)
    echo "# brew version=$BREW_VER"

    # Install GitHub CLI.
    brew install gh
    GH_VER=$(gh --version)
    echo "# gh version=$GH_VER"

    # Install dive.
    # https://github.com/wagoodman/dive
    #brew install dive
    #echo "dive version="$(dive --version)
fi;

echo "# Configure your client with:"
echo "> source dev_scripts/setenv_amp.sh"
