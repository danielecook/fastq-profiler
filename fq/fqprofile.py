#! /usr/bin/env python
"""
usage:
    fqprofile [options] <fq>...

options:
  --project=<project>         Google Cloud Project Name [default: andersen-lab]
  -h --help                   Show this screen.
  --version                   Show version.

"""

from docopt import docopt
from gcloud import datastore
import hashlib
import io
import os
from clint.textui import colored, puts, progress
from fq_util import fastq_reader


def get_item(kind, name):
    return ds.get(ds.key(kind, name))


def update_item(kind, name, **kwargs):
    m = get_item(kind, name)
    if m is None:
        m = datastore.Entity(key=ds.key(kind, name))
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


def getSize(filename):
    st = os.stat(filename)
    return st.st_size


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
        filesize = getSize(src)
        expected_size = (filesize / io.DEFAULT_BUFFER_SIZE) + 1
        for chunk in progress.bar(iter(lambda: fd.read(length), b''),
                                  expected_size=expected_size):
            md5.update(chunk)
            calculated += len(chunk)
    return md5


def main():
    args = docopt(__doc__,
                  options_first=True)
    if "*" in args["<fq>"] and len(args) == 1:
        fq_set = glob.glob(args["<fq>"])
    else:
        fq_set = args["<fq>"]
    global ds
    ds = datastore.Client(project=args['--project'])
    for fastq in args['<fq>']:
        puts(colored.blue(fastq))
        hash = md5sum(fastq).hexdigest()
        nfq = get_item("fastq", hash)
        kwdata = {}
        # Test if fq stats generated.
        if nfq is None or u"Total_Reads" not in nfq.keys():
            fq = fastq_reader(fastq)
            kwdata["fastq_stats"] = True
            kwdata.update(fq.header)
            kwdata.update(fq.calculate_fastq_stats())
        path_filename=os.path.abspath(fastq)
        update_item("fastq", hash, filename=[unicode(fastq)], path_filename=[unicode(path_filename)], **kwdata)


if __name__ == '__main__':
    main()
