#! /usr/bin/env python
"""
usage:
    fq profile [options] <fq>...
    fq fetch <fq>...
    fq fastqc-dump <fastqc-group> [<fq>...]
    fq dump
    fq summary
    fq set <project> <kind>

options:
  -h --help                   Show this screen.
  --version                   Show version.
  --verbose                   Speak up
  --fastqc                    Gather fastqc statistics as well
  --kv=<k:v>                  Additional key-value pairs to add

"""

from docopt import docopt
from gcloud import datastore
import hashlib
import io
import os
from clint.textui import colored, puts_err, progress, indent
import fqprofile
from fq import autoconvert, json_serial, parse_fastqc
from fq import check_program_exists, fastqc_groups, fastqc_headers
from fq.fq_util import fastq_reader
import json
import os.path
import sys
from datetime import datetime
from math import log
import re
import time
import glob
from subprocess import Popen, PIPE
import tempfile
import socket
from collections import defaultdict
import shutil


def fastqc(filename):
    t_dir = tempfile.mkdtemp(prefix=filename)
    basename = os.path.basename(filename)
    fastqc_results = basename.replace(".fq", "_fastqc") \
                             .replace(".fastq", "_fastqc") \
                             .replace("_fastqc.gz", "")

    comm = ["fastqc", "--out", t_dir, "--extract", filename]
    out, err = Popen(comm, stdout=PIPE, stderr=PIPE).communicate()
    # Get folder within tempdir
    fqc_file = glob.glob(os.path.join(t_dir, "*", "fastqc_data.txt"))[0]
    results = parse_fastqc(fqc_file)
    shutil.rmtree(t_dir)
    return results


def test_fastqc(filename):
    return filename.endswith(".fq.gz") or filename.endswith(".fastq.gz")


def get_item(kind, name):
    return ds.get(ds.key(kind, name))


exclude_indices = ['most_abundant_sequence',
                   'fastqc_per_base_sequence_quality_data',
                   'fastqc_per_tile_sequence_quality_data',
                   'fastqc_per_sequence_quality_scores_data',
                   'fastqc_per_base_sequence_content_data',
                   'fastqc_per_sequence_gc_content_data',
                   'fastqc_per_base_n_content_data',
                   'fastqc_sequence_length_distribution_data',
                   'fastqc_sequence_duplication_levels_data',
                   'fastqc_overrepresented_sequences_data',
                   'fastqc_adapter_content_data',
                   'fastqc_kmer_content_data']


def update_item(kind, name, **kwargs):
    item = get_item(kind, name)
    if item is None:
        m = datastore.Entity(key=ds.key(kind, name),
                             exclude_from_indexes=exclude_indices)
    else:
        m = datastore.Entity(key=ds.key(kind, name),
                             exclude_from_indexes=exclude_indices)
        m.update(dict(item))
    for key, value in kwargs.items():
        if type(value) == str:
            m[key] = unicode(value)
        elif type(value) == list:
            if key in m:
                m[key] += value
            else:
                m[key] = value
            m[key] = list(set(m[key]))
        # If date created of file is earlier
        elif key == 'date_created' and item:
            vtimestamp = time.mktime(value.timetuple())
            dstimestamp = time.mktime(m['date_created'].timetuple())
            if vtimestamp < dstimestamp:
                m[key] = value

        else:
            m[key] = value
    if 'fq_profile_count' in m:
        m['fq_profile_count'] += 1
    else:
        m['fq_profile_count'] = 1
    ds.put(m)


def store_item(kind, name, **kwargs):
    m = datastore.Entity(key=ds.key(kind, name))
    for key, value in kwargs.items():
        if type(value) == str:
            m[key] = unicode(value)
        else:
            m[key] = value
    ds.put(m)


def query_item(kind, filters=None):
    # filters:
    # [("var_name", "=", 1)]
    query = ds.query(kind=kind)
    if filters:
        for var, op, val in filters:
            query.add_filter(var, op, val)
    return query.fetch()


def md5sum(src, length=io.DEFAULT_BUFFER_SIZE):
    calculated = 0
    md5 = hashlib.md5()
    with io.open(src, mode="rb") as fd:
        filesize = os.stat(src).st_size
        expected_size = (filesize / io.DEFAULT_BUFFER_SIZE) + 1
        for chunk in progress.bar(iter(lambda: fd.read(length), b''),
                                  expected_size=expected_size):
            md5.update(chunk)
            calculated += len(chunk)
    return md5


