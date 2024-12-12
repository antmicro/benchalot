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


## Configuration

Benchmarker is configured using a YAML file, e.g.:

<!-- name="config.yml" -->
```yaml
---
system:
  isolate-cpus: [0,1]
  disable-aslr: True
  disable-core-boost: True
  disable-smt: True
  governor-performance: False
matrix:
  thread: [2, 4, 8]
  tag: ["slow", "fast"]
  input: ["data1", "data2", "data3"]
run:
  samples: 3
  save-output: "run.log"
  before-all:
    - "git clone . ../{{tag}}"
    - "cd ../{{tag}} && git checkout {{tag}} && make build"
  benchmark:
    - "../{{tag}}/sleeper {{thread}} {{input}}"
  after-all:
    - "cd ../{{tag}} && make clean"
    - "rm -rf ../{{tag}}"
output:
  csv:
    filename: "result.csv"
    format: "csv"
  plot:
    filename: "plot.png"
    format: "bar"
    x-axis: input
    facet: tag
    color: thread
    width: 10
    height: 9
    dpi: 100
  table:
    format: "md"
    filename: "table.md"
    columns: ["tag"]
    pivot: "{{metric}} to process {{input}}"
    stats: ["mean", "std"]
```

The config above will generate this `plot.png`:

<img src="plot.png" alt="plot created automatically based on configuration file" width="700" height="630"/>

And this `table.md`:
```markdown
| tag   | mean time to process data1   | mean time to process data2   | mean time to process data3   |
|:------|:-----------------------------|:-----------------------------|:-----------------------------|
| slow  | 0.474 ± 0.235                | 0.222 ± 0.087                | 0.508 ± 0.247                |
| fast  | 0.362 ± 0.166                | 0.212 ± 0.081                | 0.475 ± 0.229                |
```

### Matrix

Based on that config, Benchmarker will run a benchmark for each value specified in `matrix.*` fields.
Commands specified as strings in `run` field will be executed with every substring with `{{var_name}}` being substituted to corresponding value.
For each combination of variable values, a run will be performed, e.g.:  
The above configuration will result in runs:  
`thread = 2; input = "data1"; tag = "slow"`  
`thread = 4; input = "data1"; tag = "slow"`  
`thread = 8; input = "data1"; tag = "slow"`  
[...]  
`thread = 8; input = "data3"; tag = "fast"`
in total creating 18 combinations of variable values.
If there is no `matrix` section, Benchmarker will execute the `run` section once.

#### Exclusions

To exclude given variable values combination, use `exclusions` section:

<!-- name="exclusions" -->
```yaml
exclusions:
  - tag: slow
    input: data1
  - tag: fast
    thread: 2
```
Benchmarker will not create benchmarks for these value combinations.

### Run

* `benchmark` contains the commands to be benchmarked.
* `before` (optional) contains the commands to be executed before the benchmark. 
* `after` (optional) contains the commands to be executed after the benchmark. 
* `before-all` (optional) contains the commands to be executed once before all of the benchmarks.
* `after-all` (optional) contains the commands to be executed once after all of the benchmarks.
* `samples` (optional, default = 1) defines how many times repeat each benchmark.
* `save-output` (optional, default = None) defines where to save the stdout and stderr of the benchmarked commands. If set to `"STDERR"` or `"STDOUT"`, the output will be printed to standard error or standard output respectively.
* `cwd` (optional) change working directory of the commands to specified location.
* `env` (optional) specify additional environment variables to be used when running commands.
By default commands inherit Benchmarker's environment.
* `metrics` (optional, default = `["time"]`) a list of metrics to be gathered from benchmarked commands.
Built-in are: `time`, `stderr` and `stdout`.
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
* `disable-smt`: if set to `True`, will disable simultaneous multithreading (called hyper-threading on Intel CPUs).
* `disable-core-boost`: if set to `True`, will disable CPU boosting.
* `governor-performance`: if set to `True`, will set frequency governors of all (or isolated) CPUs to `performance`.

### Output

