# General Description

Benchmarker is a tool used for automatic benchmarking of software. 


User can be specify commands to be run before and after taking measurement to prepare and maintain environment of the measurement using configuration file.


# Usage

To use the program install and create python virutal environment:

```bash
sudo apt install python3-venv
python3 -m  venv .venv
source .venv/bin/activate
```

Configure the application by edditing the `config.yml` file. Then start the benchamrk by typing this command:

```bash
python src/main.py
```


## Configuration

Benchmarker is configured using a `config.yml` file placed inside the root directory of the project. 

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

Based on that config, Benchmarker will run a benchmark for each value specified in `matrix.*` fields.
It will then store the results in the `result.csv` file.
Commands specified as strings in `run` field will be executed with every substring beginning with `$matrix.` being substituted to the corresponding variable.
For each value of the variable, a run will be performed. 
`before` is used to change current commit of the project working directory and to build new version of the program. 
`benchmark` contains the commands to be measured with their arguments.
`after` section performs cleanup after the measurement. 

Only execution time of commands inside the `benchmark` section is stored in the output.  
