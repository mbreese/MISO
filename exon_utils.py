##
## Utilities for fetching exons from GFF files
##
import subprocess
import time
import os
import errno
import sys
import pysam

from collections import defaultdict
import GFF

def is_exon_in_mRNA(gff_in, exon, mRNA):
    """
    Check if the exon is in mRNA based on genomic coordinates.

    Arguments:

    - exon: gff record of exon
    - mRNA: gff record of mRNA
    """
    mRNA_id = mRNA.get_id()
    if mRNA_id not in gff_in.exons_by_mRNA:
        return False
    
    for curr_exon in gff_in.exons_by_mRNA[mRNA.get_id()]:
        # Exon in mRNA if it has the same coordinates and strand
        # as one of the mRNA's exons
        if curr_exon.start == exon.start and \
           curr_exon.end == exon.end and \
           curr_exon.strand == exon.strand:
            return True
    return False
    

def get_const_exons_from_mRNA(gff_in, mRNAs,
                              min_size=0,
                              all_constitutive=False):
    """
    optional:

    - all_constitutive: flag to treat all exons as constitutive
    """
    const_exons = []
    # Get first mRNA's exons
    gene_id = mRNAs[0].get_parent()
    mRNA_id = mRNAs[0].get_id()
    if mRNA_id not in gff_in.exons_by_mRNA:
        # If mRNA has no exons, skip
        return const_exons

    exons = gff_in.exons_by_mRNA[mRNA_id]

    for exon in exons:
        const_exon = True
        # Skip exons that don't meet size requirement
        exon_len = exon.end - exon.start + 1
        if exon_len < min_size: continue

        # Unless we're told all exons are constitutive, determine
        # which ones occur in all mRNAs
        if not all_constitutive:
            # Exon flagged constitutive unless it is missing
            # in one of the mRNAs
            for mRNA in mRNAs[1:]:
                curr_mRNA_id = mRNA.get_id()
                if not is_exon_in_mRNA(gff_in, exon, mRNA):
                    const_exon = False
                    break

        # If exon is constitutive, add the parent gene information
        # as a field
        exon.attributes['GeneParent'] = [gene_id]
        # Record exon if it is constitutive
        if const_exon: const_exons.append(exon)

    return const_exons


def get_bam_reads_in_exons(exons_filename, bam_filename):
    """
    Get the BAM reads that land inside the boundaries of a set of exons.

    Arguments:

    - exons filename (in GFF format)

    - BAM filename

    Returns results in BED format.

    Relies on intersectBed being available.
    """
    #intersectBed -abam reads.bam -b exons.gff -wb -f 1 | coverageBed -abam stdin -b exons.gff
    cmd = "intersectBed -abam %s -b %s -wb -f 1 | coverageBed -abam stdin -b %s -bed" \
          %(bam_filename, exons_filename, exons_filename)
    print "Getting BAM reads in exons..."
#    a = subprocess.Popen("intersectBed -abam test-output/sam-output/c2c12.Atp2b1.sorted.bam -b test-gff/Atp2b1.mm9.gff.const_exons -wb -f 1 -bed".split(), stdout=subprocess.PIPE,stderr=subprocess.PIPE)    
    return bam_reads


def output_exons_to_file(recs, output_filename,
                         output_format='gff'):
    """
    Output exons to file.

    Arguments:

    - records in gff format
    - filename to output results to
    """
    print "Outputting exons to file: %s" %(output_filename)

    if output_format == "gff":
        # Write file in GFF format
        output_file = open(output_filename, 'w')
        gff_writer = GFF.Writer(output_file)
        recs.reverse()
        gff_writer.write_recs(recs)
        output_file.close()
    elif output_format == "bed":
        # Write file in BED format
        raise Exception, "BED format unsupported."

def get_tagBam_cmd(bam_filename,
                   interval_label,
                   gff_filename,
                   as_sam=True,
                   only_interval=True):
    """
    Get call to tagBam, optionally piped through samtools.

    Assumes tagBam and samtools are available.
    """
    tagBam = "tagBam"
    tagBam_cmd = "%s -i %s -files %s -labels %s -intervals -f 1" \
                 %(tagBam, bam_filename, gff_filename,
                   interval_label)
    
    if as_sam:
        tagBam_cmd += " | samtools view - -h"

    if only_interval:
        assert(as_sam == True), \
                      "Must use as_sam= with only_interval=."
        # Keep only the header or the interval intersecting
        # reads
        tagBam_cmd += " | egrep '^@|:%s:'" %(interval_label)
    return tagBam_cmd


