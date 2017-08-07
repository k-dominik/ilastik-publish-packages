import os
from os.path import basename, splitext, abspath, exists
from pathlib import Path
import sys
import copy
import argparse
import subprocess
import platform
import json
from io import StringIO

import yaml

CONDA_PLATFORM = { 'Darwin': 'osx-64',
                   'Linux': 'linux-64',
                   'Windows': 'win-64' }[platform.system()]

REPO_CACHE_DIR = Path(abspath('./repo-cache'))
PYTHON_VERSION = '3.6'
NUMPY_VERSION = '1.12'
SOURCE_CHANNEL_STRING  = '-c conda-forge'
DESTINATION_CHANNEL = 'ilastik-forge'

# There's probably some proper way to obtain BUILD_PKG_DIR
# via the conda.config python API, but I can't figure it out.
CONDA_ROOT = Path( subprocess.check_output('conda info --root', shell=True).rstrip().decode() )
BUILD_PKG_DIR = CONDA_ROOT / 'conda-bld' / CONDA_PLATFORM

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('recipe_specs_path')
    args = parser.parse_args()
    
    mkdir_p(REPO_CACHE_DIR)
    
    specs_file_contents = yaml.load(open(args.recipe_specs_path, 'r'))
    recipe_specs = specs_file_contents["recipe-specs"]
    for spec in recipe_specs:
        build_and_upload_recipe(spec)

    print("--------")
    print("DONE")
    print("--------")

def build_and_upload_recipe(recipe_spec):
    """
    Given a recipe-spec dictionary, build and upload the recipe if
    it doesn't already exist on ilastik-forge.
    
    More specifically:
      1. Clone the recipe repo to our cache directory (if necessary)
      2. Check out the tag (with submodules, if any)
      3. Render the recipe's meta.yaml ('conda render')
      4. Query the 'ilastik-forge' channel for the exact package.
      5. If the package doesn't exist on ilastik-forge channel yet, build it and upload it.
     
    A recipe-spec is a dict with the following keys:
      - name -- The package name
      - recipe-repo -- A URL to the git repo that contains the package recipe.
      - recipe-subdir -- The name of the recipe directory within the git repo
      - tag -- Which tag/branch/commit of the recipe-repo to use.
      - environment (optional) -- Extra environment variables to define before building the recipe
      - no-test (optional) -- If true, use 'conda build --no-test' when building the recipe
      - conda-build-flag (optional) -- Extra arguments to pass to conda build for this package
    """
    # Extract spec fields
    package_name = recipe_spec['name']
    recipe_repo = recipe_spec['recipe-repo']
    tag = recipe_spec['tag']
    recipe_subdir = recipe_spec['recipe-subdir']
    conda_build_flags = recipe_spec['conda-build-flags'] or ''
    
    if 'no-test' in recipe_spec and recipe_spec['no-test']:
        conda_build_flags += ' --no-test'
    
    build_environment = dict(**os.environ)
    if 'environment' in recipe_spec:
        for key in recipe_spec['environment'].keys():
            recipe_spec['environment'][key] = str(recipe_spec['environment'])
        build_environment.update(recipe_spec['environment'])

    print("-------------------------------------------")        
    print(f"Processing {package_name}")

    os.chdir(REPO_CACHE_DIR)
    repo_dir = checkout_recipe_repo(recipe_repo, tag)

    # All subsequent work takes place within the recipe repo
    os.chdir(repo_dir)

    # Render
    recipe_version, recipe_build_string = get_rendered_version(package_name, recipe_subdir, build_environment)
    print(f"Recipe version is: {package_name}-{recipe_version}-{recipe_build_string}")

    # Check our channel.  Did we already upload this version?
    if check_already_exists(package_name, recipe_version, recipe_build_string):
        print(f"Found {package_name}-{recipe_version}-{recipe_build_string} on {DESTINATION_CHANNEL}, skipping build.")
    else:
        # Not on our channel.  Build and upload.
        build_recipe(package_name, recipe_subdir, conda_build_flags, build_environment)
        upload_package(package_name, recipe_version, recipe_build_string)        


def checkout_recipe_repo(recipe_repo, tag):
    """
    Checkout the given repository and tag.
    Clone it first if necessary, and update any submodules it has.
    """
    repo_name = splitext(basename(recipe_repo))[0]

    cwd = abspath(os.getcwd())
    if not exists( repo_name ):
        subprocess.check_call(f"git clone {recipe_repo}", shell=True)
        os.chdir(repo_name)
    else:
        os.chdir(repo_name)
        subprocess.check_call(f"git fetch", shell=True)

    print(f"Checking out {tag} of {repo_name} into {cwd}...")
    subprocess.check_call(f"git checkout {tag}", shell=True)
    subprocess.check_call(f"git submodule update --init --recursive", shell=True)
    os.chdir(cwd)

    return repo_name

def get_rendered_version(package_name, recipe_subdir, build_environment):
    """
    Use 'conda render' to process a recipe's meta.yaml (processes jinja templates and selectors).
    Returns the version and build string from the rendered file.
    """
    print(f"Rendering recipe in {recipe_subdir}...")
    render_cmd = f"conda render --python={PYTHON_VERSION} --numpy={NUMPY_VERSION} {recipe_subdir} {SOURCE_CHANNEL_STRING}"
    print('\t' + render_cmd)
    rendered_meta_text = subprocess.check_output(render_cmd, env=build_environment, shell=True).decode()
    meta = yaml.load(StringIO(rendered_meta_text))
    if meta['package']['name'] != package_name:
        raise RuntimeError("Recipe for package '{package_name}' has unexpected name: '{meta['package']['name']}'")
    #import pprint
    #pprint.pprint(meta)
    
    render_cmd += " --output"
    rendered_filename = subprocess.check_output(render_cmd, env=build_environment, shell=True).decode()
    build_string_with_hash = rendered_filename.split('-')[-1].split('.')[0]

    return meta['package']['version'], build_string_with_hash


def check_already_exists(package_name, recipe_version, recipe_build_string):
    """
    Check if the given package already exists on anaconda.org in the
    ilastik-forge channel with the given version and build string.
    """
    print(f"Searching channel: {DESTINATION_CHANNEL}")
    search_cmd = f"conda search --json  --full-name --override-channels --channel={DESTINATION_CHANNEL} {package_name}"  
    print('\t' + search_cmd)
    search_results_text = subprocess.check_output( search_cmd, shell=True ).decode()
    search_results = json.loads(search_results_text)

    if package_name not in search_results:
        return False

    print("Found package!")

    for result in search_results[package_name]:
        if result['build'] == recipe_build_string and result['version'] == recipe_version:
            return True
    
    return False


def build_recipe(package_name, recipe_subdir, build_flags, build_environment):
    """
    Build the recipe.
    """
    print(f"Building {package_name}")
    build_cmd = f"conda build {build_flag} --python={PYTHON_VERSION} --numpy={NUMPY_VERSION} {recipe_subdir} {SOURCE_CHANNEL_STRING}"
    print('\t' + build_cmd)
    try:
        subprocess.check_call(build_cmd, env=build_environment, shell=True)
    except subprocess.CalledProcessError as ex:
        print(f"Failed to build package: {package_name}", file=sys.stderr)
        sys.exit(1)


def upload_package(package_name, recipe_version, recipe_build_string):
    """
    Upload the package to the ilastik-forge channel.
    """
    pkg_file_name = f"{package_name}-{recipe_version}-{recipe_build_string}.tar.bz2"
    pkg_file_path = BUILD_PKG_DIR / pkg_file_name
    upload_cmd = f"anaconda upload -u {DESTINATION_CHANNEL} {pkg_file_path}"
    print(f"Uploading {pkg_file_name}")
    print(upload_cmd)
    subprocess.check_call(upload_cmd, shell=True)


def mkdir_p(path):
    """
    Like the bash command: mkdir -p
    
    ...why the heck isn't this built-in to the Python std library?
    """
    import os, errno
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

if __name__ == "__main__":
#     import os
#     from os.path import dirname
#     os.chdir(dirname(__file__))
#     sys.argv.append('recipe-specs.yaml')

    sys.exit( main() )
