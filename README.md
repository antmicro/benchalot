# General Description

Benchmarker is a tool used for automatic benchmarking of software. 


User can specify commands to be run before and after taking measurement to prepare the environment using a configuration file.

# Usage

To use the program install and create a Python virtual environment:

```bash
sudo apt install python3-venv
python3 -m  venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure the application by editing the YAML configuration file.
Pass configuration file's name as an argument.
For example, start the benchmark by typing this command:

```bash
python src/main.py config.yml
```


## Configuration

Benchmarker is configured using a YAML file. 
Example:

```yaml
---

output:
  name: "result.csv"
  format: "csv"
matrix:
  thread: [2, 4, 8]
  input: ["data1", "data2", "data3"]
  commit: ["abc123", "cba321"]
run:
  before:
    - "cd ~/repository/ && git checkout $matrix.commit && make build"
  benchmark:
    - "~/repository/bin/sort --threads=$matrix.thread $matrix.input"
  after:
    - "cd ~/repository/ && make clean"

```

Based on that config, Benchmarker will run benchmark for each value specified in `matrix.*` fields.
It will then store the results in the `output.name` file.
Commands specified as strings in `run` field will be executed with every substring beginning with `$matrix.` being substituted to corresponding variable.
For each combination of variable values, a run will be performed, e.g.:  
The above configuration will result in runs:  
`$matrix.thread = 2; $matrix.input = "data1"; $matrix.commit = "abc123"`  
`$matrix.thread = 4; $matrix.input = "data1"; $matrix.commit = "abc123"`  
`$matrix.thread = 8; $matrix.input = "data1"; $matrix.commit = "abc123"`  
[...]  
`$matrix.thread = 8; $matrix.input = "data3"; $matrix.commit = "cba321"`
in total performing 27 benchmarks.
If there is no `matrix` section, Benchmarker will execute `run` section once.

`before` contains commands to be executed before the benchmark. 
`benchmark` contains the commands to be benchmarked.
`after` contains commands to be executed after the measurement. 
The `before` and `after` sections are optional.