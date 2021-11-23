
# xFilter


[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/genomewalker/x-filter?include_prereleases&label=version)](https://github.com/genomewalker/x-filter/releases) [![x-filter](https://github.com/genomewalker/x-filter/workflows/xFilter_ci/badge.svg)](https://github.com/genomewalker/x-filter/actions) [![PyPI](https://img.shields.io/pypi/v/x-filter)](https://pypi.org/project/x-filter/) [![Conda](https://img.shields.io/conda/v/genomewalker/x-filter)](https://anaconda.org/genomewalker/x-filter)


A simple tool to calculate metrics from a BAM file and filter references to be used with Woltka

# Installation

We recommend having [**conda**](https://docs.conda.io/en/latest/) installed to manage the virtual environments

### Using pip

First, we create a conda virtual environment with:

```bash
wget https://raw.githubusercontent.com/genomewalker/x-filter/master/environment.yml
conda env create -f environment.yml
```

Then we proceed to install using pip:

```bash
pip install x-filter
```

### Using conda

```bash
conda install -c conda-forge -c bioconda -c genomewalker x-filter
```

### Install from source to use the development version

Using pip

```bash
pip install git+ssh://git@github.com/genomewalker/x-filter.git
```

By cloning in a dedicated conda environment

```bash
git clone git@github.com:genomewalker/x-filter.git
cd x-filter
conda env create -f environment.yml
conda activate x-filter
pip install -e .
```


# Usage

xFilter only needs a BAM file. For a complete list of options:

```
$ xFilter --help

usage: xFilter [-h] [-t THREADS] [-p PREFIX] [-l MIN_READ_LENGTH] [-n MIN_READ_COUNT] [-b MIN_EXPECTED_BREADTH_RATIO] [-a MIN_READ_ANI] [-c MIN_COVERAGE_EVENNESS] [-m SORT_MEMORY] [-r REFERENCE_LENGTHS]
                 [--debug] [--version]
                 bam

A simple tool to calculate metrics from a BAM file and filter references to be used with Woltka

positional arguments:
  bam                   BAM file containing aligned reads

optional arguments:
  -h, --help            show this help message and exit
  -t THREADS, --threads THREADS
                        Number of threads to use (default: 1)
  -p PREFIX, --prefix PREFIX
                        Prefix used for the output files (default: None)
  -l MIN_READ_LENGTH, --min-read-length MIN_READ_LENGTH
                        Minimum read length (default: 30)
  -n MIN_READ_COUNT, --min-read-count MIN_READ_COUNT
                        Minimum read count (default: 10)
  -b MIN_EXPECTED_BREADTH_RATIO, --min-expected-breadth-ratio MIN_EXPECTED_BREADTH_RATIO
                        Minimum expected breadth ratio (default: 0.5)
  -a MIN_READ_ANI, --min-read-ani MIN_READ_ANI
                        Minimum average read ANI (default: 90.0)
  -c MIN_COVERAGE_EVENNESS, --min-coverage-evenness MIN_COVERAGE_EVENNESS
                        Minimum coverage evenness (default: 0)
  -m SORT_MEMORY, --sort-memory SORT_MEMORY
                        Set maximum memory per thread for sorting; suffix K/M/G recognized (default: 1G)
  -r REFERENCE_LENGTHS, --reference-lengths REFERENCE_LENGTHS
                        File with references lengths (default: None)
  --debug               Print debug messages (default: False)
  --version             Print program version
```

One would run xFilter as:

```bash
xFilter --min-read-count 100 --min-expected-breadth-ratio 0.75 --min-read-ani 98 --sort-memory 1G --threads 16  c55d4e2df1.woltka.dedup.bam
```

**--min-read-count**: Minimum number of reads mapped to a reference in the BAM file

**--min-expected-breadth-ratio**: Minimum expected breadth ratio needed to keep a reference. This is based on the concepts defined [here](https://instrain.readthedocs.io/en/latest/important_concepts.html#detecting-organisms-in-metagenomic-data). I basically estimates the ratio between the observed and expected breadth, the closest to 1 the more evenly distributed the mapped reads are and we can be more confident that the genome was detected.

**--min-read-ani**: Minimum average read ANI that a reference has

**--sort-memory**: Memory used for each thread when sorting the filtered BAM file

**--threads**: Number of threads


