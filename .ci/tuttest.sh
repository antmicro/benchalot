#!/bin/bash

assert_file_exists() {
    if [ ! -f "$1" ]; then
        echo "$1 does not exist."
        return 1
    fi
}
set -e

RUN=$(tuttest README.md run)

EXAMPLE_BASIC=$(tuttest README.md example-basic)
EXAMPLE_INTERMEDIATE="$(tuttest README.md example-intermediate)"
EXAMPLE_ADVANCED=$(tuttest README.md example-advanced)

SECTION_MATRIX=$(tuttest README.md section-matrix)
SECTION_EXCLUDE=$(tuttest README.md section-exclude)
SECTION_INCLUDE=$(tuttest  README.md section-include)
SECTION_RUN=$(tuttest README.md section-run)
SECTION_SYSTEM=$(tuttest README.md section-system)
SECTION_RESULTS=$(tuttest README.md section-results)

SPECIAL_OPTION_MUL=$(tuttest README.md special-option-mul)

CLI_HELP=$(tuttest README.md cli-help)
CLI_PLAN=$(tuttest README.md cli-plan)
CLI_RESULTS_FROM_CSV=$(tuttest README.md cli-results-from-csv)
CLI_INCLUDE=$(tuttest README.md cli-include)
CLI_SPLIT=$(tuttest README.md cli-split)
CLI_INCLUDE_FAILED=$(tuttest README.md cli-include-failed)
CLI_INCLUDE_OUTLIERS=$(tuttest README.md cli-include-outliers)

TMP_DIR=$(mktemp -d)
git clone . $TMP_DIR
cd $TMP_DIR

python3 -m  venv .venv
source .venv/bin/activate
pip install .

n_failed=0
n_passed=0

function test_passed(){
    echo "TEST PASSED."
    n_passed=$((n_passed + 1))
    rm output.log
}

function test_failed(){
    cat output.log
    echo "TEST FAILED!"
    n_failed=$((n_failed + 1))
    rm output.log
}

echo "RUNNING TEST CONFIG EXAMPLE BASIC..."
if {
    echo "$EXAMPLE_BASIC" > config.yml
    eval "$RUN" &> output.log
    assert_file_exists result.csv
    mv result.csv basic_result.csv
    rm output
}; then 
    test_passed
else
    test_failed
fi


echo "RUNNING TEST CONFIG EXAMPLE INTERMEDIATE..."
if {
    echo "$EXAMPLE_INTERMEDIATE" > config.yml
    eval "$RUN" &> output.log
    assert_file_exists plot.png
    assert_file_exists table.md
    assert_file_exists result.csv
    rm table.md
    rm result.csv
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CONFIG EXAMPLE ADVANCED..."
if {
    echo "$EXAMPLE_ADVANCED" &> config.yml
    eval "$RUN" &> output.log
    assert_file_exists file_size.csv
    assert_file_exists file_table.md
    rm file_size.csv
    rm file_table.md
    rm plot.png # remove plot from EXAMPLE_INTERMEDIATE, needed here for compression
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST SECTION TUTORIALS..."
if {
    rm config.yml
    echo "$SECTION_MATRIX" >> config.yml
    echo "$SECTION_EXCLUDE" >> config.yml
    echo "$SECTION_INCLUDE" >> config.yml
    echo "$SECTION_RUN" >> config.yml
    echo "$SECTION_SYSTEM" >> config.yml
    # Remove isolate CPUs line since it causes any line with chained commands '&&' to fail.
    sed -i '/isolate-cpus/d' config.yml
    if [ "$CI" == 'true' ]; then
        echo "    governor-performance: False" >> config.yml # cannot set governor in CI
    fi
    echo "$SECTION_RESULTS" >> config.yml
    printf "\n%s" "$SPECIAL_OPTION_MUL" | sed 's/^/    /' >> config.yml
    eval "$RUN" &> output.log
    assert_file_exists example.csv
    assert_file_exists example.md
    assert_file_exists example.html
    assert_file_exists example_scatter.png
    assert_file_exists example_box.png
    assert_file_exists example_violin.png
    assert_file_exists example_bar.png
    assert_file_exists plot_data1.png
    assert_file_exists plot_data2.png
    assert_file_exists plot_data3.png
    rm example.csv
    rm example.md
    rm example.html
    rm example_scatter.png
    rm example_box.png
    rm example_violin.png
    rm example_bar.png
    rm plot_data1.png
    rm plot_data2.png
    rm plot_data3.png
}; then 
    test_passed
else
    test_failed
fi

# Create test environment
cp basic_result.csv result.csv
echo "$EXAMPLE_BASIC" > config.yml
printf "results:\n    cs2:\n        filename: \"test_result.csv\" \n        format: \"csv\"" >> config.yml

echo "RUNNING TEST CLI HELP..."
if {
    eval "$CLI_HELP" &> output.log
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CLI PLAN..."
if {
    eval "$CLI_PLAN" &> output.log
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CLI RESULTS FROM CSV..."
if {
    eval "$CLI_RESULTS_FROM_CSV" &> output.log
    assert_file_exists test_result.csv
    rm test_result.csv
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CLI INCLUDE..."
if {
    eval $CLI_INCLUDE &> output.log
    assert_file_exists test_result.csv
    rm test_result.csv
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CLI INCLUDE FAILED..."
if {
    eval $CLI_INCLUDE_FAILED &> output.log
    assert_file_exists test_result.csv
    rm test_result.csv
}; then 
    test_passed
else
    test_failed
fi

echo "RUNNING TEST CLI INCLUDE OUTLIERS..."
if {
    eval $CLI_INCLUDE_OUTLIERS &> output.log
    assert_file_exists test_result.csv
    rm test_result.csv
}; then 
    test_passed
else
    test_failed
fi


echo "RUNNING TEST CLI SPLIT..."
if {
    echo "$EXAMPLE_INTERMEDIATE" > config.yml
    eval "$CLI_SPLIT" &> output.log
    assert_file_exists "out/config.yml.part0.yml"
    assert_file_exists "out/config.yml.part1.yml"

    # test if the configuration files are valid
    benchmarker "out/config.yml.part0.yml" -p &>> output.log
    benchmarker "out/config.yml.part1.yml" -p &>> output.log
}; then 
    test_passed
else
    test_failed
fi

echo "PASSED $n_passed/$((n_failed+n_passed)) TESTS"
if [ "$n_failed" -gt 0 ]; then
  exit 1
fi
