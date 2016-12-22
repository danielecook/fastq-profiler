__version__ = "0.0.4"
from datetime import datetime
from clint.textui import colored, puts_err
import os

try:
    from dateutil.parser import parse
except:
    pass



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
    if type(s) is str and s.startswith("date-"):
        s = parse(s.replace("date-", ""))
    return s


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


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


fastqc_groups = ['per_base_sequence_quality',
                 'per_tile_sequence_quality',
                 'per_sequence_quality_scores',
                 'per_base_sequence_content',
                 'per_sequence_gc_content',
                 'per_base_n_content',
                 'sequence_length_distribution',
                 'sequence_duplication_levels',
                 'overrepresented_sequences',
                 'adapter_content',
                 'kmer_content']

fastqc_headers = {'per_base_sequence_quality': ["base",
                                                "mean",
                                                "median",
                                                "lower_quartile",
                                                "upper_quartile",
                                                "10th_percentile",
                                                "90th_percentile"],
                  'per_tile_sequence_quality': ["Tile", "Base", "Mean"],
                  'per_sequence_quality_scores': ["quality", "count"],
                  'per_base_sequence_content': ["base", "G", "A", "T", "C"],
                  'per_sequence_gc_content': ["gc_content", "count"],
                  'per_base_n_content': ["base", "n_count"],
                  'sequence_length_distribution': ["length", "count"],
                  'sequence_duplications_levels': ["duplication_level",
                                                   "percentage_of_deduplicated",
                                                   "percentage_of_total"],
                  'overrepresented_sequences': ["sequence",
                                                "count",
                                                "percentage",
                                                "possible_source"],
                  'adapter_content': ["position", "illumina_universal_adapter",
                                      "illumina_small_rna_3_adapter",
                                      "illumina_small_rna_5_adapter",
                                      "nextera_transposase_sequence",
                                      "solid_small_rna_adapter"],
                  'kmer_content': ["sequence", "count", "pvalue", "obs_exp_max", "max_obs_exp_pos"]}