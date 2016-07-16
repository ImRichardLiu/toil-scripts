import os
import multiprocessing

from toil_scripts.lib import require
from toil_scripts.lib.programs import docker_call


def run_cutadapt(job, r1_id, r2_id, fwd_3pr_adapter, rev_3pr_adapter):
    """
    Adapter triming for RNA-seq data

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param str r1_id: FileStoreID of fastq read 1
    :param str r2_id: FileStoreID of fastq read 2 (if paired data)
    :param str fwd_3pr_adapter: Adapter sequence for the forward 3' adapter
    :param str rev_3pr_adapter: Adapter sequence for the reverse 3' adapter (second fastq pair)
    :return: R1 and R2 FileStoreIDs
    :rtype: tuple
    """
    work_dir = job.fileStore.getLocalTempDir()
    if r2_id:
        require(rev_3pr_adapter, "Paired end data requires a reverse 3' adapter sequence.")
    # Retrieve files
    parameters = ['-a', fwd_3pr_adapter,
                  '-m', '35']
    if r1_id and r2_id:
        job.fileStore.readGlobalFile(r1_id, os.path.join(work_dir, 'R1.fastq'))
        job.fileStore.readGlobalFile(r2_id, os.path.join(work_dir, 'R2.fastq'))
        parameters.extend(['-A', rev_3pr_adapter,
                           '-o', '/data/R1_cutadapt.fastq',
                           '-p', '/data/R2_cutadapt.fastq',
                           '/data/R1.fastq', '/data/R2.fastq'])
    else:
        job.fileStore.readGlobalFile(r1_id, os.path.join(work_dir, 'R1.fastq'))
        parameters.extend(['-o', '/data/R1.fastq', '/data/R1.fastq'])
    # Call: CutAdapt
    docker_call(tool='quay.io/ucsc_cgl/cutadapt:1.9--6bd44edd2b8f8f17e25c5a268fedaab65fa851d2',
                work_dir=work_dir, parameters=parameters)
    # Write to fileStore
    if r1_id and r2_id:
        r1_cut_id = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'R1_cutadapt.fastq'))
        r2_cut_id = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'R2_cutadapt.fastq'))
    else:
        r1_cut_id = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'R1_cutadapt.fastq'))
        r2_cut_id = None
    return r1_cut_id, r2_cut_id


def run_samtools_faidx(job, ref_id, mock=False):
    """
    Use Samtools to create reference index file

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param str ref_id: FileStoreID for the reference genome
    :return: FileStoreID for reference index
    :rtype: str
    """
    job.fileStore.logToMaster('Created reference index')
    work_dir = job.fileStore.getLocalTempDir()
    job.fileStore.readGlobalFile(ref_id, os.path.join(work_dir, 'ref.fasta'))
    command = ['faidx', 'ref.fasta']
    outputs = {'ref.fasta.fai': None}
    docker_call(work_dir=work_dir, parameters=command, mock=mock, outputs=outputs,
                tool='quay.io/ucsc_cgl/samtools:0.1.19--dd5ac549b95eb3e5d166a5e310417ef13651994e')
    return job.fileStore.writeGlobalFile(os.path.join(work_dir, 'ref.fasta.fai'))


def run_samtools_index(job, bam_id):
    """
    Runs samtools index to create (.bai) files

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param str bam_id: FileStoreID of the bam file
    :return: BAM index FileStoreID
    :rtype: str
    """
    work_dir = job.fileStore.getLocalTempDir()
    job.fileStore.readGlobalFile(bam_id, os.path.join(work_dir, 'sample.bam'))
    # Call: index the bam
    parameters = ['index', '/data/sample.bam']
    docker_call(work_dir=work_dir, parameters=parameters,
                tool='quay.io/ucsc_cgl/samtools:0.1.19--dd5ac549b95eb3e5d166a5e310417ef13651994e')
    # Write to fileStore
    return job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.bam.bai'))


def samtools_view(job, bam_id, flag='0', mock=False):
    """
    Outputs bam file using a samtools view flag value
    :param job: Job instance
    :param bamFileStoreID str: bam fileStoreID
    :param flag str: samtools defined flags
    :param mock bool: If True, run in mock mode
    :return str: bam fileStoreID

    '0x800'
    """
    work_dir = job.fileStore.getLocalTempDir()
    job.fileStore.readGlobalFile(bam_id, os.path.join(work_dir, 'sample.bam'))
    outputs = {'sample.output.bam': None}
    outpath = os.path.join(work_dir, 'sample.output.bam')

    cores = multiprocessing.cpu_count()

    command = ['view',
               '-b',
               '-o', '/data/sample.output.bam',
               '-F', str(flag),
               '-@', str(cores),
               '/data/sample.bam']
    docker_call(work_dir=work_dir, parameters=command,
                tool='quay.io/ucsc_cgl/samtools:1.3--256539928ea162949d8a65ca5c79a72ef557ce7c',
                outputs=outputs,
                mock=mock)
    return job.fileStore.writeGlobalFile(outpath)


