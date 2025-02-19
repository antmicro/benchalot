#!/bin/bash
set -e
TMP_DIR=$(mktemp -d)
cd $TMP_DIR

n_failed=0
n_passed=0
prev_failed=0

function benchalot_run() {
  echo "$1" > config.yml
  benchalot config.yml &> bench_log
  rm result.csv
  rm config.yml
}

function compare_order() {
  echo "$1" > order
  if ! cmp order $2; then
    set +e
    diff order $2 -y
    set -e
    cat bench_log
    echo "TEST FAILED"
    n_failed=$((n_failed + 1))
    echo ""
    rm order
    rm $2
    return 1
  else
    rm order
    rm $2
    return 0
  fi
}


function test() {
  echo "RUNNING  $1..."
  benchalot_run "$2"
  if compare_order "$3" output; then
    echo "TEST SUCCESS"
    n_passed=$((n_passed + 1))
  fi
  rm bench_log
}




test_order_simple=$(cat <<'EOF'
---
setup: [echo "setup" >> output]
prepare: [echo "prepare" >> output]
benchmark: [echo "benchmark" >> output]
conclude: [echo "conclude" >> output]
custom-metrics: [ test: echo "custom-metrics" >> output && echo 0]
cleanup: [echo "cleanup" >> output]
EOF
)
expected_order_simple=$(cat << 'EOF'
setup
prepare
benchmark
conclude
custom-metrics
cleanup
EOF
)
test "TEST ORDER SIMPLE" "$test_order_simple" "$expected_order_simple"

test_order_mul=$(cat <<'EOF'
---
setup: [echo "setup" >> output]
prepare: [echo "prepare" >> output]
benchmark: [echo "benchmark" >> output]
conclude: [echo "conclude" >> output]
custom-metrics: [ test: echo "custom-metrics" >> output && echo 0]
cleanup: [echo "cleanup" >> output]
samples: 3
EOF
)
expected_order_mul=$(cat << 'EOF'
setup
prepare
benchmark
conclude
custom-metrics
prepare
benchmark
conclude
custom-metrics
prepare
benchmark
conclude
custom-metrics
cleanup
EOF
)

test "TEST ORDER SAMPLES" "$test_order_mul" "$expected_order_mul"


test_order_cwd=$(cat <<'EOF'
---
matrix: 
  dir: ["dir1", "dir2", "dir3"]
cwd: "./{{dir}}"
setup: [echo $PWD/setup]
prepare: [echo $PWD/prepare]
benchmark: [echo $PWD/benchmark]
conclude: [echo $PWD/conclude]
custom-metrics: [ test: echo $PWD/custom-metrics && echo 0]
cleanup: [echo $PWD/cleanup]
save-output: output
EOF
)
expected_order_cwd=$(cat << EOF
$PWD/dir1/setup
$PWD/dir1/prepare
$PWD/dir1/benchmark
$PWD/dir1/conclude
$PWD/dir1/custom-metrics
0
$PWD/dir1/cleanup
$PWD/dir2/setup
$PWD/dir2/prepare
$PWD/dir2/benchmark
$PWD/dir2/conclude
$PWD/dir2/custom-metrics
0
$PWD/dir2/cleanup
$PWD/dir3/setup
$PWD/dir3/prepare
$PWD/dir3/benchmark
$PWD/dir3/conclude
$PWD/dir3/custom-metrics
0
$PWD/dir3/cleanup
EOF
)

mkdir dir1 dir2 dir3
test "TEST ORDER CWD" "$test_order_cwd" "$expected_order_cwd"
rmdir dir1 dir2 dir3


test_order_env=$(cat <<'EOF'
---
matrix:
  var: ["A", "B", "C"]
setup: [echo "setup $VAR" >> output]
prepare: [echo "prepare $VAR" >> output]
benchmark: [echo "benchmark $VAR" >> output]
conclude: [echo "conclude $VAR" >> output]
custom-metrics: [ test: echo "custom-metrics $VAR" >> output && echo 0]
cleanup: [echo "cleanup $VAR" >> output]
env:
  VAR: "{{var}}"
EOF
)

expected_order_env=$(cat << 'EOF'
setup A
prepare A
benchmark A
conclude A
custom-metrics A
cleanup A
setup B
prepare B
benchmark B
conclude B
custom-metrics B
cleanup B
setup C
prepare C
benchmark C
conclude C
custom-metrics C
cleanup C
EOF
)


test "TEST ORDER ENV" "$test_order_env" "$expected_order_env"


test_order_save_output=$(cat <<'EOF'
---
matrix:
  var: ["A", "B", "C"]
setup: ["echo setup {{var}}"]
prepare: ["echo prepare {{var}}"]
benchmark: ["echo benchmark {{var}}"]
conclude: ["echo conclude {{var}}"]
custom-metrics: [ test: "echo custom-metrics {{var}} && echo 0"]
cleanup: ["echo cleanup {{var}}"]
save-output: output{{var}}
EOF
)
expected_order_save_output_A=$(cat << 'EOF'
setup A
prepare A
benchmark A
conclude A
custom-metrics A
0
cleanup A
EOF
)

expected_order_save_output_B=$(cat << 'EOF'
setup B
prepare B
benchmark B
conclude B
custom-metrics B
0
cleanup B
EOF
)

expected_order_save_output_C=$(cat << 'EOF'
setup C
prepare C
benchmark C
conclude C
custom-metrics C
0
cleanup C
EOF
)

echo "RUNNING TEST ORDER SAVE-OUTPUT..."
benchalot_run "$test_order_save_output"
if compare_order "$expected_order_save_output_A" outputA; then
  if compare_order "$expected_order_save_output_B" outputB; then
    if compare_order "$expected_order_save_output_C" outputC; then
      echo "TEST SUCCESS"
      n_passed=$((n_passed + 1))
    fi
  else
    rm outputC
  fi
  else
    rm outputB
    rm outputC
fi
rm bench_log


test_order_multiline_config=$(cat << 'EOF'
---
matrix:
  var: ["A", "B", "C"]
setup: |
  echo "setup line 1 {{var}}" >> output
  echo "setup line 2 {{var}}" >> output
prepare: |
  echo "prepare line 1 {{var}}" >> output
  echo "prepare line 2 {{var}}" >> output
benchmark: |
  echo "benchmark line 1 {{var}}" >> output
  echo "benchmark line 2 {{var}}" >> output
conclude: |
  echo "conclude line 1 {{var}}" >> output
  echo "conclude line 2 {{var}}" >> output
cleanup: |
  echo "cleanup line 1 {{var}}" >> output
  echo "cleanup line 2 {{var}}" >> output
EOF
)

expected_order_multiline=$(cat << 'EOF'
setup line 1 A
setup line 2 A
prepare line 1 A
prepare line 2 A
benchmark line 1 A
benchmark line 2 A
conclude line 1 A
conclude line 2 A
cleanup line 1 A
cleanup line 2 A
setup line 1 B
setup line 2 B
prepare line 1 B
prepare line 2 B
benchmark line 1 B
benchmark line 2 B
conclude line 1 B
conclude line 2 B
cleanup line 1 B
cleanup line 2 B
setup line 1 C
setup line 2 C
prepare line 1 C
prepare line 2 C
benchmark line 1 C
benchmark line 2 C
conclude line 1 C
conclude line 2 C
cleanup line 1 C
cleanup line 2 C
EOF
)
test "TEST ORDER MULTILINE" "$test_order_multiline_config" "$expected_order_multiline"

echo "PASSED $n_passed/$((n_failed+n_passed)) TESTS"
if [ "$n_failed" -gt 0 ]; then
  exit 1
fi
