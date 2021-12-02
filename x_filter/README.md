
# xFilter: a BLASTx filtering tool


[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/genomewalker/x-filter?include_prereleases&label=version)](https://github.com/genomewalker/x-filter/releases) [![x-filter](https://github.com/genomewalker/x-filter/workflows/xFilter_ci/badge.svg)](https://github.com/genomewalker/x-filter/actions) [![PyPI](https://img.shields.io/pypi/v/x-filter)](https://pypi.org/project/x-filter/) [![Conda](https://img.shields.io/conda/v/genomewalker/x-filter)](https://anaconda.org/genomewalker/x-filter)


A simple tool to filter BLASTx results with special emphasis on ancient DNA studies. xFilter implements the same filtering approach as [FAMLI](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-020-03802-0) but adds a couple of features designed for the annotation of ancient DNA short reads. [FAMLI](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-020-03802-0) solved one the principal problems when annotating short reads by iteratively assigning multi-mapped reads to the most likely true protein. You can find more information [here](https://www.minot.bio/home/2018/4/4/famli).

In addition to the filter that removes references with uneven coverage, xFilter allows to filter them based on a scaled version of the expected breadth of coverage, similar to the one described in [inStrain](https://instrain.readthedocs.io/en/latest/important_concepts.html#detecting-organisms-in-metagenomic-data). Furthermore, xFilter allows to aggregate the coverage values of the filtered references into higher categories, like KEGG orthologs or viral genomes.

For the BLASTx searches we recommend to use [MMSseqs2](https://github.com/soedinglab/MMseqs2) with parameters optimized for ancient DNA data as described [here](#)

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

xFilter uses a BLASTx m8 formatted file containing aligned reads to references. It has to contain query and subject lengths. For a complete list of options:

```
$ xFilter --help

usage: xFilter [-h] [-i INPUT] [-t THREADS] [-p PREFIX] [-n ITERS] [-e EVALUE] [-s SCALE] [-b BITSCORE] [-f FILTER]
               [--breadth BREADTH] [--breadth-expected-ratio BREADTH_EXPECTED_RATIO] [--depth DEPTH]
               [--depth-evenness DEPTH_EVENNESS] [-m MAPPING_FILE] [--no-trim] [--debug] [--version]

A simple tool to filter BLASTx m8 files using the FAMLI algorithm

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        A blastx m8 formatted file containing aligned reads to references. It has to contain query and
                        subject lengths (default: None)
  -t THREADS, --threads THREADS
                        Number of threads to use (default: 1)
  -p PREFIX, --prefix PREFIX
                        Prefix used for the output files (default: None)
  -n ITERS, --n-iters ITERS
                        Number of iterations for the FAMLI-like filtering (default: 25)
  -e EVALUE, --evalue EVALUE
                        Evalue where to filter the results (default: 1e-10)
  -s SCALE, --scale SCALE
                        Scale to select the best weithing alignments (default: 0.9)
  -b BITSCORE, --bitscore BITSCORE
                        Bitscore where to filter the results (default: 60)
  -f FILTER, --filter FILTER
                        Which filter to use. Possible values are: breadth, depth, depth_evenness,
                        breadth_expected_ratio (default: breadth_expected_ratio)
  --breadth BREADTH     Breadth of the coverage (default: 0.5)
  --breadth-expected-ratio BREADTH_EXPECTED_RATIO
                        Expected breath to observed breadth ratio (scaled) (default: 0.5)
  --depth DEPTH         Depth to filter out (default: 0.1)
  --depth-evenness DEPTH_EVENNESS
                        Reference with higher evenness will be removed (default: 1.0)
  -m MAPPING_FILE, --mapping-file MAPPING_FILE
                        File with mappings to genes for aggregation (default: None)
  --no-trim             Deactivate the trimming for the coverage calculations (default: True)
  --debug               Print debug messages (default: False)
  --version             Print program version
```

One would run xFilter as:

```bash
xFilter --input xFilter-1M-test.m8.gz --bitscore 60 --evalue 1e-5 --filter breadth_expected_ratio --breadth-expected-ratio 0.4 --n-iters 25 --mapping-file ko_gene_list.tsv.gz --threads 8
```

**--input**: A BLASTx tabular output with the query and subject lengths.

**--bitscore**: Bitscore where to filter the BLASTx results.

**--evalue**: Evalue where to filter the BLASTx results.

**--filter**: Which filter to use to filter the references. We have the following options:
 - depth: Filter out references with a depth below a given threshold. 
 - depth_evenness: Filter out references with a depth evenness below a given threshold. This is FAMLI's approach (SD/MEAN)
 - breadth: Filter out references with a breadth below a given threshold.
 - breadth_expected_ratio: Filter out references with a breadth below the scaled observed breadth to expected breadth ratio as in _(breadth/(1 - e<sup>-coverage</sup>)) &#215; breadth_. 

**--breadth-expected-ratio**: The observed breadth to expected breadth ratio (scaled).

**--mapping-file**: File with mappings to genes for aggregation. It contains two columns: the gene name and the grouping.

**--threads**: Number of threads

xFilter by default will trim the coverage values on both 5' and 3' ends based on the average read length (in amino acid) mapped to each query. This can be deactivated with the **--no-trim** option.

xFilter will generate the following files:
 - {prefix}**_multimap.tsv.gz**: This file contains the filtered BLASTx results after removing non-well supported references and multi-mappings.
 - {prefix}**_cov-stats.tsv.gz**: This file contains the coverage statistics of the references after the filtering. It contains the following columns:
   - **reference**: Reference name
   - **depth_mean**: Coverage mean
   - **depth_std**: Coverage standard deviation
   - **depth_evenness**: Coverage evenness (SD/MEAN)
   - **breadth**: Breadth of coverage
   - **breadth_expected**: Expected breadth of coverage
   - **breadth_expected_ratio**: Observed breadth to expected breadth ratio (scaled)
   - **n_alns**: Number of alignments
  - {prefix}**_group-abundances.tsv.gz**: If a mapping file is provided, it reports:
    - **group**: Group name
    - **mean**: Mean coverage values
    - **std**: Standard deviation of coverage values
    - **median**: Median coverage values
    - **sum**: Sum of coverage values
    - **n_genes**: Number of genes in the group

