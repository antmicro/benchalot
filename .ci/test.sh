#!/bin/bash
set -e
python -m unittest

# TMP_DIR=$(mktemp -d)
# cd $TMP_DIR



test() {
  echo "$1" > config.yml
  benchmarker config.yml
  rm result.csv
  echo "$2" > order
  if ! cmp order output; then
    set +e
    diff order output -y
    echo "TEST FAILED"
    exit 1
  else
    rm output
    echo "TEST PASSED"
  fi
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
test "$test_order_simple" "$expected_order_simple"

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

test "$test_order_mul" "$expected_order_mul"


test_order_cwd=$(cat <<'EOF'
---
matrix: 
  dir: ["dir1", "dir2", "dir3"]
cwd: "./{{dir}}"
setup: [echo $PWD/setup]
prepare: [echo $PWD/prepare]
benchmark: [echo $PWD/benchmark]
conclude: [echo $PWD/conclude]
custom-metrics: [ test: echo $PWD/custom-metrics&& echo 0]
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
$PWD/dir1/cleanup
$PWD/dir2/setup
$PWD/dir2/prepare
$PWD/dir2/benchmark
$PWD/dir2/conclude
$PWD/dir2/custom-metrics
$PWD/dir2/cleanup
$PWD/dir3/setup
$PWD/dir3/prepare
$PWD/dir3/benchmark
$PWD/dir3/conclude
$PWD/dir3/custom-metrics
$PWD/dir3/cleanup
EOF
)

mkdir dir1 dir2 dir3
test "$test_order_cwd" "$expected_order_cwd"
rmdir dir1 dir2 dir3