def run_picard_create_sequence_dictionary(job, ref_id, xmx='10G', mock=False):
    """
    Use Picard-tools to create reference dictionary

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param str ref_id: FileStoreID for the reference genome
    :return: FileStoreID for reference dictionary
    :rtype: str
    """
    job.fileStore.logToMaster('Created reference dictionary')
    work_dir = job.fileStore.getLocalTempDir()
    job.fileStore.readGlobalFile(ref_id, os.path.join(work_dir, 'ref.fasta'))
    command = ['CreateSequenceDictionary', 'R=ref.fasta', 'O=ref.dict']
    outputs = {'ref.dict': None}
    docker_call(work_dir=work_dir, parameters=command, mock=mock, outputs=outputs,
                env={'JAVA_OPTS':'-Xmx{}'.format(xmx)},
                tool='quay.io/ucsc_cgl/picardtools:1.95--dd5ac549b95eb3e5d166a5e310417ef13651994e')
    return job.fileStore.writeGlobalFile(os.path.join(work_dir, 'ref.dict'))


def picard_sort_sam(job, bam_id, xmx='8', mock=False):
    """
    Uses picardtools SortSam to sort a sample bam file

    :param job:
    :param bam_id:
    :param config:
    :param xmx:
    :return:
    """
    work_dir = job.fileStore.getLocalTempDir()
    outputs={'sample.sorted.bam': None, 'sample.sorted.bai': None}
    job.fileStore.readGlobalFile(bam_id, os.path.join(work_dir, 'sample.bam'))
    outpath_bam = os.path.join(work_dir, 'sample.sorted.bam')
    outpath_bai = os.path.join(work_dir, 'sample.sorted.bai')

    #Call: picardtools
    command = ['SortSam',
               'INPUT=sample.bam',
               'OUTPUT=sample.sorted.bam',
               'SORT_ORDER=coordinate',
               'CREATE_INDEX=true']
    docker_call(work_dir=work_dir, parameters=command,
                env={'JAVA_OPTS':'-Xmx{}'.format(xmx)},
                tool='quay.io/ucsc_cgl/picardtools:1.95--dd5ac549b95eb3e5d166a5e310417ef13651994e',
                outputs=outputs, mock=mock)
    bam_id = job.fileStore.writeGlobalFile(outpath_bam)
    bai_id = job.fileStore.writeGlobalFile(outpath_bai)
    return bam_id, bai_id


def picard_mark_duplicates(job, bam_id, bai_id, xmx='8G', mock=False):
    """
    Uses picardtools MarkDuplicates

    :param job:
    :param bam_id:
    :param bai_id:
    :param config:
    :param xmx:
    :return:
    """
    work_dir = job.fileStore.getLocalTempDir()
    outputs={'sample.mkdups.bam': None, 'sample.mkdups.bai': None}
    outpath_bam = os.path.join(work_dir, 'sample.mkdups.bam')
    outpath_bai = os.path.join(work_dir, 'sample.mkdups.bai')

    # Retrieve file path
    job.fileStore.readGlobalFile(bam_id, os.path.join(work_dir, 'sample.sorted.bam'))
    job.fileStore.readGlobalFile(bai_id, os.path.join(work_dir, 'sample.sorted.bai'))

    # Call: picardtools
    command = ['MarkDuplicates',
               'INPUT=sample.sorted.bam',
               'OUTPUT=sample.mkdups.bam',
               'METRICS_FILE=metrics.txt',
               'ASSUME_SORTED=true',
               'CREATE_INDEX=true']
    docker_call(work_dir=work_dir, parameters=command,
                env={'JAVA_OPTS':'-Xmx{}'.format(xmx)},
                tool='quay.io/ucsc_cgl/picardtools:1.95--dd5ac549b95eb3e5d166a5e310417ef13651994e',
                outputs=outputs, mock=mock)

    bam_id = job.fileStore.writeGlobalFile(outpath_bam)
    bai_id = job.fileStore.writeGlobalFile(outpath_bai)
    return bam_id, bai_id

