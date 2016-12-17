from datetime import datetime
from clint.textui import colored, puts_err
import os

def boolify(s):
    if s == 'True':
        return True
    if s == 'False':
        return False
    raise ValueError("huh?")

def autoconvert(s):
    for fn in (boolify, int, float):
        try:
            return fn(s)
        except ValueError:
            pass
    return s

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")


def parse_fastqc(fqc):
    d = [x.strip().split("\t") for x in open(fqc, 'r').readlines()]
    out = {}
    table_group = None
    table_out = ""
    for line in d:
        if line[0].startswith("##FastQC"):
            out['fastqc_version'] = autoconvert(line[1])
        elif line[0] == ">>END_MODULE" and table_group == "basic_statistics" or line[0].startswith("#"):
            pass
        elif line[0] == ">>END_MODULE" and table_group:
            out["fastqc_" + table_group + "_data"] = table_out
            table_group = None
            table_out = ""
        # Pass QC
        elif line[0].startswith(">>"):
            k = line[0].lower() \
                       .replace(" ", "_") \
                       .strip(">")
            out[k] = line[1]
            table_group = k
        elif line[0] in ["Encoding",
                         "Sequences flagged as poor quality",
                         "Sequence length",
                         "%GC"]:
            k = line[0].lower() \
                       .replace(" ", "_") \
                       .replace("%gc", "GC_content")
            out["fastqc_" + k] = autoconvert(line[1])
        elif table_group:
            table_out += '\t'.join(line) + "\n"

    return(out)


# Stack Overflow: 377017
def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def check_program_exists(program):
    if which(program) is None:
        exit(puts_err(colored.red("\nError: " + program + " not installed or on PATH.\n")))
