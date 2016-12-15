# fqprofiler

`fqprofiler` is a command line utility useful for keeping track of fastqs and generating summary statistics from them. The program produces hashes from fastqs and uses the hash as a key on google datastore. Summary data is stored with each hash.


### Usage

```
    fqprofile --project=<project name> <fq>...
```

`fqprofile` is invoked from the command line. You must have authorized google cloud using the [gcloud SDK](https://cloud.google.com/sdk/). By default, `fqprofile` stores summary statistics in a `kind`=`fastq` within google datastore. The following properties are stored:

1. `key` Hash of the file
1. `filename` Fastq file name
1. `path_filename` - Full path of Fastq file
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