def run_preprocessing(job, cores, bam, bai, ref, ref_dict, fai, phase, mills, dbsnp, mem='10G', unsafe=False):
    """
    Convenience method for grouping together GATK preprocessing

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param int cores: Maximum number of cores on a worker node
    :param str bam: Sample BAM FileStoreID
    :param str bai: Bam Index FileStoreID
    :param str ref: Reference genome FileStoreID
    :param str ref_dict: Reference dictionary FileStoreID
    :param str fai: Reference index FileStoreID
    :param str phase: Phase VCF FileStoreID
    :param str mills: Mills VCF FileStoreID
    :param str dbsnp: DBSNP VCF FileStoreID
    :param str mem: Memory value to be passed to children. Needed for CI tests
    :param bool unsafe: If True, runs gatk UNSAFE mode: "-U ALLOW_SEQ_DICT_INCOMPATIBILITY"
    :return: BAM and BAI FileStoreIDs from Print Reads
    :rtype: tuple(str, str)
    """
    rtc = job.wrapJobFn(run_realigner_target_creator, cores, bam, bai, ref, ref_dict, fai, phase, mills, mem, unsafe)
    ir = job.wrapJobFn(run_indel_realignment, rtc.rv(), bam, bai, ref, ref_dict, fai, phase, mills, mem, unsafe)
    br = job.wrapJobFn(run_base_recalibration, cores, ir.rv(0), ir.rv(1), ref, ref_dict, fai, dbsnp, mem, unsafe)
    pr = job.wrapJobFn(run_print_reads, cores, br.rv(), ir.rv(0), ir.rv(1), ref, ref_dict, fai, mem, unsafe)
    # Wiring
    job.addChild(rtc)
    rtc.addChild(ir)
    ir.addChild(br)
    br.addChild(pr)
    return pr.rv(0), pr.rv(1)


def run_gatk_preprocessing(job, cores, bam, bai, ref, ref_dict, fai, phase, mills, dbsnp,
                           mem='10G', unsafe=False, mock=False):
    """
    Pre-processing steps for running the GATK Germline pipeline

    :param cores:
    :param bam:
    :param bai:
    :param ref:
    :param ref_dict:
    :param fai:
    :param phase:
    :param mills:
    :param dbsnp:
    :param mem:
    :param unsafe:
    :return:
    """
    rm_secondary = job.wrapJobFn(samtools_view, bam, flag='0x800', mock=mock)
    picard_sort = job.wrapJobFn(picard_sort_sam, rm_secondary.rv(), xmx=mem, mock=mock)
    mdups = job.wrapJobFn(picard_mark_duplicates, picard_sort.rv(0), picard_sort.rv(1),
                          xmx=mem, mock=mock)
    rtc = job.wrapJobFn(run_realigner_target_creator, cores, mdups.rv(0), mdups.rv(1), ref,
                        ref_dict, fai, phase, mills, mem, unsafe=unsafe, mock=mock)
    ir = job.wrapJobFn(run_indel_realignment, rtc.rv(), bam, bai, ref, ref_dict, fai, phase,
                       mills, mem, unsafe=unsafe, mock=mock)
    br = job.wrapJobFn(run_base_recalibration, cores, ir.rv(0), ir.rv(1), ref, ref_dict, fai,
                       dbsnp, mem, unsafe=unsafe, mock=mock)
    pr = job.wrapJobFn(run_print_reads, cores, br.rv(), ir.rv(0), ir.rv(1), ref, ref_dict, fai,
                       mem, unsafe=unsafe, mock=mock)
    # Wiring
    job.addChild(rm_secondary)
    rm_secondary.addChild(picard_sort)
    picard_sort.addChild(mdups)
    mdups.addChild(rtc)
    rtc.addChild(ir)
    ir.addChild(br)
    br.addChild(pr)
    return pr.rv(0), pr.rv(1)


