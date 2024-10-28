# General Description

Benchmarker is a tool used for automatic benchmarking of software. 


User can specify commands to be run before and after taking measurement to prepare the environment using a configuration file.

# Usage

To use the program, first install dependencies:
<!--name="dependencies"-->
```bash
apt install python3 pipx cpuset -y
```
then install the Benchmarker:
```bash
python3 -m pip install .
```

Configure the application by editing the YAML configuration file.
Then pass configuration file's name as an argument.
For example, start the benchmark by typing this command:
<!--name="run"-->
```bash
benchmarker config.yml
```

To regenerate the output without re-running benchmarks, use `--update-output`:
<!--name="update-output"-->
```bash
benchmarker config.yml --update-output result.csv
```

To see available command line arguments type:
<!--name="help-information"-->
```
benchmarker --help
```

## Configuration

Benchmarker is configured using a YAML file, e.g.:

<!-- name="config.yml" -->
```yaml
---
system:
  isolate-cpus: [0,1]
  disable-aslr: True
  governor-performance: False
matrix:
  thread: [2, 4, 8]
  tag: ["slow", "fast"]
  input: ["data1", "data2", "data3"]
run:
  samples: 3
  save-output: "run.log"
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

* `benchmark` contains the commands to be benchmarked.
* `before` (optional) contains the commands to be executed before the benchmark. 
* `after` (optional) contains the commands to be executed after the benchmark. 
* `before-all` (optional) contains the commands to be executed once before all of the benchmarks.
* `after-all` (optional) contains the commands to be executed once after all of the benchmarks.
* `samples` (optional, default = 1) defines how many times repeat each benchmark.
* `save-output` (optional, default = None) defines where to save the stdout and stderr of the benchmarked commands. If set to `"STDERR"` or `"STDOUT"`, the output will be printed to standard error or standard output respectively.
* `cwd` (optional) change working directory of the commands to specified location.
* `env` (optional) specify additional environmental variables to be used when running commands.
By default commands inherit Benchmarker's environment.
* `metrics` (optional, default = `["time"]`) a list of metrics to be gathered from benchmarked commands.
Built-in are: `time`, `stderr` and `stdout`.
Each metric is gathered independently.
User can also specify their own metric using `metric_name: command` syntax.
See: [Custom Metrics](#custom-metrics)

Commands in the `benchmark` section can be split into stages using this syntax:
```yaml
run:
    benchmark:
        stage-1:
            - "command1"
        stage-2:
            - "command2"
```
Benchmarker will take measurements for each stage separately.

If you want to use stages with custom metrics see: [Custom Metrics and Stages](#custom-metrics-and-stages).

### System

The `system` section allows the user to apply variance reduction measures.
When benchmarking in a regular system environment, external factors such as other processes or randomized memory layout can affect the measurements.
Options in this section aim to minimize some of the external factors. 
Using these options require Benchmarker to be run with root privileges.
The section is optional; if no options are specified, Benchmarker can be run without root.

* `isolate-cpus`: contains a list of CPUs which will be shielded from running processes other than benchmarks.
* `disable-aslr`: if set to `True`, will disable address space layout randomization. 
* `governor-performance`: if set to `True`, will set frequency governors of all (or isolated) CPUs to `performance`.

### Output

In the `output` section user can specify desired output of the program.
Each subsection of the `output` corresponds to one output file described by `filename` and `format`.
Currently there are three supported formats: `csv`, `bar-plot` and `table-md`.

`csv` output will contain columns corresponding to variables and one column with benchmark results.

`bar-plot` will result in a `.png` image containing the plot.
Configure using these options:
* `x-axis` (mandatory): contains name of the variable which will be used as x-axis on the plot.
* `y-axis` (optional, default = `time`): contains name of metric to be used as y-axis on the plot.
* `facet` (optional): contains name of the variable which will be used to facet (divide into subplots) the plot.
* `width` (optional, default = 10in): width of resulting image in inches.
* `height` (optional, default = 9in): height of resulting image in inches.
* `dpi` (optional, default = 100): DPI of resulting image.
`table-md` will result in a text file containing a markdown table. 
Configured using these options:
* `columns` (optional, default - include all columns): contains an array of variable names which will be used to group the results in the table.
* `result-column` (optional, default = `"time"`): name of a metric which will be included in the resulting table.

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

### Custom Metrics

Benchmarker allows usage of custom metrics.
To use a custom metric, specify the metric name and command in `run.metrics` using the syntax `metric_name: command`.
`command` will be executed after each run of `benchmark` section.
`command` should output results by printing them to standard output.

Example: Let's say we want to measure size difference between files compressed by `gzip`, `bzip2` and `xz`.
We can start by specifying the configuration:
 <!--name="size-config"-->
```yaml
---
matrix:
  compression: ["bzip2", "gzip", "xz"]
run:
  benchmark:
    - "$matrix.compression -c plot.png > compressed"
  after:
    - "rm compressed"
  metrics: 
    - "size": "stat -c %s compressed"
output:
  csv:
    filename: "file_size.csv"
    format: "csv"
  table:
    filename: "file_table.md"
    format: "table-md"
    result-column: size
```
Benchmarker will then execute `stat -c %s compressed` after commands in benchmark section and store stdout as the result. 
The size measurements are accessible under `size` name and can be specified for `table-md` as `result-colum`.

#### Custom Metrics and Stages

Standard syntax for specifying stages does not work with custom metrics.
To specify your own stages with custom metrics make sure that command prints formatted measurements formatted like `csv` file to `stdout`.
For example, if the custom metric command outputs this:
```csv
stage1,stage2
19.3,30.12
```
Benchmarker will store `19.3` as the measurement for `stage1` and `30.12` as the measurement for `stage2`.
Benchmarker will also combine `stage1` and `stage2` to create a column with their sum under the custom metric's name.
