# Benchmarker

Copyright (c) 2024-2025 [Antmicro](https://www.antmicro.com)


## Overview

Benchmarker is a tool used for automatic benchmarking of software. 
Benchmarker can be configured to execute multiple benchmarks with different parameters, aggregate their results and present them using tables and plots.

## Installation

To use Benchmarker, install it as a pip package.
If you plan on using [isolate-cpus](#system) option, install `cpuset`.

## Usage

To use Benchmarker first create [YAML configuration file](#configuration). 
Then pass configuration file's name as an argument.
For example, start the benchmark by typing this command:

<!--name="run"-->
```bash
benchmarker config.yml
```


## Configuration

Benchmarker is configured using a YAML file.
For example:

<!--name="example-basic"-->
```yaml
matrix:
    program: [gzip, bzip2, xz]
benchmark:
    - "{{program}} plot.png -c > output"
samples: 5
```

Benchmarker will use this configuration to run these three commands:

```bash
gzip plot.png -c > output
bzip2 plot.png -c > output
xz plot.png -c > output
```
Each command will be executed five times.
The summary containing min, median, and max execution will be then printed to the terminal.
Detailed results will be saved to `result.csv`.

Benchmarker is much more capable. 
For example look at the following configuration file:

<!-- name="example-intermediate" -->
```yaml
---
system:
  isolate-cpus: [0]
  disable-aslr: True
  disable-core-boost: True
  disable-smt: True
  governor-performance: False
matrix:
  thread: [2, 4, 8]
  tag: ["sleeper-v2.0", "sleeper-v2.2"]
  input: ["data1", "data2", "data3"]
samples: 3
save-output: "run.log"
setup:
- "git clone . ../{{tag}}"
- "cd ../{{tag}} && git checkout {{tag}} && make build"
benchmark:
- "../{{tag}}/sleeper {{thread}} {{input}}"
cleanup:
- "cd ../{{tag}} && make clean"
- "rm -rf ../{{tag}}"
results:
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

Benchmarker automatically builds and measures execution time of the program `sleeper` with different combinations of arguments. 
Then results are aggregated and, in addition to `result.csv`, two files are created - `plot.png` and `table.md`.

The `plot.png` will look like this:

<img src="plot.png" alt="plot created automatically based on configuration file" width="700" height="630"/>

And `table.md` like this:
```markdown
| tag          | mean time to process data1   | mean time to process data2   | mean time to process data3   |
|:-------------|:-----------------------------|:-----------------------------|:-----------------------------|
| sleeper-v2.0 | 0.005 ± 0.002                | 0.003 ± 0.001                | 0.004 ± 0.002                |
| sleeper-v2.2 | 0.003 ± 0.001                | 0.002 ± 0.000                | 0.003 ± 0.001                |
```

### Matrix

Benchmarker will run a benchmark for each combination of variable values specified in `matrix.*` fields.

<!-- name="section-matrix" -->
```yaml
matrix:
    thread: [2, 4, 8]
    tag: [sleeper-v2.0, sleeper-v2.2] 
    input: [data1, data2, data3]
```

Commands will have very substring in format `{{var_name}}` substituted to corresponding value.
For each combination of variable values, a run will be performed, e.g.:  
The above configuration will result in runs:  

```
thread = 2; input = "data1"; tag = "sleeper-v2.0"
thread = 4; input = "data1"; tag = "sleeper-v2.0"
thread = 8; input = "data1"; tag = "sleeper-v2.0"
[...]  
thread = 8; input = "data3"; tag = "sleeper-v2.2"
```

in total creating 18 combinations of variable values.

Matrix variables can [contain fields](#advanced-configuration).

#### Exclude

To exclude given variable combination, use `exclude` section:

<!-- name="section-exclude" -->
```yaml
exclude:
  - tag: sleeper-v2.0
    input: data1
```

#### Include

To run benchmarks with given variable value assignment without creating combinations, use `include` section:

<!-- name="section-include" -->
```yaml
include:
  - tag: sleeper-v2.1
    input: data1
    thread: 32
```

### Command Execution

Benchmarker has predefined execution order:

```
setup -> (prepare -> benchmark -> conclude -> custom-metrics) * samples -> cleanup
```

By default, only commands inside `benchmark` section are measured.
However, you can modify this behavior by using `custom-metrics`.

<!-- name="section-run" -->
```yaml
setup:                                                  # commands to be executed once, before 'prepare', for each combination of variable values
    - git clone . ../{{tag}}
prepare:                                                # commands to be executed for each sample before 'benchmark'
    - cd ../{{tag}} && git checkout {{tag}}
benchmark:                                              # commands to be benchmarked
    compilation:                                        # benchmarks can be divided into stages
        - cd ../{{tag}} && make build -s
    execution:
        - ../{{tag}}/sleeper {{thread}} {{input}}
conclude:                                               # contains the commands to be executed for each sample after 'benchmark'
    - cd ../{{tag}} && make clean
cleanup:                                                # contains the commands to be excetued once, after 'conclude/custom-metrics', for each combination of variable values
    - rm -rf ../{{tag}}

#  built-in metrics
metrics:
    - time              # measure time
    - utime             # measure user time
    - stime             # measure system time
    - rss               # measure resident set size
    - stdout            # treat stdout output of the command as the result
    - stderr            # treat stderr output of the command as the result

custom-metrics:         # specify your own metrics, for more information checkout Advanced Configuration section of README
    - threads: echo {{thread}}

samples: 5                      # how many times repeat each benchmark (default=1)
save-output: "{{datetime}}.log" # log file for command output, 'datetime' is special matrix variable defined by Benchmarker
cwd: "./"                       # change working directory of the commands to specified location, you can also use matrix variable in here
env:                            # specify additional environment variables to be used when running commands
    CC: gcc
    VAR_NAME: "{{input}}"       # use matrix variables to change the enviromnent for each benchmark
```

### System

The `system` section allows the user to apply variance reduction measures.
When benchmarking in a regular system environment, external factors such as other processes or randomized memory layout can affect the measurements.
Options in this section aim to minimize some of the external factors. 
Using these options require Benchmarker to be run with root privileges.
The section is optional; if no options are specified, Benchmarker can be run without root.

<!-- name="section-system" -->
```yaml
system:
    isolate-cpus: [0, 1]        # contains a list of CPUs which will be shielded from running processes other than benchmarks
    disable-aslr: True          # disable address space layout randomization
    disable-smt: True           # disable simultaneous multithreading (called hyper-threading on Intel CPUs
    disable-core-boost: True    # disable CPU boosting
    governor-performance: True  # set CPU frequency governor to `performance`
```

### Results

<!-- name="section-results" -->
```yaml
# Here are examples of available output formats.
results:
    # Results in a csv file in format that is compatible with the Benchmarker
    csv-table:
        format: csv
        filename: example.csv
        overwrite: false                 # If set to `true` will overwrite any existing file with the same name. If set to false (defualt) will backup the existing file.

    # Results in a text file containing a markdown table
    markdown-table:
        format: md
        filename: example.md
        columns: [tag, input, thread]   # Column names which will be used to group the results in the table. By default names of all variables are used.
        metrics: [time]                 # Metrics which will be included in the table. By default all metrics are included.
        pivot: "{{stage}} {{metric}}"   # Result column name pattern, containing names of the variables which will be used to create columns.
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
        x-axis: input   # Variable which will be used as x-axis on the plot.
        y-axis: time    # Metric which will be used as y-axis on the plot.
        facet: thread   # Variable which will be used to facet (divide into subplots) the plot.
        color: input    # Variable which will be used as color channel of the plot.
        width: 10       # Width of resulting image in inches.
        height: 9       # Height of resulting image in inches.
        dpi: 100        # DPI of resulting image.

    # Results in an image of a box plot.
    box-plot:
        format: box 
        filename: example_box.png
        y-axis: time

    # Results in an image of a violin plot.
    violin-plot:
        format: violin 
        filename: example_violin.png
        y-axis: time

    # Results in an image of a bar chart.
    bar-chart:
        format: bar 
        filename: example_bar.png
        # Option bar chart specific
        stat: median # Function which will determine bar height. Available are: `min`, `mean`, `median` and `max`.
        y-axis: time
```

Additionally, instead of using variable names you can use one of the following:
* `stage` - column containing stages' names.
* `failed` - column containing `True` or `False` depending on whether the benchmark failed.


#### Multiplying output

To create multiple outputs from one rule, you can use variables in filenames.

For example, to create a separate bar chart for each value of variable `tag`, your configuration should look like this:

<!-- name=special-option-mul" -->
```yaml
mul-plot:
  filename: "plot_{{input}}.png"
  format: "bar"
  x-axis: input
  y-axis: time
  facet: tag
  color: thread
  width: 10
  height: 9
  dpi: 100
```

If we add this section to the configuration above, Benchmarker will generate two files: `plot_slow.png` which visualizes benchmarks with `tag == slow`, and `plot_fast.png` which visualizes benchmarks with `tag == fast`.

### Advanced Configuration

This configuration file is used to measure size difference between a file compressed by `gzip`, `bzip2` and `xz`
It also measures how much time it takes to compress and decompress a file.

 <!--name="example-advanced"-->
```yaml
---
matrix:
  opt:                          # `opt` is compound variable, its sub-variables can be accessed using `opt.var_name`
    - compress: "bzip2"
      decompress: "bunzip2"
      ext: "bz2"
    - compress: "gzip"
      decompress: "gunzip"
      ext: "gz"
    - compress: "xz"
      decompress: "unxz"
      ext: "xz"

benchmark:                                                        # divide benchmark section into two stages `compress` and `decompress`
  compress:
    - "{{opt.compress}} -c plot.png > out.{{opt.ext}}"            # use `{{opt.compress}}` to compress the file
  decompress:
    - "{{opt.decompress}} -c out.{{opt.ext}} > {{opt.ext}}.png"   # use `{{opt.decompress}}` to decompress the file

custom-metrics:                               # specify the metric name and command using the syntax `metric_name: command`.
  - "size": "stat -c %s out.{{opt.ext}}"      # will be executed after commands in `after` section with stdout treated as the measurement
metrics:
  - "time"
cleanup:
  - rm out.{{opt.ext}}
  - rm {{opt.ext}}.png

results:
  csv:
    filename: "file_size.csv"
    format: "csv"
  table:
    filename: "file_table.md"
    format: "md"
    metrics: [size]             # size measurements are accessible under the `size` name
```

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
<!--name="cli-help"-->
```bash
benchmarker --help
```

To print command execution plan without running benchmarks, use `--plan`:
<!--name="cli-plan"-->
```bash
benchmarker config.yml --plan
```
Please note that the execution plan will not take number of samples into account.

To generate the output without re-running benchmarks, use `--results-from-csv`:
<!--name="cli-results-from-csv"-->
```bash
benchmarker config.yml --results-from-csv result.csv
```

To include previous results with the next benchmark, use `--include`:
<!--name="cli-include"-->
```bash
benchmarker config.yml --include result.csv
```

To split configuration file into many smaller ones, use `--split`:
<!--name="cli-split"-->
```bash
benchmarker config.yml --split tag
```

In case one of the benchmarks fails (its exit code is not equal 0) Benchmarker will filter out the failed results when creating outputs (the `csv` file will still include the failed benchmarks).
To generate outputs with failed benchmarks, use `--include-failed`:
<!--name="cli-include-failed"-->
```bash
benchmarker config.yml -r result.csv --include-failed
```


The Benchmarker will try to automatically detect and remove outliers (the `csv` file will still include them) using [modified Z-Score](http://d-scholarship.pitt.edu/7948/1/Seo.pdf).
To generate outputs with outliers, use `--include-outliers`:
<!--name="cli-include-outliers"-->
```bash
benchmarker config.yml -r result.csv --include-outliers
```
