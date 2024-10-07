#!/bin/bash

assert_file_exists() {
    [ -f "$1" ] || exit 1
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