# General Description

Benchmarker is a tool used for automatic benchmarking of software. 


User can specify commands to be run before and after taking measurement to prepare the environment using a configuration file.

# Usage

To use the program install and create a Python virtual environment:

<!--name="install"-->
```bash
apt install python3-venv cpuset sudo linux-cpupower -y
python3 -m  venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure the application by editing the YAML configuration file.
Then pass configuration file's name as an argument.
For example, start the benchmark by typing this command:
<!--name="run"-->
```bash
sudo .venv/bin/python src/main.py config.yml
```


## Configuration

Benchmarker is configured using a YAML file, e.g.:

<!-- name="config.yml" -->
```yaml
---
options:
  isolate-cpus: [0,1]
  disable-aslr: True
  governor-performance: False
matrix:
  thread: [2, 4, 8]
  tag: ["slow", "fast"]
  input: ["data1", "data2", "data3"]
run:
  samples: 3
  before:
    - "git clone . ../sleeper"
    - "cd ../sleeper && git checkout $matrix.tag && make build"
  benchmark:
    - "../sleeper/sleeper $matrix.thread $matrix.input"
  after:
    - "cd ../sleeper && make clean"
    - "rm -rf ../sleeper"
output:
  csv:
    filename: "result.csv"
    format: "csv"
  plot:
    filename: "plot.png"
    format: "bar-chart"
    x-axis: input
    facet: tag
    color: thread
    width: 10
    height: 9
    dpi: 100
  table:
    format: "table-md"
    filename: "table.md"
    columns: ["tag", "input"]
```

### Matrix

Based on that config, Benchmarker will run a benchmark for each value specified in `matrix.*` fields.
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
If there is no `matrix` section, Benchmarker will execute the `run` section once.

### Run
`samples` (optional, default = 1) defines how many times repeat each benchmark.
`before` contains the commands to be executed before the benchmark. 
`benchmark` contains the commands to be benchmarked.
`after` contains the commands to be executed after the measurement. 
The `before` and `after` sections are optional.

### Output

In the `output` section user can specify desired output of the program.
Each subsection of the `output` corresponds to one output file described by `filename` and `format`.
Currently there are three supported formats: `csv`, `bar-plot` and `table-md`.

`csv` output will contain columns corresponding to variables and one column with benchmark results.

`bar-plot` will result in a `.png` image containing the plot.
Configure using these options:
* `x-axis` (mandatory): contains name of the variable which will be used as x-axis on the plot.
* `facet` (optional): contains name of the variable which will be used to facet (divide into subplots) the plot.
* `width` (optional, default = 10in): width of resulting image in inches.
* `height` (optional, default = 9in): height of resulting image in inches.
* `dpi` (optional, default = 100): DPI of resulting image.

`table-md` will result in a text file containing a markdown table. 
Configured using these options:
* `columns` (optional, default - include all columns): contains an array of variable names which will be used to group the results in the table.

For example, the config above will generate this `plot.png`:

<img src="plot.png" alt="plot created automatically based on configuration file" width="700" height="630"/>

And this `table.md`:
```markdown
| tag   | input   |     mean |   median |       std |
|:------|:--------|---------:|---------:|----------:|
| fast  | data1   | 0.292805 | 0.251214 | 0.165203  |
| fast  | data2   | 0.147003 | 0.125923 | 0.0827682 |
| fast  | data3   | 0.409555 | 0.350952 | 0.231543  |
| slow  | data1   | 0.409459 | 0.350861 | 0.231534  |
| slow  | data2   | 0.152782 | 0.130948 | 0.0860583 |
| slow  | data3   | 0.438692 | 0.376356 | 0.248082  |
```