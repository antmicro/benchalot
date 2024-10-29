#!/bin/bash

assert_file_exists() {
    if [ ! -f "$1" ]; then
        echo "$1 does not exist."
        exit 1
    fi
}

TMP_DIR=$(mktemp -d)
git clone . $TMP_DIR
cd $TMP_DIR
CONFIG="$(tuttest README.md config.yml)"
DEPENDENCIES=$(tuttest README.md dependencies)
RUN=$(tuttest README.md run)
HELP_INFORMATION=$(tuttest README.md help-information)
RUN_UPDATE=$(tuttest README.md update-output)
RUN_INCLUDE=$(tuttest README.md include)
RUN_SPLIT=$(tuttest README.md split)
SIZE_CONFIG=$(tuttest README.md size-config)
if [ "$CI" == 'true' ]; then
    eval "$DEPENDENCIES"
fi
python3 -m  venv .venv
source .venv/bin/activate
pip install .
eval "$HELP_INFORMATION"

echo "$CONFIG" > config.yml
eval "$RUN"
assert_file_exists plot.png
assert_file_exists table.md
assert_file_exists result.csv
mv plot.png previous.png

printf "  cs2:\n    filename: \"result2.csv\" \n    format: \"csv\"" >> config.yml
eval "$RUN_UPDATE"
assert_file_exists result2.csv
cmp plot.png previous.png
ret=$?
if [ $ret -ne 0 ]; then
    echo "Plots are not the same."
    exit 1
fi

echo "$SIZE_CONFIG" > config.yml
benchmarker config.yml
assert_file_exists file_size.csv
rm result.csv
mv file_size.csv result.csv
eval $RUN_INCLUDE
echo "$CONFIG" > config.yml
eval $RUN_SPLIT
assert_file_exists "out/config.yml.part0.yml"
assert_file_exists "out/config.yml.part1.yml"
