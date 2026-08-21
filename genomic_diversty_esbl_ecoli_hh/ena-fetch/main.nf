#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

/*
 * ENA-FETCH — download FASTQ reads from ENA by accession numbers
 * (ERR/SRR/ERX/SRX/ERS/SRS/PRJ), verify checksums, and report
 * sequencing yield. Optional FastQC/MultiQC.
 *
 * Usage: nextflow run main.nf --accessions <file> [--outdir DIR] [--fastqc]
 */

params.accessions    = null
params.outdir        = 'ena_downloads'
params.fastqc        = false
params.fastqc_outdir = 'fastqc'

if (!params.accessions || !file(params.accessions).exists())
    error "Provide a valid --accessions file (one accession per line)"

workflow.onStart { log.info "ENA-FETCH — fetching reads listed in ${params.accessions}" }

workflow.onComplete {
    def y   = file("${params.outdir}/yield_summary.tsv")
    def mbp = y.exists() ? y.readLines().drop(1).collect { it.tokenize('\t')[2] as long }.sum() / 1e6 : 0
    log.info "${workflow.success ? '✔ done' : '✘ failed'} in ${workflow.duration} — ${String.format('%.2f', mbp)} Mbp downloaded → ${params.outdir}"
}

process queryENA {
    tag "$accession"
    errorStrategy 'retry'
    maxRetries 3

    input:
    val accession

    output:
    tuple val(accession), stdout

    script:
    """
    curl -sS --fail "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=${accession}&result=read_run&fields=run_accession,fastq_ftp,fastq_md5&format=tsv&limit=0" \
    | tail -n +2 \
    | awk -F'\\t' '{n=split(\$2,u,";"); split(\$3,m,";"); for(i=1;i<=n;i++) if(u[i]) print \$1"\\t"u[i]"\\t"m[i]}' \
    | sed 's|ftp.sra.ebi.ac.uk|https://ftp.sra.ebi.ac.uk|'
    """
}

process downloadFASTQ {
    tag "$acc"
    publishDir params.outdir, mode: 'copy'
    errorStrategy 'retry'
    maxRetries 3

    input:
    tuple val(acc), val(run), val(url), val(md5)

    output:
    path outfile, emit: reads
    stdout emit: yield

    script:
    filename = url.tokenize('/')[-1]
    outfile  = acc == run ? filename : filename.replace(run, acc)
    """
    wget -q -O "${outfile}" "${url}"
    [ -z "${md5}" ] || [ "\$(md5sum "${outfile}" | cut -d' ' -f1)" = "${md5}" ] || { echo "checksum mismatch: ${outfile}" >&2; exit 1; }
    zcat -f "${outfile}" | awk -v acc="${acc}" 'NR%4==2{n++;b+=length(\$0)} END{printf "%s\\t%d\\t%d\\n", acc, n, b}'
    """
}

process fastQC {
    tag "$fastq"
    publishDir params.fastqc_outdir, mode: 'copy'
    input:  path fastq
    output: path "*_fastqc.{html,zip}"
    script: "fastqc -q ${fastq}"
}

process multiQC {
    publishDir params.fastqc_outdir, mode: 'copy'
    input:  path '*'
    output: path "multiqc_report.html"
    script: "multiqc ."
}

workflow {
    accessions = Channel.fromPath(params.accessions)
        .splitText()
        .map { it.trim() }
        .filter { it && !it.startsWith('#') }
        .unique()

    queryENA(accessions)

    downloads = queryENA.out
        .map { acc, res -> res.trim() ?
            res.trim().split('\n').collect { l -> def (r, u, m) = l.split('\t'); tuple(acc, r, u, m ?: '') } : [] }
        .flatten()
        .collate(4)

    downloadFASTQ(downloads)

    Channel.of("accession\treads\tbases\n")
        .concat(downloadFASTQ.out.yield)
        .collectFile(name: 'yield_summary.tsv', storeDir: params.outdir, newLine: false)

    if (params.fastqc) {
        multiQC(fastQC(downloadFASTQ.out.reads).collect())
    }
}
