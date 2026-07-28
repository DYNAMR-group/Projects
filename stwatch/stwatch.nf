#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

params.input          = null                             // required: quoted glob of assemblies, e.g. "assemblies/*.fasta"
params.output         = 'mlst_results'
params.concerning_sts = "$projectDir/concerning_sts.csv"   // override with --concerning_sts your_list.csv

process RUN_MLST { 
    // Show the sample name in the Nextflow log.
    tag "$sample_id"
    publishDir params.output, mode: 'copy'

    input:
    tuple val(sample_id), path(contigs)

    output:
    path "${sample_id}_alleles.tsv"

    script:
    """
    mlst "${contigs}" > "${sample_id}_alleles.tsv"
    """
}

process BUILD_REPORT {
    // copys the summary files to the output directory
    publishDir params.output, mode: 'copy'

    input:
    path allele_files
    path concerning_csv

    output:
    path "mlst_report.csv"
    path "mlst_report.tsv"
    path "mlst_report.json", emit: json

    script:
    """
    build_report.py ${allele_files} "${concerning_csv}"
    """
}

process BUILD_HTML {
    // this is where we create an interactive HTML report from the JSON summary
    publishDir params.output, mode: 'copy'

    input:
    path report_json

    output:
    path "mlst_surveillance_report.html"

    script:
    """
    build_html_report.py "${report_json}" mlst_surveillance_report.html
    """
}

workflow {
    // this uses the default concerning ST list, or one supplied by user on the command line
    concerning_csv = file(params.concerning_sts)

    // find all input assemblies and pair each one with its sample name
    input_ch = Channel.fromPath(params.input)
        .map { f -> tuple(f.baseName, f) }

    // run MLST on each assembly
    allele_files = RUN_MLST(input_ch).collect()

    //this combines the MLST results into summary tables and a JSON file
    report = BUILD_REPORT(allele_files, concerning_csv)

    //this will build and create the HTML file report
    BUILD_HTML(report.json)
}