def map_bam2gff(bam_filename, gff_filename,
                output_dir,
                interval_label="gff"):
    """
    Map BAM file against intervals in GFF, return results as BAM.

    Only keep hits that are in the interval.

    Uses tagBam utility from bedtools.
    """
    gff_basename = os.path.basename(gff_filename)
    bam_basename = os.path.basename(bam_filename)
    output_dir = os.path.join(output_dir, "bam2gff_%s" \
                              %(gff_basename))
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    output_filename = os.path.join(output_dir, bam_basename)

    print "Mapping BAM to GFF..."
    print "  - BAM: %s" %(bam_filename)
    print "  - GFF: %s" %(gff_filename)
    print "  - Output file: %s" %(output_filename)

    if os.path.isfile(output_filename):
        print "WARNING: %s exists. Skipping.." \
              %(output_filename)
        return output_filename

    # "-intervals" option embeds the original GFF coordinates
    # in the output BAM file. Thanks to Aaron Quinlan for implementing
    # this helpful feature.
    print "Preparing to call bedtools \'tagBam\'"
    tagBam_cmd = get_tagBam_cmd(bam_filename, interval_label,
                                gff_filename)
    # Write intervals as BAM
    tagBam_cmd += " | samtools view - -Shb -o %s" \
                  %(output_filename)
    print tagBam_cmd
    
    t1 = time.time()
    cmd_status = None
    try:
        cmd_status = subprocess.call(tagBam_cmd,
                                     stdout=subprocess.PIPE,
                                     shell=True)
    except OSError, e:
        if e.errno == errno.ENOENT:
            raise Exception, "Error: tagBam or one of the input filenames " \
                  "does not exist. Are you sure tagBam is on your PATH?"
    if cmd_status != 0:
        raise Exception, "Error: tagBam call failed."
    t2 = time.time()
    print "tagBam call took %.2f seconds." \
          %(t2 - t1)
    return output_filename
    

def get_const_exons_by_gene(gff_filename, output_dir,
                            all_constitutive=False,
                            min_size=0,
                            output_format='gff'):
    """
    Get consitutive exons from GFF file.

    Arguments:
    - gff_filename: GFF input filename
    - output_dir: output directory

    Optional arguments:

    - min_size: minimum exon size
    - output_format: gff or BED
    - all_constitutive: treat all exons as constitutive
    """
    print "Getting constitutive exons..."
    print "  - Input GFF: %s" %(gff_filename)
    print "  - Output dir: %s" %(output_dir)
    print "  - Output format: %s" %(output_format)

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    if min_size > 0:
        print "  - Including only exons greater than or " \
              "equal to %d-bp" \
              %(min_size)

    t1 = time.time()
    gff_in = GFF.GFFDatabase(from_filename=gff_filename)

    const_exons_by_gene = []

    num_exons = 0

    for gene, mRNAs in gff_in.mRNAs_by_gene.iteritems():
        # For each gene, look at all mRNAs and return constitutive exon
        curr_const_exons = get_const_exons_from_mRNA(gff_in, mRNAs,
                                                     all_constitutive=all_constitutive,
                                                     min_size=min_size)
        const_exons_by_gene.extend(curr_const_exons)
        num_exons += len(curr_const_exons)

    t2 = time.time()
    output_filename = None

    if not all_constitutive:
        # If we were not given a constitutive exons GFF file, output
        # a separate file containing the constitutive exons
        output_filename = os.path.join(output_dir,
                                       "%s.min_%d.const_exons.gff" \
                                       %(os.path.basename(gff_filename).replace(".gff", ""),
                                         min_size))

        print "Constitutive exon retrieval took %.2f seconds (%d exons)." \
              %((t2 - t1), num_exons)

        output_exons_to_file(const_exons_by_gene, output_filename,
                             output_format=output_format)
    else:
        print "Constitutive exons GFF was given, so not outputting " \
              "another one."
    return const_exons_by_gene, output_filename


def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("--get-const-exons", dest="get_const_exons", nargs=1, default=None,
                      help="Get constitutive exons from an input GFF file.")
    parser.add_option("--min-exon-size", dest="min_exon_size", nargs=1, type="int", default=20,
                      help="Minimum size of constitutive exon (in nucleotides) that should be used "
                      "in the computation. Default is 20 bp.")
    parser.add_option("--output-dir", dest="output_dir", nargs=1, default=None,
                      help="Output directory.")
    (options, args) = parser.parse_args()

    if options.output_dir == None:
        print "Error: need --output-dir."
        
    output_dir = os.path.abspath(os.path.expanduser(options.output_dir))

    if options.get_const_exons != None:
        gff_filename = os.path.abspath(os.path.expanduser(options.get_const_exons))
        get_const_exons_by_gene(gff_filename,
                                output_dir,
                                min_size=options.min_exon_size)
        

if __name__ == '__main__':
    main()
