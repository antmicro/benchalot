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
INSTALL=$(tuttest README.md install)
DEPENDENCIES=$(tuttest README.md dependencies)
RUN=$(tuttest README.md run)
RUN_UPDATE=$(tuttest README.md update-output)
HELP_INFORMATION=$(tuttest README.md help-information)
SIZE_CONFIG=$(tuttest README.md size-config)
SIZE_C=$(tuttest README.md size-c)
eval "$HELP_INFORMATION"
if [ "$CI" == 'true' ]; then
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

wget https://github.com/garrett/Tux/blob/main/tux-large.png -O tux.svg
wget https://upload.wikimedia.org/wikipedia/en/2/22/Heckert_GNU_white.svg -O gnu.svg
echo "$SIZE_C" > measure_size_diff.c
gcc measure_size_diff.c  -o measure_size_diff

echo "$SIZE_CONFIG" > size_config.yml

python src/main.py size_config.yml

assert_file_exists file_sizes.csv
assert_file_exists size_diff_table.md