# ilastik-publish-packages
Scripts to update our published conda packages when our recipes have changed.

By Stuart Berg, Carsten Haubold, in 2017

## Introduction:

ilastik has quite a lot of dependencies, which we handle by using the _conda package manager_.
Conda can retrieve packages from different channels, and most of our dependencies we take from the `conda-forge` channel (see also https://conda-forge.org). 

Some of ilastik's dependencies are developed by us, and for some external packages we require special builds or patches, hence we need to build those conda packages ourselves.

The build process is automated by the scripts in this repository.

## Prerequisites:


### Linux:
We build all Linux packages in the conda-forge docker image to be compatible, and compile with GCC 4.8.
To start an interactive session in this barebones linux, execute

```
docker run -i -t condaforge/linux-anvil
```

If you want to mount some local folders into the docker container, e.g. to install the commercial solvers there, append `-v localfolder:mountfolder` for every folder you want to make accessible.

Inside the docker container, you might want to install some necessities:

```sh
yum install vim 
yum install java-1.8.0-openjdk-headless.x86_64 unzip # (java and unzip needed for CPLEX installer)
conda install cmake
conda install conda-build --override-channels -c defaults # to get the latest conda-build
```

### MacOS:

* Install XCode (freely available on the AppStore)
* Install the MacOS 10.9 SDK to build for older OS versions than your one from https://github.com/devernay/xcodelegacy by following their instructions.
* Install [Miniconda](https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh) if you don't have it yet.
* Install CMake, e.g. by `conda install cmake` or through `brew`.
* Install `conda-build` (otherwise `conda render` won't work): `conda install conda-build`
* Install the anaconda client for uploading packages to our `ilastik-forge` channel: `conda install anaconda-client` in your conda root environment

### Windows:

* Install the Visual Studio 2015 build tools (which contain the VC14 compiler) from http://landinghub.visualstudio.com/visual-cpp-build-tools
  - select _custom_ installation and select the Win 10 SDK
* Install Miniconda Python 3 64-bit and let it add conda to the environment vars
  - If you do not do this, the `activate` step below will fail. Then you'll have to add `C:\Users\YOURUSERNAME\Miniconda3\Scripts` to `PATH` via the control panel.
* Open a command prompt by executing: `C:\Program Files (x86)\Microsoft Visual C++ Build Tools\Visual C++ 2015 x64 Native Build Tools CMD`
* Install some prerequisites in conda's root environment:
  ```sh
  activate root
  conda install git cmake pyyaml conda-build anaconda-client m2-patch
  ```


### Solvers:

To build the tracking and multicut C++ packages with all features (listed in `ilastik-dependencies` at the bottom), you need to install the ILP solvers Gurobi and CPLEX on your development machine, and **adjust the paths to the solvers in the `ilastik-recipe-specs.yaml` file**:

* **CPLEX**
    * Linux Docker Container:
        * start a clean shell for cplex installation: env -i bash --noprofile --norc
        * install cplex (e.g. `/opt/cplex`)
          ```
          bash cplex_studio12.7.1.linux-x86-64.bin
          ```
        * quit the clean shell (exit)
    * macOS (requires CPLEX version 12.7 or newer, the ones before weren't built with clang):
      ```
      bash cplex_studio12.7.1.osx.bin
      ```
* **Gurobi:**
    * Extract/Install Gurobi on the machine
    * If you do not have that yet, obtain a licence for the build machine (needs to be done for each new docker container!) and run `grbgetkey ...` as described on their website.

## Building packages:

Run `conda install anaconda-client`. You need to be logged in to your https://anaconda.org account by running `anaconda login`. Then you can build the packages by running the commands below:

```bash
git clone https://github.com/ilastik/ilastik-publish-packages
cd ilastik-publish-packages
source activate root # needs to have latest conda-build and anaconda, and being logged into an anaconda account
# on Linux and Windows:
python build-recipes.py ilastik-recipe-specs.yaml
# on Mac:
MACOSX_DEPLOYMENT_TARGET=10.9 python build-recipes.py ilastik-recipe-specs.yaml
```

The `build-recipes.py` script parses the packages from `ilastik-recipe-specs.yaml`, and for each package checks whether that version is already available on the `ilastik-forge` channel. If that is not the case, it will build the package and upload it to `ilastik-forge`. By default, the script **assumes you have both solvers** and wants to build all packages. If you do not have CPLEX or Gurobi, comment out the sections near the end that have `cplex` or `gurobi` in their name, as well as the `ilastik-dependencies` package as described below.

### Configuration:

If you want to change which packages are built, _e.g._ to build **without solvers** edit the ilastik-recipe-specs.yaml file. There, you can comment or change the sections specific to respective packages.
It is a YAML file with the following format:
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
