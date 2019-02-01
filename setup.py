from setuptools import setup, find_packages

setup(
    name="publish-conda-stack",
    version="0.2.1dev2",
    author="Stuart Berg, Carsten Haubold",
    author_email="team@ilastik.org",
    license="MIT",
    description="Short description",
    # long_description=description,
    # url='https://...',
    package_dir={"": "src"},
    packages=find_packages("./src"),
    include_package_data=True,
    install_requires=["argcomplete", "conda-build", "pyyaml"],
    entry_points={
        "console_scripts": ["publish-conda-stack = publish_conda_stack.__main__:main"]
    },
)
