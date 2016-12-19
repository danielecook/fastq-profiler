from collections import OrderedDict
from subprocess import Popen, PIPE
import mimetypes
import gzip
import re
from itertools import groupby as g

legacy_illumina_header = ["instrument",
                          "flowcell_lane",
                          "flowcell_number",
                          None,  # x-tile
                          None,  # y-tile
                          "barcode",  # barcode - fetched later
                          "pair"]

illumina_header = ["instrument",
                   "run_id",
                   "flowcell_id",
                   "flowcell_lane",
                   None,  # tile number
                   None,  # x-tile
                   None,  # y-tile
                   "pair",
                   "filtered",
                   "control_bits",
                   "barcode"]  # barcode/index sequence; fetched later.

pacbio_header = [""]

SRR_header = ['SRR']

stat_header = ["total_reads",
         "unique_reads",
         "percent_unique", 
         "most_abundant_sequence",
         "most_abundant_frequency",
         "most_abundant_frequency_percent"]


def parse_filename(filename):
    # <sample name>_<barcode sequence>_L<lane (0-padded to 3 digits)>_R<read number>_<set number (0-padded to 3 digits>.fastq.gz
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
    return s

def most_common(L):
    # Fetch most common item from a list.
  try:
    return max(g(sorted(L)), key=lambda(x, v):(len(list(v)),-L.index(x)))[0]
  except:
    return ""

class fastq_reader:
    # Simple class for reading fastq files.
    def __init__(self, filename):
        self.filename = filename
        # Get fastq information
        try:
            header_lines = [x["info"] for x in self.read(1)]
            header_line = header_lines[0]
            if header_line.count(":") > 3:
                header = re.split(r'(\:|#|/| )',header_lines[0])[::2]
                self.sequencing = "Illumina"
            elif re.match(r'^@.*\/[0-9]+\/[0-9]+_[0-9]+', header_line):
                header = re.split(r'(\:|#|/| )',header_lines[0])[::2]
                self.sequencing = "PacBio"
            fetch_barcode = True

            if len(header) == 11 and self.sequencing == "Illumina":
                # Use new header format.
                use_header = illumina_header
            elif len(header) == 6  and self.sequencing == "Illumina":
                # Use old header format.
                header_type = "legacy_illumina_header"
            elif len(header) == 7  and self.sequencing == "Illumina":
                # Use old header and add pair if available.
                use_header = legacy_illumina_header + ["pair"]
            elif self.sequencing == "PacBio":
                use_header = ["movie_name"]
                header = header_line.split("/")[0:1]
                fetch_barcode = False
            elif header[0].startswith("@SRR"):
                # Setup SRR Header
                header = header[0].split(".")[0:1]
                use_header = SRR_header
                fetch_barcode = False
            else:
                # If unknown header, enumerate
                use_header = ["h" + str(x) for x in range(0,len(header))]
                fetch_barcode = False

            if fetch_barcode == True:
                # Fetch index
                index_loc = use_header.index("barcode")
                fetch_index = [re.split(r'(\:|#|/| )',x["info"])[::2][index_loc] for x in self.read(1000)]
                self.barcode = most_common(fetch_index)


            self.header = {}
            # Set remaining attributes.
            for attr, val in zip(use_header, header):
                if attr is not None:
                    val = autoconvert(val) # Set variable type
                    self.header[attr] = val
                    setattr(self, attr, val)
            self.error = False
        except:
            self.error = True


    def read(self, n=-1):
        """
            Iterate through gzipped fastq file and put
            yield sequence+info in dictionary.
        """
        if self.filename.endswith(".gz"):
            open_file = gzip.open(self.filename, 'rb')
        else:
            open_file = open(self.filename, 'r') 
        with open_file as f:
            dna = {}
            for linenum, line in enumerate(f):
                dna["info"] = line.strip()
                dna["seq"] = f.next().strip()
                f.next()
                dna["qual"] = f.next().strip()
                if linenum < n or n == -1:
                    yield dna
                else:
                    break

    def calculate_fastq_stats(self):
        if mimetypes.guess_type(self.filename)[1] is None:
            # Read if not zipped.
            awk_read = "cat"
        else:
            awk_read = "gunzip -c"
        awk_one_liner =  """ awk '((NR-2)%4==0){ 
                                read=$1;total++;count[read]++;
                                print $0;
                             }
                             END{
                             for(read in count){
                             if(!max||count[read]>max) {
                                 max=count[read];
                                 maxRead=read};
                                 if(count[read]==1){
                                    unique++
                                 }
                             };
                             print "#AWK",
                                   total,
                                   unique,
                                   unique*100/total,
                                   maxRead,
                                   count[maxRead],
                                   count[maxRead]*100/total}'"""
        awk = awk_read + " " + self.filename + " | " + awk_one_liner
        out = Popen([awk], shell = True, stdout = PIPE, stderr = PIPE)
        min_length = ""
        max_length = None
        cum_length = 0
        A, T, C, G, N = [0]*5
        for n, line in enumerate(out.stdout):
            if line.startswith("#AWK"):
                d = OrderedDict(zip(stat_header, line.strip().split(" ")[1:]))
            else:
                line = line.strip()
                length = len(line)
                cum_length += length
                A += line.count("A")
                T += line.count("T")
                C += line.count("C")
                G += line.count("G")
                N += line.count("N")
                if length < min_length:
                    min_length = length
                if length > max_length:
                    max_length = length
        d["cum_length"] = cum_length  # Stat line at end + 1
        d["A_count"] = A
        d["T_count"] = T
        d["C_count"] = C
        d["G_count"] = G
        d["N_count"] = N
        d["total_reads"] = int(d["total_reads"])
        d["unique_reads"] = int(d["unique_reads"])
        d["bases"] = A + T + C + G
        d["GC_content"] = (G + C) / float(cum_length)
        d["min_length"] = min_length
        d["avg_length"] = cum_length / float(d["total_reads"])
        d["max_length"] = max_length
        return d