<!-- name="output" -->
```yaml
---
# Here are examples of available output formats.
output:
    # Results in a csv file with a format that is compatible with the Benchmarker
    csv-table:
        format: csv
        filename: example.csv

    # Results in a text file containing a markdown table
    markdown-table:
        format: md
        filename: example.md
        columns: [tag, input, thread] # Column names which will be used to group the results in the table. By default names of all variables are used.
        metrics: [time] # Metrics which will be included in the table. By default all metrics are included.
        pivot: "{{stage}} {{metric}}" # Result columns' name pattern, containing names of the variables which will be used to create columns.
        stats: ["min", "median", "max"] # Statistics which will be calculated for each result column. Available are: `min`, `max`, `mean`, `std` and `relative`.

    # HTML version of the `md` format.
    html-table:
        format: html
        filename: example.html

    # Results in an image of a scatter plot. 
    scatter-plot:
        format: scatter 
        filename: example_scatter.png
        # Options that are common for all the plots:
        x-axis: input # Variable which will be used as x-axis on the plot.
        y-axis: time # Metric which will be used as y-axis on the plot.
        facet: thread # Variable which will be used to facet (divide into subplots) the plot.
        color: input # Variable which will be used as color channel of the plot.
        width: 10 # Width of resulting image in inches.
        height: 9 # Height of resulting image in inches.
        dpi: 100 # DPI of resulting image.

    # Results in an image of a box plot.
    box-plot:
        format: box 
        filename: example_box.png

    # Results in an image of a violin plot.
    violin-plot:
        format: violin 
        filename: example_violin.png

    # Results in an image of a bar chart.
    bar-chart:
        format: bar 
        filename: example_bar.png
        # Option bar chart specific
        stat: median # Function which will determine bar height. Available are: `min`, `mean`, `median` and `max`.
```

Additionally, instead of using variable names you can use one of the following:
* `benchmark_date` - time stamp (date and hour) of when the benchmarks completed.
* `stage` - column containing stages' names.
* `has_failed` - column containing `True` or `False` depending on whether the benchmark failed.


#### Multiplying output

To create multiple outputs from one rule, you can use variables in filenames.

For example, to create a separate bar chart for each value of variable `tag`, your configuration should look like this:

<!-- name="mul" -->
```
plot2:
  filename: "plot_{{tag}}.png"
  format: "bar"
  x-axis: input
  facet: tag
  color: thread
  width: 10
  height: 9
  dpi: 100
```

If we add this section to the configuration above, Benchmarker will generate two files: `plot_slow.png` which visualizes benchmarks with `tag == slow`, and `plot_fast.png` which visualizes benchmarks with `tag == fast`.

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
    - "{{compression}} -c plot.png > {{compression}}.out"
  metrics: 
    - "size": "stat -c %s {{compression}}.out"
  after-all:
    - rm {{compression}}.out
output:
  csv:
    filename: "file_size.csv"
    format: "csv"
  table:
    filename: "file_table.md"
    format: "md"
    metrics: [size]
```
Benchmarker will then execute `stat -c %s {{compression}}.out` after commands in benchmark section and store stdout as the result. 
The size measurements are accessible under `size` name and can be specified for `md` as `result-colum`.

#### Custom Metrics and Stages

Standard syntax for specifying stages does not work with custom metrics.
To specify your own stages with custom metrics make sure that command prints formatted measurements formatted like `csv` file to `stdout`.
For example, if the custom metric command outputs this:
```csv
stage1,stage2
19.3,30.12
```
Benchmarker will store `19.3` as the measurement for `stage1` and `30.12` as the measurement for `stage2`.

## CLI

To see available command line arguments type:
<!--name="help-information"-->
```
benchmarker --help
```

To regenerate the output without re-running benchmarks, use `--update-output`:
<!--name="update-output"-->
```bash
benchmarker config.yml --update-output result.csv
```

To include previous results with the next benchmark, use `--include`:
<!--name="include"-->
```bash
benchmarker config.yml --include result.csv
```

To split configuration file into many smaller ones, use `--split`:
<!--name="split"-->
```bash
benchmarker config.yml --split tag
```

In case one of the benchmarks fails (its exit code is not equal 0) Benchmarker will filter out the failed results when creating outputs (the `csv` file will still include the failed benchmarks).
To generate outputs with failed benchmarks, use `--include-failed`:
<!--name="failed"-->
```bash
benchmarker config.yml --u result.csv --include-failed
```


The Benchmarker will try to automatically detect and remove outliers (the `csv` file will still include them) using (modified Z-Score)[http://d-scholarship.pitt.edu/7948/1/Seo.pdf].
To generate outputs with outliers, use `--include-outliers`:
<!--name="outliers"-->
```bash
benchmarker config.yml --u result.csv --include-outliers
```