def run_realigner_target_creator(job, cores, bam, bai, ref, ref_dict, fai, phase, mills, mem,
                                 unsafe=False, mock=False):
    """
    Creates intervals file needed for indel realignment

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param int cores: Maximum number of cores on a worker node
    :param str bam: Sample BAM FileStoreID
    :param str bai: Bam Index FileStoreID
    :param str ref: Reference genome FileStoreID
    :param str ref_dict: Reference dictionary FileStoreID
    :param str fai: Reference index FileStoreID
    :param str phase: Phase VCF FileStoreID
    :param str mills: Mills VCF FileStoreID
    :param str mem: Memory value to be passed to children. Needed for CI tests
    :param bool unsafe: If True, runs gatk UNSAFE mode: "-U ALLOW_SEQ_DICT_INCOMPATIBILITY"
    :return: FileStoreID for the processed bam
    :rtype: str
    """
    work_dir = job.fileStore.getLocalTempDir()
    file_ids = [ref, fai, ref_dict, bam, bai, phase, mills]
    inputs = ['ref.fasta', 'ref.fasta.fai', 'ref.dict', 'sample.bam', 'sample.bam.bai', 'phase.vcf', 'mills.vcf']
    for file_store_id, name in zip(file_ids, inputs):
        job.fileStore.readGlobalFile(file_store_id, os.path.join(work_dir, name))
    # Call: GATK -- RealignerTargetCreator
    parameters = ['-T', 'RealignerTargetCreator',
                  '-nt', str(cores),
                  '-R', '/data/ref.fasta',
                  '-I', '/data/sample.bam',
                  '-known', '/data/phase.vcf',
                  '-known', '/data/mills.vcf',
                  '--downsampling_type', 'NONE',
                  '-o', '/data/sample.intervals']
    if unsafe:
        parameters.extend(['-U', 'ALLOW_SEQ_DICT_INCOMPATIBILITY'])
    docker_call(tool='quay.io/ucsc_cgl/gatk:3.5--dba6dae49156168a909c43330350c6161dc7ecc2',
                inputs=inputs,
                outputs={'sample.intervals': None}, mock=mock,
                work_dir=work_dir, parameters=parameters, env=dict(JAVA_OPTS='-Xmx{}'.format(mem)))
    # Write to fileStore
    return job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.intervals'))


def run_indel_realignment(job, intervals, bam, bai, ref, ref_dict, fai, phase, mills, mem,
                          unsafe=False, mock=False):
    """
    Creates realigned bams using the intervals file from previous step

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param str intervals: Indel interval FileStoreID
    :param str bam: Sample BAM FileStoreID
    :param str bai: Bam Index FileStoreID
    :param str ref: Reference genome FileStoreID
    :param str ref_dict: Reference dictionary FileStoreID
    :param str fai: Reference index FileStoreID
    :param str phase: Phase VCF FileStoreID
    :param str mills: Mills VCF FileStoreID
    :param str mem: Memory value to be passed to children. Needed for CI tests
    :param bool unsafe: If True, runs gatk UNSAFE mode: "-U ALLOW_SEQ_DICT_INCOMPATIBILITY"
    :return: FileStoreID for the processed bam
    :rtype: tuple(str, str)
    """
    work_dir = job.fileStore.getLocalTempDir()
    file_ids = [ref, fai, ref_dict, intervals, bam, bai, phase, mills]
    inputs = ['ref.fasta', 'ref.fasta.fai', 'ref.dict', 'sample.intervals',
              'sample.bam', 'sample.bam.bai', 'phase.vcf', 'mills.vcf']
    for file_store_id, name in zip(file_ids, inputs):
        job.fileStore.readGlobalFile(file_store_id, os.path.join(work_dir, name))
    # Call: GATK -- IndelRealigner
    parameters = ['-T', 'IndelRealigner',
                  '-R', '/data/ref.fasta',
                  '-I', '/data/sample.bam',
                  '-known', '/data/phase.vcf',
                  '-known', '/data/mills.vcf',
                  '-targetIntervals', '/data/sample.intervals',
                  '--downsampling_type', 'NONE',
                  '-maxReads', str(720000), # Taken from MC3 pipeline
                  '-maxInMemory', str(5400000), # Taken from MC3 pipeline
                  '-o', '/data/sample.indel.bam']
    if unsafe:
        parameters.extend(['-U', 'ALLOW_SEQ_DICT_INCOMPATIBILITY'])
    docker_call(tool='quay.io/ucsc_cgl/gatk:3.5--dba6dae49156168a909c43330350c6161dc7ecc2',
                inputs=inputs, mock=mock,
                outputs={'sample.indel.bam': None, 'sample.indel.bai': None},
                work_dir=work_dir, parameters=parameters, env=dict(JAVA_OPTS='-Xmx{}'.format(mem)))
    # Write to fileStore
    indel_bam = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.indel.bam'))
    indel_bai = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.indel.bai'))
    return indel_bam, indel_bai


