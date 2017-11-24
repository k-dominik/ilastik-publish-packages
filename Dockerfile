# will configure the image in the following way:
# /solvers <- /gurobi... /cplex...
# /license <- gurobi.lic

# Base image:
FROM condaforge/linux-anvil

# OVERRIDE with --build-arg GUROBI_KEY="...", ...
ARG GUROBI_KEY
ARG GUROBI_ARCHIVE="gurobi7.5.2_linux64.tar.gz"

# install some necessities:
# java and unzip are needed for cplex
RUN yum update -y && \
    yum install -y \
                    vim \
                    java-1.8.0-openjdk-headless.x86_64 \
                    unzip \
                    && \
    yum clean all

# get to the latest conda-build:
RUN export PATH="/opt/conda/bin:${PATH}" && \
    conda install --yes cmake && \
    conda install --yes conda-build --override-channels -c defaults

# Solver installation
# right now the folder solvers must be reachable for docker build (e.g. copy to this folder)
# and contain the solver files for gurobi and cplex
# Gurobi

# MODIFY FOR NEW VERSIONS
COPY solvers/${GUROBI_ARCHIVE} /solvers/${GUROBI_ARCHIVE}
RUN tar -xvf /solvers/${GUROBI_ARCHIVE} -C /opt
RUN ls /opt/gurobi752/linux64

# GUROBI-KEY has to be set via -env GUROBI_KEY=...
run printf "y\n/license" | /opt/gurobi752/linux64/bin/grbgetkey ${GUROBI_KEY}


# cplex..........
