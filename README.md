# fastq-profiler

__fastq-profiler__ is a command line utility for keeping track of and organizing fastqs. fastq-profiler generates summary statistics and stores data using the file hash in [Google Datastore](https://cloud.google.com/datastore/). 

The program stores data in Google Datastore because it is centralized - allowing you to profile fastqs locally, or within cluster environments and elsewhere without having to track/combine files. Importantly, when duplicates are identified, fastq-profiler keeps track of both locations, allowing you to identify and track their locations.

### Installation

```
Coming soon.
```

### Setup

1. Setup an account with google cloud.
2. Authorize Google Cloud using the [gcloud SDK](https://cloud.google.com/sdk/):

```
gcloud auth login
```

3. Set your project and default Google Datastore "kind" using:

```
fq set <project> <kind>
```

### Data

__fastq-profiler__ uses an md5sum of each fastq processed as a `name` (analogous to a key) in Google Datastore and stores its associated data as properties under a `fastq` kind in Google Datastore. Resulting data looks like this:

![fqprofile-datastore](datastore.png)

The following properties are stored:

1. `key` Hash of the file
1. `filename` Fastq file name
1. `path_filename` - Full path of Fastq file (in every location identified)
1. `locations_count` - Count of identified locations.
1. `date_created` Earliest identified date created
1. `flowcell_lane` Flowcell lane
1. `filesize` - Filesize in bytes
1. `hfilesize` - Filesize in human readable form
1. `total_reads` - Read count
1. `[ATCGN]_count` - Base counts
1. `GC_content` - GC content
1. `min_length` - Minimum read length
1. `avg_length` - Average read length
1. `max_length` - maximum read length

__Additional fields included if applicable__

1. `instrument` Instrument name if available
1. `flowcell_lane` 
1. `flowcell_number`
1. `run_id`
1. `pair` 1/2 for paired end sequencing.
1. `barcode` Index/barcode of read for pooled sequencing
1. `control_bits` 

__Illumina Filename__

If the filename follows the [Illumina filename conventions](http://support.illumina.com/content/dam/illumina-support/help/BaseSpaceHelp_v2/Content/Vault/Informatics/Sequencing_Analysis/BS/swSEQ_mBS_FASTQFiles.htm), these items will be parsed out as well:

1. `illumina_filename_sample`
1. `illumina_filename_barcode_sequence` OR `illumina_filename_sample_number`
1. `illumina_filename_lane`
1. `illumina_filename_read`
1. `illumina_filename_set_number`

_For example:_

`EA-CFB-2-421_S1_L001_R1_001.fastq.gz` would be parsed into:

1. `illumina_filename_sample` = EA-CFB-2-421U
1. `illumina_filename_sample_number` = S1
1. `illumina_filename_lane` = L001
1. `illumina_filename_read` =  R1
1. `illumina_filename_set_number` 1

`fq profile` creates a .checksum file in every directory containing fastqs that it is run on. The `.checksum` file is used as a cache when retrieving data for a fastq.


### Usage

__Set your `project` and `kind`:__

```
fq set <project> <kind>
```

Set `<project>` to your google cloud project name. Set kind to the name of the `kind` you want to store fastq data in within Google Datastore.

```
fq set 'my-google-cloud-project' 'fastq-set'
```

__Profile a fastq__

```
fq profile [options] <fq>...
```

__Run fq profile on multiple fastqs__

```
fq profile myseq1.fq.gz myseq2.fq.gz myseq3.fq.gz
```

__Run fq profile on an entire directory__

You can use a `*` wildcard:

```
fq profile *.fq.gz
```

__Read files from stdin__

```
find . -name *.gz  | egrep "(fastq|fq)" - | fq profile - 
```

#### Fetching fastq data

Once you have profiled fastqs, you can fetch data associated with them using the `fetch` command:

```
fq profile fetch myseq1.fq.gz myseq2.fq.gz
```

__Output__

Output is in JSON format.

```
{
    "A_count": 67669, 
    "C_count": 44800, 
    "GC_content": 0.3954977777777778, 
    "G_count": 44187, 
    "N_count": 4, 
    "T_count": 68340, 
    "avg_length": 90.0, 
    "barcode": "CATCCGGA", 
    "bases": 224996, 
    "cum_length": 225000, 
    "date_created": "2016-12-17T09:57:40+00:00", 
    "filename": [
        "t_N2_CGC_130119_I861_FCC1GWRACXX_L6_CHKPEI13010003_2.fq.gz.fq.gz"
    ], 
    "filesize": 197839, 
    "flowcell_lane": 6, 
    "flowcell_number": 1101, 
    "fq_profile_count": 5, 
    "hfilesize": "193 KiB", 
    "instrument": "@FCC1GWRACXX", 
    "max_length": 90, 
    "min_length": 90, 
    "most_abundant_frequency": "7", 
    "most_abundant_frequency_percent": "0.28", 
    "most_abundant_sequence": "GCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAAGCCTAA", 
    "pair": 2, 
    "path_filename": [
        "/Users/dancook/coding/git/fastq-profiler/test/t_N2_CGC_130119_I861_FCC1GWRACXX_L6_CHKPEI13010003_2.fq.gz.fq.gz"
    ], 
    "percent_unique": "99.4", 
    "total_reads": "2500", 
    "unique_reads": "2485"
}
```

#### Dump fastq data

Alternatively, you can dump fastq data stored that is stored in the `kind` you set with `fq set`:

```
fq dump
```

The command above will dump all fastq data in JSON format.

#### Options

__--kv=<k:v>__ can be used to store custom data. 

```
fq profile --kv=date_sequenced:20160610 *.fq.gz
```

In the example above, a 'date_sequenced' property will be added to the fastq entity in google datastore.