class checksums:
    def __init__(self):
        self.hashes = {}

    def get_or_update_checksum(self, filename):
        filename = os.path.abspath(filename)
        basename = os.path.basename(filename)
        base_dir = os.path.dirname(filename)
        checksum_file = base_dir + "/.checksum"
        if os.path.exists(checksum_file):
            hash_set = open(checksum_file, 'r').readlines()
            hash_set = [x.strip().split("\t") for x in hash_set]
            hash_set = {v: k for k, v in hash_set}
            self.hashes.update(hash_set)

        if filename in self.hashes.keys():
            if verbose:
                puts_err(colored.blue("\n" + basename + "\t[x] Using cached hash"))
        else:
            if verbose:
                puts_err(colored.blue("\n" + basename + "\t[ ] Generating hash"))

        if filename not in self.hashes.keys():
            hash = md5sum(filename).hexdigest()
            self.hashes.update({filename: hash})
            # Generate hash if it does not exist
            self.hashes.update({filename: hash})
            out = hash + "\t" + filename + "\n"
            open(checksum_file, 'a').write(out)
        return self.hashes[filename]


# Stack Overflow: 1094841
_suffixes = ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']


def file_size(size):
    order = int(log(float(size), 2) / 10) if size else 0
    return '{:.4g} {}'.format(size / (1 << (order * 10)), _suffixes[order])


