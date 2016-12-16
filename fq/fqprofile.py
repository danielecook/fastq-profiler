#! /usr/bin/env python
"""
usage:
    fqprofile [options] <fq>...

options:
  --project=<project>         Google Cloud Project Name [default: andersen-lab]
  --kind=<kind>               Datastore kind [default: fastq]
  -h --help                   Show this screen.
  --version                   Show version.

"""

from docopt import docopt
from gcloud import datastore
import hashlib
import io
import os
from clint.textui import colored, puts, progress, indent
from fq_util import fastq_reader
import os.path
import sys
from datetime import datetime

def get_item(kind, name):
    return ds.get(ds.key(kind, name))


def update_item(kind, name, **kwargs):
    m = get_item(kind, name)
    if m is None:
        m = datastore.Entity(key=ds.key(kind, name), exclude_from_indexes = ['Most_Abundant_Sequence'])
    for key, value in kwargs.items():
        if type(value) == str:
            m[key] = unicode(value)
        elif type(value) == list:
            if key in m:
                m[key] += value
            else:
                m[key] = value
            m[key] = list(set(m[key]))
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


def query_item(kind, filters):
    # filters:
    # [("var_name", "=", 1)]
    query = ds.query(kind=kind)
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


# Stack Overflow: 1094841
from math import log
_suffixes = ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
def file_size(size):
    order = int(log(float(size), 2) / 10) if size else 0
    return '{:.4g} {}'.format(size / (1 << (order * 10)), _suffixes[order])


def main():
    args = docopt(__doc__,
                  options_first=True)
    if "*" in args["<fq>"] and len(args) == 1:
        fq_set = glob.glob(args["<fq>"])
    elif "-" in args["<fq>"]:
        fq_set = sys.stdin.readlines().strip().split("\n")
    else:
        fq_set = args["<fq>"]
    fq_set_exists = map(os.path.isfile, fq_set)
    if not all(fq_set_exists):
        missing_files = [f for f,exists in zip(fq_set, fq_set_exists) if exists is False]
        with indent(4):
            puts(colored.red("\nFile not found:\n\n" + \
                             "\n".join(missing_files) + "\n"))
            exit()


    global ds
    ds = datastore.Client(project=args['--project'])
    error_fqs = []
    for fastq in fq_set:
        puts(colored.blue(fastq))
        fq = fastq_reader(fastq)
        if fq.error is True:
            error_fqs.append(fastq)
            with indent(4):
                puts(colored.red("\nDoes not appear to be a Fastq: " + fastq + "\n"))
            continue
        hash = md5sum(fastq).hexdigest()
        nfq = get_item(args["--kind"], hash)
        kwdata = {}
        # Test if fq stats generated.
        if nfq is None or u"total_reads" not in nfq.keys():
            kwdata.update(fq.header)
            kwdata.update(fq.calculate_fastq_stats())
        file_stat = os.stat(fastq)
        kwdata['filesize'] = file_stat.st_size
        kwdata['hfilesize'] = file_size(file_stat.st_size)
        date_created = file_stat.st_ctime
        kwdata['date_created'] = datetime.fromtimestamp(date_created)

        path_filename = os.path.abspath(fastq)
        update_item("fastq",
                    hash,
                    filename=[unicode(fastq)],
                    path_filename=[unicode(path_filename)],
                    **kwdata)
    
    if error_fqs and len(fq_set) > 1:
        with indent(4):
            puts(colored.red("\nFastqs that errored:\n\n" + '\n'.join(error_fqs) + "\n"))


if __name__ == '__main__':
    main()
