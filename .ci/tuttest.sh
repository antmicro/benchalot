#!/bin/bash

TMP_DIR=$(mktemp -d)
git clone . $TMP_DIR
cd $TMP_DIR
CONFIG="$(tuttest README.md config.yml)"
INSTALL=$(tuttest README.md install)
DEPENDENCIES=$(tuttest README.md dependencies)
RUN=$(tuttest README.md run)
RUN_UPDATE=$(tuttest README.md update-output)

if [ "$CI" == 'true' ]; then
    eval "$DEPENDENCIES"
fi
eval "$INSTALL"

echo "$CONFIG" > config.yml

eval "$RUN"
[ -f "plot.png" ] || exit 1
[ -f "table.md" ] || exit 1
[ -f "result.csv" ] || exit 1
mv plot.png previous.png

printf "  cs2:\n    filename: \"result2.csv\" \n    format: \"csv\"" >> config.yml
eval "$RUN_UPDATE"
[ -f "result2.csv" ] || exit 1
cmp plot.png previous.png

[ $? -ne 0 ] || exit 1