#! /usr/bin/env python
"""
usage:
    fq fetch <fq>...
    fq dump
    fq set <project> <kind>
    fq profile [options] <fq>...

options:
  -h --help                   Show this screen.
  --version                   Show version.
  --kv=<k:v>                  Additional key-value pairs to add

"""

from docopt import docopt
from gcloud import datastore
import hashlib
import io
import os
from clint.textui import colored, puts_err, progress, indent
import fqprofile
from fq import autoconvert, json_serial
from fq.fq_util import fastq_reader
import json
import os.path
import sys
from datetime import datetime
from math import log
import re
import time


def get_item(kind, name):
    return ds.get(ds.key(kind, name))


def update_item(kind, name, **kwargs):
    item = get_item(kind, name)
    if item is None:
        m = datastore.Entity(key=ds.key(kind, name),
                             exclude_from_indexes=['Most_Abundant_Sequence'])
    else:
        m = item
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


def query_item(kind, filters = None):
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
            puts_err(colored.blue(basename + "\tUsing cached hash"))
        else:
            puts_err(colored.blue(basename))

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
                  options_first=True)

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
        puts_err(colored.blue("\n{output_str}\n{output_under}\n".format(**locals())))

    global ds
    ds = datastore.Client(project=project)

    if args["dump"]:
        fastq_dumped = query_item(kind)
        for i in fastq_dumped:
            print(json.dumps(i, default=json_serial, indent=4, sort_keys=True))


    if "*" in args["<fq>"] and len(args) == 1:
        fq_set = glob.glob(args["<fq>"])
    elif "-" in args["<fq>"]:
        fq_set = [x.strip() for x in sys.stdin.readlines()]
    else:
        fq_set = args["<fq>"]
    fq_set_exists = map(os.path.isfile, fq_set)
    if not all(fq_set_exists):
        missing_files = [f for f, exists in zip(fq_set, fq_set_exists)
                         if exists is False]
        with indent(4):
            puts_err(colored.red("\nFile not found:\n\n" +
                             "\n".join(missing_files) + "\n"))
            exit()

    error_fqs = []
    ck = checksums()
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
                print(json.dumps(d, default=json_serial, indent=4, sort_keys=True))
            else:
                puts_err(colored.red("{basename} has not been profiled. Profile with 'fq profile'".format(basename=basename)))
            continue

        nfq = get_item(kind, hash)
        kwdata = {}
        # Test if fq stats generated.
        if nfq is None or u"total_reads" not in nfq.keys():
            puts_err(colored.blue(basename + "\tProfiling"))
            kwdata.update(fq.header)
            kwdata.update(fq.calculate_fastq_stats())

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

        file_stat = os.stat(fastq)
        kwdata['filesize'] = file_stat.st_size
        kwdata['hfilesize'] = file_size(file_stat.st_size)
        date_created = file_stat.st_ctime
        kwdata['date_created'] = datetime.fromtimestamp(date_created)

        # Add custom data
        if args['--kv']:
            puts_err(colored.blue(basename + "\Storing Custom data"))
            kv = [x.split(":") for x in args['--kv'].split(",")]
            kv = {k: autoconvert(v) for k, v in kv}
            kwdata.update(kv)

        path_filename = os.path.abspath(fastq)
        update_item(kind,
                    hash,
                    filename=[unicode(fastq)],
                    path_filename=[unicode(path_filename)],
                    **kwdata)

    if error_fqs and len(fq_set) > 1:
        with indent(4):
            puts_err(colored.red("\nFastqs that errored:\n\n" +
                     '\n'.join(error_fqs) + "\n"))


if __name__ == '__main__':
    main()
