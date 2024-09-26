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
Then pass configuration file's name as an argument.
For example, start the benchmark by typing this command:

```bash
python src/main.py config.yml
```


## Configuration

Benchmarker is configured using a YAML file, e.g.:

```yaml
---
matrix:
  thread: [2, 4, 8]
  commit: ["04b536d553a21219d1419820e35d8cd703561636", "32d369e077b7330022d8eda68bcbbfcd25b9e56a"]
  input: ["data1", "data2", "data3"]
run:
  before:
    - "cd ~/Documents/sleeper && git checkout $matrix.commit && make build"
  benchmark:
    - "~/Documents/sleeper/sleeper $matrix.thread $matrix.input"
  after:
    - "cd ~/Documents/sleeper && make clean"
output:
  csv:
    filename: "result.csv"
    format: "csv"
  plot:
    filename: "plot.png"
    format: "bar-chart"
    x-axis: input
    facet: commit
    color: thread
    width: 10
    height: 9
    dpi: 100
  table:
    format: "table-md"
    filename: "table.md"
    columns: ["commit", "input"]
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

`before` contains the commands to be executed before the benchmark. 
`benchmark` contains the commands to be benchmarked.
`after` contains the commands to be executed after the measurement. 
The `before` and `after` sections are optional.

### Output

In the `output` section user can specify desired output of the program.
Each subsection of the `output` corresponds to one output file described by `filename` and `format`.
Currently there are three supported formats: `csv`, `bar-plot` and `table-md`.

`csv` output will contain columns corresponding to variables and one column with benchmark results.

`bar-plot` will result in `.png` image containing the plot.
Configure using this options:
* `x-axis` (mandatory): contains name of the variable which will be used as x-axis on the plot.
* `facet` (optional): contains name of the variable which will be used to facet (divide into subplots) the plot.
* `width` (optional, default = 10in): width of resulting image in inches.
* `height` (optional, default = 9in): height of resulting image in inches.
* `dpi` (optional, default = 100): DPI of resulting image.

`table-md` will result in plain text file containing a markdown table. 
Configured using this options:
* `columns` (optional, default - include all columns): contains array of variable names which will be used to group the results in the table.

For example, the config above with result with this `plot.png`:

<img src="plot.png" alt="plot created automatically based on configuration file" width="700" height="630"/>

And this `table.md`:
```markdown
| commit                                   | input   |   time |
|:-----------------------------------------|:--------|-------:|
| 04b536d553a21219d1419820e35d8cd703561636 | data1   | 0.2901 |
| 04b536d553a21219d1419820e35d8cd703561636 | data2   | 0.4389 |
| 04b536d553a21219d1419820e35d8cd703561636 | data3   | 0.0097 |
| 32d369e077b7330022d8eda68bcbbfcd25b9e56a | data1   | 0.2929 |
| 32d369e077b7330022d8eda68bcbbfcd25b9e56a | data2   | 0.1468 |
| 32d369e077b7330022d8eda68bcbbfcd25b9e56a | data3   | 0.4097 |
```