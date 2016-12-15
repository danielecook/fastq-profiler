#! /usr/bin/env python

"""
usage:
	fqprofile <fq>...

options:
  --project                   Google Cloud Project Name
  -h --help                   Show this screen.
  --version                   Show version.

"""

from docopt import docopt
from gcloud import datastore
import hashlib
import io
import os
from clint.textui import colored, puts, indent, progress


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
    print(m)
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
    query = ds.query(kind = kind)
    for var, op, val in filters:
        query.add_filter(var, op, val)
    return query.fetch()

def md5sum(src, length=io.DEFAULT_BUFFER_SIZE):
    calculated = 0
    md5 = hashlib.md5()
    with io.open(src, mode="rb") as fd:
        filesize = getSize(src)
        for chunk in progress.bar(iter(lambda: fd.read(length), b''), expected_size = (filesize / io.DEFAULT_BUFFER_SIZE) + 1):
            md5.update(chunk)
            calculated += len(chunk)
    return md5

def main():
    args = docopt(__doc__,
                  options_first=True)
    print(args)

    ds = datastore.Client(project="andersen-lab")
    global ds
    for fastq in args['<fq>']:
        puts(colored.blue(fastq))
        hash = md5sum(fastq).hexdigest()
        update_item("fastq", hash, filename = [unicode(fastq)])



if __name__ == '__main__':
    main()