def run_base_recalibration(job, cores, indel_bam, indel_bai, ref, ref_dict, fai, dbsnp, mem,
                           unsafe=False, mock=False):
    """
    Creates recal table used in Base Quality Score Recalibration

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param int cores: Maximum number of cores on a worker node
    :param str indel_bam: Indel interval FileStoreID
    :param str indel_bai: Bam Index FileStoreID
    :param str ref: Reference genome FileStoreID
    :param str ref_dict: Reference dictionary FileStoreID
    :param str fai: Reference index FileStoreID
    :param str dbsnp: DBSNP VCF FileStoreID
    :param str mem: Memory value to be passed to children. Needed for CI tests
    :param bool unsafe: If True, runs gatk UNSAFE mode: "-U ALLOW_SEQ_DICT_INCOMPATIBILITY"
    :return: FileStoreID for the processed bam
    :rtype: str
    """
    work_dir = job.fileStore.getLocalTempDir()
    file_ids = [ref, fai, ref_dict, indel_bam, indel_bai, dbsnp]
    inputs = ['ref.fasta', 'ref.fasta.fai', 'ref.dict', 'sample.indel.bam', 'sample.indel.bai', 'dbsnp.vcf']
    for file_store_id, name in zip(file_ids, inputs):
        job.fileStore.readGlobalFile(file_store_id, os.path.join(work_dir, name))
    # Call: GATK -- IndelRealigner
    parameters = ['-T', 'BaseRecalibrator',
                  '-nct', str(cores),
                  '-R', '/data/ref.fasta',
                  '-I', '/data/sample.indel.bam',
                  '-knownSites', '/data/dbsnp.vcf',
                  '-o', '/data/sample.recal.table']
    if unsafe:
        parameters.extend(['-U', 'ALLOW_SEQ_DICT_INCOMPATIBILITY'])
    docker_call(tool='quay.io/ucsc_cgl/gatk:3.5--dba6dae49156168a909c43330350c6161dc7ecc2',
                inputs=inputs, mock=mock,
                outputs={'sample.recal.table': None},
                work_dir=work_dir, parameters=parameters, env=dict(JAVA_OPTS='-Xmx{}'.format(mem)))
    # Write output to file store
    return job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.recal.table'))


def run_print_reads(job, cores, table, indel_bam, indel_bai, ref, ref_dict, fai, mem,
                    unsafe=False, mock=False):
    """
    Creates BAM that has had the base quality scores recalibrated

    :param JobFunctionWrappingJob job: passed automatically by Toil
    :param int cores: Maximum number of cores on host node
    :param str table: Recalibration table FileStoreID
    :param str indel_bam: Indel interval FileStoreID
    :param str indel_bai: Bam Index FileStoreID
    :param str ref: Reference genome FileStoreID
    :param str ref_dict: Reference dictionary FileStoreID
    :param str fai: Reference index FileStoreID
    :param str mem: Memory value to be passed to children. Needed for CI tests
    :param bool unsafe: If True, runs gatk UNSAFE mode: "-U ALLOW_SEQ_DICT_INCOMPATIBILITY"
    :return: FileStoreID for the processed bam
    :rtype: tuple(str, str)
    """
    work_dir = job.fileStore.getLocalTempDir()
    file_ids = [ref, fai, ref_dict, table, indel_bam, indel_bai]
    inputs = ['ref.fasta', 'ref.fasta.fai', 'ref.dict', 'sample.recal.table',
              'sample.indel.bam', 'sample.indel.bai']
    for file_store_id, name in zip(file_ids, inputs):
        job.fileStore.readGlobalFile(file_store_id, os.path.join(work_dir, name))
    # Call: GATK -- PrintReads
    parameters = ['-T', 'PrintReads',
                  '-nct', str(cores),
                  '-R', '/data/ref.fasta',
                  '--emit_original_quals',
                  '-I', '/data/sample.indel.bam',
                  '-BQSR', '/data/sample.recal.table',
                  '-o', '/data/sample.bqsr.bam']
    if unsafe:
        parameters.extend(['-U', 'ALLOW_SEQ_DICT_INCOMPATIBILITY'])
    docker_call(tool='quay.io/ucsc_cgl/gatk:3.5--dba6dae49156168a909c43330350c6161dc7ecc2',
                inputs=inputs, mock=mock,
                outputs={'sample.bqsr.bam': None, 'sample.bqsr.bai': None},
                work_dir=work_dir, parameters=parameters, env=dict(JAVA_OPTS='-Xmx{}'.format(mem)))
    # Write ouptut to file store
    bam_id = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.bqsr.bam'))
    bai_id = job.fileStore.writeGlobalFile(os.path.join(work_dir, 'sample.bqsr.bai'))
    return bam_id, bai_id
