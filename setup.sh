#!/usr/bin/env bash
set -e

SINGULARITY_BIN="/opt/ohpc/pub/libs/singularity/3.7.1/bin/singularity"
XFCE_CONTAINER="/gscratch/ece/xfce_singularity/xfce.sif"

$SINGULARITY_BIN exec $XFCE_CONTAINER \
    pip3 install --user setuptools && \
    pip3 install --user wheel && \
    pip3 install --user psutil