def main():
    args = docopt(__doc__,
                  options_first=False)
    ck = checksums()
    settings_file = os.path.dirname(fqprofile.__file__) + "/.config"
    # Save settings
    if args["set"]:
        settings = {"project": args["<project>"], "kind": args["<kind>"]}
        open(settings_file, 'w').write(json.dumps(settings, indent=4))
        puts_err("Saved Settings")
        exit()
    else:
        if not os.path.exists(settings_file):
            with indent(4):
                exit(puts_err(colored.red("\nPlease set project and kind using 'fq set'\n")))
        # Load settings
        settings = json.loads(open(settings_file, 'r').read())
        project = settings['project']
        kind = settings['kind']
        output_str = "Project: {project} - Kind: {kind}".format(**locals())
        output_under = len(output_str) * "="
        puts_err(colored.blue("\n{output_str}\n{output_under}".format(**locals())))

    global ds
    global verbose
    verbose = args["--verbose"]
    ds = datastore.Client(project=project)

    if args["dump"]:
        fastq_dumped = query_item(kind)
        for i in fastq_dumped:
            for j in exclude_indices[1:]:
                del i[j]
            print(json.dumps(i, default=json_serial, indent=4, sort_keys=True))
        exit()

    if args["summary"]:
        fastq_dumped = query_item(kind)
        cn = defaultdict(int)
        for i in fastq_dumped:
            cn['count'] += 1
            cn['bases'] += i['bases']
            cn['filesize'] += i['filesize']
        fm = """FASTQ count: {count}\nBases: {bases}\nfilesize: {filesize}\n"""

        print fm.format(count=cn['count'],
                        bases=cn['bases'],
                        filesize=file_size(cn['filesize']))

    if "*" in args["<fq>"] and len(args) == 1:
        fq_set = glob.glob(args["<fq>"])
    elif "-" in args["<fq>"]:
        fq_set = [x.strip() for x in sys.stdin.readlines()]
    else:
        fq_set = args["<fq>"]
    fq_set_exists = map(os.path.isfile, fq_set)
    fastqc_complient = map(test_fastqc, fq_set)


    if args["fastqc-dump"]:
        fastqc_group = "fastqc_" + args["<fastqc-group>"] + "_data"
        if args["<fastqc-group>"] not in fastqc_groups:
            with indent(4):
                puts_err(colored.blue("\nFastQC group not found. Available FastQC groups:\n\n" + 
                                      '\n'.join(fastqc_groups) + "\n"))
                exit()

        if fq_set:
            # Output header
            print('\t'.join(['filename'] + fastqc_headers[args["<fastqc-group>"]]))
            for i in fq_set:
                hash = ck.get_or_update_checksum(i)
                fastqc_data = get_item(kind, hash)[fastqc_group].splitlines()
                out = '\n'.join([i + "\t" + x for x in fastqc_data])
                print(out)
        else:
            # Output header
            print('\t'.join(['hash', 'filename'] + fastqc_headers[args["<fastqc-group>"]]))
            # If no fq specified, dump everything:
            fastq_dumped = query_item(kind)
            for i in fastq_dumped:
                fastqc_data = i[fastqc_group].splitlines()
                fnames = i.key.name + "\t" + i['filename'][0]
                out = '\n'.join([fnames + "\t" + x for x in fastqc_data])
                print(out)
        exit()

    if args["--fastqc"]:
        check_program_exists("fastqc")
        if not all(fastqc_complient):
            err_msg = "\n--fastqc only works with fq.gz, fastq.gz," + \
                       " fq, and fastq extensions.\n"
            with indent(4):
                puts_err(colored.red(err_msg))
                exit()
    if not all(fq_set_exists):
        missing_files = [f for f, exists in zip(fq_set, fq_set_exists)
                         if exists is False]
        with indent(4):
            puts_err(colored.red("\nFile not found:\n\n" +
                             "\n".join(missing_files) + "\n"))
            exit()


    error_fqs = []
    for fastq in fq_set:
        basename = os.path.basename(fastq)
        hash = ck.get_or_update_checksum(fastq)
        fq = fastq_reader(fastq)
        if fq.error is True:
            error_fqs.append(fastq)
            with indent(4):
                puts_err(colored.red("\nDoes not appear to be a Fastq: " +
                     fastq + "\n"))
            continue


        if args["fetch"]:
            d = get_item(kind, hash)
            if d:
                for j in exclude_indices[1:]:
                    del d[j]
                print(json.dumps(d,
                                 default=json_serial,
                                 indent=4,
                                 sort_keys=True))
            else:
                puts_err(colored.red("{basename} has not been profiled. Profile with 'fq profile'".format(basename=basename)))
            continue

        nfq = get_item(kind, hash)
        kwdata = {}
        # Test if fq stats generated.
        if nfq is None or u"total_reads" not in nfq.keys():
            if verbose:
                puts_err(colored.blue(basename + "\t[ ] Profiling"))
            kwdata.update(fq.header)
            kwdata.update(fq.calculate_fastq_stats())
        else:
            if verbose:
                puts_err(colored.blue(basename + "\t[x] Already profiled"))

        # Test if fastq filename matches illumina conventions
        illumina_keys = None
        i1 = re.match(r"([^_]+)_([ATGC]+)_([L0-9]{4})_([R12]{2})_([0-9]{3}).(fastq|fq).gz", basename)
        i2 = re.match(r"([^_]+)_(S[0-9]+)_([L0-9]{4})_([R12]{2})_([0-9]{3}).(fastq|fq).gz", basename)
        if i1:
            r = i1
            illumina_keys = ["illumina_filename_sample",
                             "illumina_filename_barcode_sequence",
                             "illumina_filename_lane",
                             "illumina_filename_read",
                             "illumina_filename_set_number"]
        elif i2:
            r = i2
            illumina_keys = ["illumina_filename_sample",
                             "illumina_filename_sample_number",
                             "illumina_filename_lane",
                             "illumina_filename_read",
                             "illumina_filename_set_number"]
        if illumina_keys:
            puts_err(colored.blue(basename + "\tIllumina Filename"))
            illumina_values = map(autoconvert, r.groups())
            illumina_data = dict(zip(illumina_keys, illumina_values))
            kwdata.update(illumina_data)

        # File statistics
        file_stat = os.stat(fastq)
        kwdata['filesize'] = file_stat.st_size
        kwdata['hfilesize'] = file_size(file_stat.st_size)
        date_created = file_stat.st_ctime
        kwdata['date_created'] = datetime.fromtimestamp(date_created)

        # Add custom data
        if args['--kv']:
            if verbose:
                puts_err(colored.blue(basename + "\tStoring Custom data"))
            kv = [x.split(":") for x in args['--kv'].split(",")]
            kv = {k: autoconvert(v) for k, v in kv}
            kwdata.update(kv)

        # FASTQC
        if args["--fastqc"]:
            if  nfq is None or u"fastqc_version" not in nfq.keys():
                if verbose:
                    puts_err(colored.blue(basename + "\t[ ] Running Fastqc"))
                fqc_data = fastqc(fastq)
                kwdata.update(fqc_data)
            else:
                if verbose:
                    puts_err(colored.blue(basename + "\t[x] FastQC already run"))

        filename = os.path.abspath(fastq)
        kwdata['hostname'] = [unicode(os.getlogin())]
        kwdata['basename'] = [unicode(basename)]
        kwdata['filename'] = [unicode(filename)]
        update_item(kind,
                    hash,
                    **kwdata)
        puts_err(colored.blue(basename + "\tComplete"))

    if error_fqs and len(fq_set) > 1:
        with indent(4):
            puts_err(colored.red("\nFastqs that errored:\n\n" +
                     '\n'.join(error_fqs) + "\n"))


if __name__ == '__main__':
    main()
