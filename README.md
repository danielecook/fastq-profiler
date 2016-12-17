# fqprofiler

`fqprofiler` is a command line utility for keeping track of and organizing fastqs. `fqprofiler` generates summary statistics and stores data using the file hash in [Google Datastore](https://cloud.google.com/datastore/).


### Installation


### Setup


1. Setup an account with google cloud.
2. Authorize Google Cloud using the [gcloud SDK](https://cloud.google.com/sdk/):

```
gcloud auth login
```

### Usage

__Profile a fastq__

```
fqprofile [options] <fq>...
```

__Run fqprofile on multiple fastqs__

```
fqprofile myseq1.fq.gz myseq2.fq.gz myseq3.fq.gz
```

__Run fqprofile on an entire directory__

You can use a `*` wildcard:

```
fqprofile *.fq.gz
```

__Read files from stdin__

```
find . -name *.gz  | egrep "(fastq|fq)" - | fqprofile - 
```

__Fetch data on a fastq__

```
fqprofile fetch [options] <fq>...
```

### Data

`fqprofile` uses an md5sum of each fastq processed as a `name` (analogous to a key) in Google Datastore and stores its associated data as properties under a `fastq` kind in Google Datastore. Resulting data looks like this:

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

1. `illumina_filename_sample` = EA-CFB-2-421
1. `illumina_filename_sample_number` = S1
1. `illumina_filename_lane` = L001
1. `illumina_filename_read` =  R1
1. `illumina_filename_set_number` 1

`fqprofile` creates a .checksum file in every directory containing fastqs that it is run on. The `.checksum` file is used as a cache when retrieving data for a fastq.


#### Fetch

#### Options

__--kv=<k:v>__ can be used to store custom data. 

```
fqprofile --kv=date_sequenced:20160610 *.fq.gz
```

In the example above, a 'date_sequenced' property will be added to the fastq entity in google datastore.
