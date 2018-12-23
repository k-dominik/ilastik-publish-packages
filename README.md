[![Build Status](https://travis-ci.org/ilastik/ilastik-publish-packages.svg?branch=master)](https://travis-ci.org/ilastik/ilastik-publish-packages)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# publish-conda-stack

Scripts build a custom set of conda packages from a common environment and publish to a custom conda channel.

By Stuart Berg, Carsten Haubold, in 2017

## Introduction:

Originally developed to manage the dependency tree for [ilastik](https://ilastik.org), which we handle by using the _conda package manager_.
The build process is automated by the scripts in this repository.

## Installation

A pre-build version of the `publish-conda-stack` package is available via conda:

```bash
conda install -c ilastik-forge -c conda-forge publish-conda-stack
```

This also installs the `publish-conda-stack` main entry-point and makes it available in the respective conda environment.

## Building packages:

### Configuration files

Run `conda install anaconda-client`. You need to be logged in to your https://anaconda.org account by running `anaconda login`.

`publish-conda-stack` builds packages specified in a `yaml` config file. An example:

#### Common configuration

```yaml
# common configuration for all packages defined in shared-config:
shared-config:
  # will translate to --python for every conda-build, deprecated, use pin-file
  python: '3.6'
  # will translate to --numpy for every conda-build, deprecated, use pin-file
  numpy: '1.13'
  # Path to store git repositories containing recipes. Relative to this yaml file's directory.
  repo-cache-dir: ./repo-cache
  # Channels to check for dependencies of the built packages
  source-channels:
    - ilastik-forge
    - conda-forge
  # channel to upload recipes to
  destination-channel: ilastik-forge
```

#### Package definitions

```yaml
recipe-specs:
    - name: PACKAGE_NAME
      recipe-repo: PACKAGE_RECIPE_GIT_URL
      tag: RECIPE_GIT_TAG_OR_BRANCH
      recipe-subdir: RECIPE_DIR_IN_GIT_REPO
      
      # Optional specs
      environment:
          MY_VAR: VALUE
      conda-build-flags: STRING_THAT_WILL_BE_APPENDED_TO_CONDA_BUILD
      # by default a package is built on all 3 platforms, you can restrict that by specifying the following
      build-on:
        - linux
        - win
        - osx

    - name: NEXT_PACKAGE
          ...
```

#### Dependency pins

```yaml

```

### Building

```bash
# on Linux and Windows:
python build-recipes.py ilastik-recipe-specs.yaml
# on Mac:
MACOSX_DEPLOYMENT_TARGET=10.9 python build-recipes.py ilastik-recipe-specs.yaml
```

The `build-recipes.py` script parses the packages from `ilastik-recipe-specs.yaml`, and for each package checks whether that version is already available on the `ilastik-forge` channel. If that is not the case, it will build the package and upload it to `ilastik-forge`. By default, the script **assumes you have both solvers** and wants to build all packages. If you do not have CPLEX or Gurobi, comment out the sections near the end that have `cplex` or `gurobi` in their name, as well as the `ilastik-dependencies` package as described below.

### Configuration:

If you want to change which packages are built, _e.g._ to build **without solvers** edit the ilastik-recipe-specs.yaml file. There, you can comment or change the sections specific to respective packages.
It is a YAML file with the following format:

