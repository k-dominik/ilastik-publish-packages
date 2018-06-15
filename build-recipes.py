#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
import os
from os.path import basename, splitext, abspath, exists, dirname, normpath
from pathlib import Path
import sys
import argparse
import subprocess
import platform
import json
import tempfile
import yaml
import textwrap
import datetime

try:
    import argcomplete
    from argcomplete.completers import FilesCompleter
    ENABLE_TAB_COMPLETION = True
except:
    # See --help text for instructions.
    ENABLE_TAB_COMPLETION = False


# See _init_globals(), below
CONDA_PLATFORM = None
PLATFORM_STR = None
BUILD_PKG_DIR = None


def parse_cmdline_args():
    """
    Parse the user's command-lines, with support for tab-completion.
    """
    bashrc = '~/.bashrc'
    if os.path.exists(os.path.expanduser('~/.bash_profile')):
        bashrc = '~/.bash_profile'

    prog_name = sys.argv[0]
    if prog_name[0] not in ('.', '/'):
        prog_name = './' + prog_name

    help_epilog = textwrap.dedent(f"""\
        --------------------------------------------------------------------
        To activate command-line tab-completion, run the following commands:

        conda install argcomplete
        echo 'eval "$(register-python-argcomplete {prog_name} -s bash)"' >> {bashrc}

        ...and run this script directly as "{prog_name}", not "python {prog_name}"
        --------------------------------------------------------------------
        """)

    parser = argparse.ArgumentParser(
        epilog=help_epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--list', action='store_true',
                        help='List the recipe names in the specs file')
    specs_path_arg = parser.add_argument(
        'recipe_specs_path', help='Path to a recipe specs YAML file')
    selection_arg = parser.add_argument(
        'selected_recipes', nargs='*', help='Which recipes to process (Default: process all)')

    if ENABLE_TAB_COMPLETION:
        def complete_recipe_selection(prefix, action, parser, parsed_args):
            specs_file_contents = yaml.load(
                open(parsed_args.recipe_specs_path, 'r'))
            recipe_specs = specs_file_contents["recipe-specs"]
            names = (spec['name'] for spec in recipe_specs)
            return filter(lambda name: name.startswith(prefix), names)

        specs_path_arg.completer = FilesCompleter(
            ('.yml', '.yaml'), directories=False)
        selection_arg.completer = complete_recipe_selection
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    return args


def main():
    start_time = datetime.datetime.now()
    args = parse_cmdline_args()
    _init_globals()

    specs_file_contents = yaml.load(open(args.recipe_specs_path, 'r'))

    # Read the 'shared-config' section
    shared_config = specs_file_contents["shared-config"]
    expected_shared_config_keys = [
        'python', 'numpy', 'source-channels', 'destination-channel', 'repo-cache-dir']
    assert set(shared_config.keys()) == set(expected_shared_config_keys), \
        f"shared-config section is missing expected keys or has too many.  Expected: {expected_shared_config_keys}"

    # Convenience member
    shared_config['source-channel-string'] = ' '.join(
        [f'-c {ch}' for ch in shared_config['source-channels']])

    # Overwrite repo-cache-dir with an absolute path
    # Path is given relative to the specs file directory.
    if not shared_config['repo-cache-dir'].startswith('/'):
        specs_dir = Path(dirname(abspath(args.recipe_specs_path)))
        shared_config['repo-cache-dir'] = Path(
            normpath(specs_dir / shared_config['repo-cache-dir']))

    os.makedirs(shared_config['repo-cache-dir'], exist_ok=True)

    selected_recipe_specs = get_selected_specs(
        args, specs_file_contents["recipe-specs"])

    if args.list:
        print_recipe_list(selected_recipe_specs)
        sys.exit(0)

    result = {
        'found': [],
        'built': [],
        'start_time': start_time.isoformat(timespec='seconds'),
        'recipe_specs_path': args.recipe_specs_path,
        'selected_recipies': args.selected_recipes
    }

    script_path = os.path.abspath(os.path.split(__file__)[0])
    result_file = os.path.join(script_path, f"{start_time.strftime('%Y%m%d-%H%M%S')}_build_out.yaml")
    for spec in selected_recipe_specs:
        status = build_and_upload_recipe(spec, shared_config)
        for k, v in status.items():
            result[k].append(v)
        with open(result_file, 'w') as f:
            yaml.dump(result, f, default_flow_style=False)

    end_time = datetime.datetime.now()
    result['end_time'] = end_time.isoformat(timespec='seconds')
    result['duration'] = str(end_time - start_time)
    with open(result_file, 'w') as f:
        yaml.dump(result, f, default_flow_style=False)

    print("--------")
    print(f"DONE, Result written to {result_file}")
    print("--------")


def _init_globals():
    """
    We initialize globals in this function, AFTER argcomplete is used.
    (Using subprocess interferes with argcomplete.)
    """
    global CONDA_PLATFORM
    global BUILD_PKG_DIR
    global PLATFORM_STR

    CONDA_PLATFORM = {'Darwin': 'osx-64',
                      'Linux': 'linux-64',
                      'Windows': 'win-64'}[platform.system()]
    PLATFORM_STR = CONDA_PLATFORM.replace('-64', '')

    # There's probably some proper way to obtain BUILD_PKG_DIR
    # via the conda.config python API, but I can't figure it out.
    CONDA_ROOT = Path(subprocess.check_output(
        'conda info --root', shell=True).rstrip().decode())
    BUILD_PKG_DIR = CONDA_ROOT / 'conda-bld'


def print_recipe_list(recipe_specs):
    max_name = max(len(spec['name']) for spec in recipe_specs)
    for spec in recipe_specs:
        print(
            f"{spec['name']: <{max_name}} : {spec['recipe-repo']} ({spec['tag']})")


def get_selected_specs(args, full_recipe_specs):
    """
    If the user gave a list of specific recipes to process,
    select them from the given recipe specs.
    """
    if not args.selected_recipes:
        return full_recipe_specs

    available_recipe_names = [spec['name'] for spec in full_recipe_specs]
    invalid_names = set(args.selected_recipes) - set(available_recipe_names)
    if invalid_names:
        sys.stderr.write("Invalid selection: The following recipes are not listed"
                         f" in {args.recipe_specs_path}: {', '.join(invalid_names)}")
        sys.exit(1)

    # Remove non-selected recipes
    filtered_specs = list(
        filter(lambda spec: spec['name'] in args.selected_recipes, full_recipe_specs))
    filtered_names = [spec['name'] for spec in filtered_specs]
    if filtered_names != args.selected_recipes:
        print(
            f"WARNING: Your recipe list was not given in the same order as in {args.recipe_specs_path}.")
        print(
            f"         They will be processed in the following order: {', '.join(filtered_names)}")

    return filtered_specs


def build_and_upload_recipe(recipe_spec, shared_config):
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
      - conda-build-flags (optional) -- Extra arguments to pass to conda build for this package
      - build-on (optional) -- A list of operating systems on which the package should be built. Available are: osx, win, linux
    """
    # Extract spec fields
    package_name = recipe_spec['name']
    recipe_repo = recipe_spec['recipe-repo']
    tag = recipe_spec['tag']
    recipe_subdir = recipe_spec['recipe-subdir']
    conda_build_flags = recipe_spec.get('conda-build-flags', '')

    print("-------------------------------------------")
    print(f"Processing {package_name}")

    # check whether we need to build the package on this OS at all
    if 'build-on' in recipe_spec:
        platforms_to_build_on = recipe_spec['build-on']
        assert isinstance(platforms_to_build_on, list)
        assert(all(o in ['win', 'osx', 'linux']
                   for o in platforms_to_build_on))
    else:
        platforms_to_build_on = ['win', 'osx', 'linux']

    if PLATFORM_STR not in platforms_to_build_on:
        print(
            f"Not building {package_name} on platform {PLATFORM_STR}, only builds on {platforms_to_build_on}")
        return {}

    # configure build environment
    build_environment = dict(**os.environ)
    if 'environment' in recipe_spec:
        for key in recipe_spec['environment'].keys():
            recipe_spec['environment'][key] = str(
                recipe_spec['environment'][key])
        build_environment.update(recipe_spec['environment'])

    os.chdir(shared_config['repo-cache-dir'])
    repo_dir = checkout_recipe_repo(recipe_repo, tag)

    # All subsequent work takes place within the recipe repo
    os.chdir(repo_dir)

    # Render
    recipe_version, recipe_build_string = get_rendered_version(
        package_name, recipe_subdir, build_environment, shared_config)
    print(
        f"Recipe version is: {package_name}-{recipe_version}-{recipe_build_string}")


    # Check our channel.  Did we already upload this version?
    package_info = {
        'pakage_name': package_name,
        'recipe_version': recipe_version,
        'recipe_build_string': recipe_build_string
    }
    if check_already_exists(package_name, recipe_version, recipe_build_string, shared_config):
        print(
            f"Found {package_name}-{recipe_version}-{recipe_build_string} on {shared_config['destination-channel']}, skipping build.")
        ret_dict = {'found': package_info}
    else:
        # Not on our channel.  Build and upload.
        build_recipe(package_name, recipe_subdir, conda_build_flags,
                     build_environment, shared_config)
        upload_package(package_name, recipe_version,
                       recipe_build_string, shared_config)
        ret_dict = {'built': package_info}
    return ret_dict


def checkout_recipe_repo(recipe_repo, tag):
    """
    Checkout the given repository and tag.
    Clone it first if necessary, and update any submodules it has.
    """
    try:
        repo_name = splitext(basename(recipe_repo))[0]

        cwd = abspath(os.getcwd())
        if not exists(repo_name):
            # assuming url of the form github.com/remote-name/myrepo[.git]
            remote_name = recipe_repo.split('/')[-2]
            subprocess.check_call(
                f"git clone -o {remote_name} {recipe_repo}", shell=True)
            os.chdir(repo_name)
        else:
            # The repo is already cloned in the cache,
            # but which remote do we want to fetch from?
            os.chdir(repo_name)
            remote_output = subprocess.check_output(
                "git remote -v", shell=True).decode('utf-8').strip()
            remotes = {}
            for line in remote_output.split('\n'):
                name, url, role = line.split()
                remotes[url] = name

            if recipe_repo in remotes:
                remote_name = remotes[recipe_repo]
            else:
                # Repo existed locally, but was missing the desired remote.
                # Add it.
                remote_name = recipe_repo.split('/')[-2]
                subprocess.check_call(
                    f"git remote add {remote_name} {recipe_repo}", shell=True)

            subprocess.check_call(f"git fetch {remote_name}", shell=True)

        print(f"Checking out {tag} of {repo_name} into {cwd}...")
        subprocess.check_call(f"git checkout {tag}", shell=True)
        subprocess.check_call(
            f"git pull --ff-only {remote_name} {tag}", shell=True)
        subprocess.check_call(
            f"git submodule update --init --recursive", shell=True)
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Failed to clone or update the repository: {recipe_repo}\n"
                           "Double-check the repo url, or delete your repo cache and try again.")

    print(f"Recipe checked out at tag: {tag}")
    print("Most recent commit:")
    subprocess.call("git log -n1", shell=True)
    os.chdir(cwd)

    return repo_name


def get_rendered_version(package_name, recipe_subdir, build_environment, shared_config):
    """
    Use 'conda render' to process a recipe's meta.yaml (processes jinja templates and selectors).
    Returns the version and build string from the rendered file.
    """
    print(f"Rendering recipe in {recipe_subdir}...")
    temp_meta_file = tempfile.NamedTemporaryFile(delete=False)
    temp_meta_file.close()
    render_cmd = (f"conda render"
                  f" --python={shared_config['python']}"
                  f" --numpy={shared_config['numpy']}"
                  f" {recipe_subdir}"
                  f" {shared_config['source-channel-string']}"
                  f" --file {temp_meta_file.name}")
    print('\t' + render_cmd)
    rendered_meta_text = subprocess.check_output(
        render_cmd, env=build_environment, shell=True).decode()
    meta = yaml.load(open(temp_meta_file.name, 'r'))
    os.remove(temp_meta_file.name)

    if meta['package']['name'] != package_name:
        raise RuntimeError(
            f"Recipe for package '{package_name}' has unexpected name: '{meta['package']['name']}'")

    render_cmd += " --output"
    rendered_filename = subprocess.check_output(
        render_cmd, env=build_environment, shell=True).decode()
    build_string_with_hash = rendered_filename.split('-')[-1].split('.')[0]

    return meta['package']['version'], build_string_with_hash


def check_already_exists(package_name, recipe_version, recipe_build_string, shared_config):
    """
    Check if the given package already exists on anaconda.org in the
    ilastik-forge channel with the given version and build string.
    """
    print(f"Searching channel: {shared_config['destination-channel']}")
    search_cmd = f"conda search --json  --full-name --override-channels --channel={shared_config['destination-channel']} {package_name}"
    print('\t' + search_cmd)
    try:
        search_results_text = subprocess.check_output(
            search_cmd, shell=True).decode()
    except Exception:
        # In certain scenarios, the search can crash.
        # In such cases, the package wasn't there anyway, so return False
        return False

    search_results = json.loads(search_results_text)

    if package_name not in search_results:
        return False

    for result in search_results[package_name]:
        if result['build'] == recipe_build_string and result['version'] == recipe_version:
            print("Found package!")
            return True
    return False


def build_recipe(package_name, recipe_subdir, build_flags, build_environment, shared_config):
    """
    Build the recipe.
    """
    print(f"Building {package_name}")
    build_cmd = (f"conda build {build_flags}"
                 f" --python={shared_config['python']}"
                 f" --numpy={shared_config['numpy']}"
                 f" {shared_config['source-channel-string']}"
                 f" {recipe_subdir}")
    print('\t' + build_cmd)
    try:
        subprocess.check_call(build_cmd, env=build_environment, shell=True)
    except subprocess.CalledProcessError as ex:
        print(f"Failed to build package: {package_name}", file=sys.stderr)
        sys.exit(1)


def upload_package(package_name, recipe_version, recipe_build_string, shared_config):
    """
    Upload the package to the ilastik-forge channel.
    """
    pkg_file_name = f"{package_name}-{recipe_version}-{recipe_build_string}.tar.bz2"

    pkg_file_path = BUILD_PKG_DIR / CONDA_PLATFORM / pkg_file_name
    if not os.path.exists(pkg_file_path):
        # Maybe it's a noarch package?
        pkg_file_path = BUILD_PKG_DIR / 'noarch' / pkg_file_name
    if not os.path.exists(pkg_file_path):
        raise RuntimeError(f"Can't find built package: {pkg_file_name}")

    upload_cmd = f"anaconda upload -u {shared_config['destination-channel']} {pkg_file_path}"
    print(f"Uploading {pkg_file_name}")
    print(upload_cmd)
    subprocess.check_call(upload_cmd, shell=True)


if __name__ == "__main__":
    #     import os
    #     from os.path import dirname
    #     os.chdir(dirname(__file__))
    #     sys.argv.append('recipe-specs.yaml')

    sys.exit(main())
