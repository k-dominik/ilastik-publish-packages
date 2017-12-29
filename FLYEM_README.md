FlyEM Publish Packages
======================

For most of the packages FlyEM depends on, developers should obtain them via the [conda-forge][2] project.
But some of the packages we use are not hosted on conda-forge.

These fall into three categories:

1. Packages which we (FlyEM) are actively developing
2. Packages which we are not the original authors of, but which conda-forge does not currently host
3. Packages which conda-forge hosts, but with a version or build configuration we can't use. 

In those cases, we must build the packages ourselves, and host them on [our own channel ("flyem-forge")][3] in the Anaconda cloud.

This repo contains a script to fetch and build such packages.  Before building each one, the script checks to see if it has already been built and uploaded to our channel, in which case the build can be skipped.  For more details, see the docstrings in `build-recipes.py`.

Usage
-----

```bash
cd flyem-publish-packages

# Activate the root conda environment. Must be Python 3.6 
source activate root

# Make sure you have a very recent version of conda-build
conda install --override-channels -c defaults conda-build

# Build/upload all FlyEM dependencies
./build-recipes.py flyem-recipe-specs.yaml
```

To add a new package, simply add a new item to `flyem-recipe-specs.yaml`.


[1]: https://github.com/ilastik/ilastik-publish-packages
[2]: https://conda-forge.org
[3]: https://anaconda.org/flyem-forge

