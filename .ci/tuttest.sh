#!/bin/bash

var_exsts() {
    if [ ! -f "$1" ]; then
        echo "$1 does not exist."
        exit 1
    fi
}

TMP_DIR=$(mktemp -d)
git clone . $TMP_DIR
cd $TMP_DIR
CONFIG="$(tuttest README.md config.yml)"
INSTALL=$(tuttest README.md install)
DEPENDENCIES=$(tuttest README.md dependencies)
RUN=$(tuttest README.md run)
RUN_UPDATE=$(tuttest README.md update-output)

if [[ "$CI" == 'true' ]]; then
    eval "$DEPENDENCIES"
fi
eval "$INSTALL"

rm plot.png
rm config.yml
echo "$CONFIG" > config.yml

eval "$RUN"
var_exsts plot.png
var_exsts table.md
var_exsts result.csv

printf "  cs2:\n    filename: \"result2.csv\" \n    format: \"csv\"" >> config.yml
eval "$RUN_UPDATE"
var_exsts result2.csv