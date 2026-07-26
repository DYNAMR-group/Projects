// Metadata Resolution

process QUERY_ENA {
    tag "$accession"
    errorStrategy 'retry'
    maxRetries 3

    input:
    val accession

    output:
    tuple val(accession), path(runs_ncbi.txt), emit: resolved

    script:
    """
    curl -sS --fail "https://ebi.ac.uk{accession}&result=read_run&fields=run_accession,fastq_ftp,fastq_md5&format=tsv&limit=0" \
        | tail -n +2 \
        | awk -F'\\t' '{n=split(\$2,u,";"); split(\$3,m,";"); for(i=1;i<=n;i++) if(u[i]) print \$1"\\t"u[i]"\\t"m[i]}' \

        | sed 's|ftp.sra.ebi.ac.uk|https://ebi.ac.uk|' \
        | awk -F'\t' '{print $1}' \
        | sort -u > runs_ncbi.txt

    touch runs_ncbi.txt

    sed -i '/^$/d' runs_ncbi.txt
    """
}

process RESOLVE_KINGFISHER {

    tag "$accession"

    container 'oras://community.wave.seqera.io/library/kingfisher:0.5.0--1e110a3093396b14'

    input:
    tuple val(accession), path(ncbi_file)

    output:
    tuple val(accession), path("runs_final.txt"), emit: resolved

    script:
    """
    # If NCBI already found runs, pass them along. Otherwise, query Kingfisher metadata.
    if [ -s ${ncbi_file} ]; then
        cp ${ncbi_file} runs_final.txt
    else
        kingfisher annotate -a ${accession} --output runs_kf.tsv 2>/dev/null || touch runs_kf.tsv
        
        if [ -f runs_kf.tsv ] && [ -s runs_kf.tsv ]; then
            # Extract run columns from Kingfisher's output format
            awk -F'\\t' 'NR>1 {print \$1}' runs_kf.tsv | sort -u > runs_final.txt
        else
            touch runs_final.txt
        fi
    fi
    """
}

// Data Download

process DUAL_DOWNLOAD_RUN {
    tag "$run_id"
    
    // Direct successful downloads to fastq folder, failed ones to logs
    publishDir "${params.outdir}/fastq", mode: 'copy', pattern: '*.fastq.gz'
    publishDir "${params.outdir}/failed_runs", mode: 'copy', pattern: 'failed_*.txt'
    
    // Essential settings to prevent a single network crash from killing the pipeline
    errorStrategy 'ignore' 
    
    // Uses Kingfisher container since it ships with both kingfisher and underlying tools
    container 'wwood/kingfisher:0.3.3' 

    input:
    val run_id

    output:
    path "*.fastq.gz", optional: true, emit: fastq
    path "failed_*.txt", optional: true, emit: failed_log

    script:
    """
    echo "Attempting to download ${run_id}..."
    
    # METHOD 1: Try downloading via Kingfisher (which handles AWS/ENA/NCBI automatically)
    if kingfisher get -r ${run_id} -m aws ena ncbi --cpus ${task.cpus} --output-directory-format fastq; then
        echo "Successfully downloaded via Kingfisher"
        
        # Kingfisher output can sometimes be uncompressed depending on backend provider
        if ls *.fastq 1> /dev/null 2>&1; then
            gzip *.fastq
        fi
    else
        echo "Kingfisher failed. Falling back to explicit NCBI fasterq-dump..."
        
        # METHOD 2: Direct fallback to fasterq-dump tool
        if fasterq-dump --split-files --threads ${task.cpus} ${run_id}; then
            gzip ${run_id}*.fastq
            echo "Successfully downloaded via fasterq-dump fallback"
        else
            echo "Both Kingfisher and fasterq-dump failed for ${run_id}"
            echo "${run_id}" > failed_${run_id}.txt
        fi
    fi
    """
}

// -----------------------------------------------------------------------------
// TRACKING AND FINAL SUMMARY PHASE
// -----------------------------------------------------------------------------

process CONSOLIDATE_FAILURES {
    publishDir "${params.outdir}", mode: 'copy'
    container 'ubuntu:22.04'

    input:
    path "unresolved_parent_*"
    path "failed_run_*"

    output:
    path "failed_accessions_summary.txt"

    script:
    """
    echo "=== COMPLETE PIPELINE FAILURE REPORT ===" > failed_accessions_summary.txt
    
    echo "" >> failed_accessions_summary.txt
    echo "--- Unresolved Input Accessions (No sub-runs found) ---" >> failed_accessions_summary.txt
    cat unresolved_parent_* >> failed_accessions_summary.txt 2>/dev/null || echo "None" >> failed_accessions_summary.txt
    
    echo "" >> failed_accessions_summary.txt
    echo "--- Failed Individual Run Downloads ---" >> failed_accessions_summary.txt
    cat failed_run_* >> failed_accessions_summary.txt 2>/dev/null || echo "None" >> failed_accessions_summary.txt
    """
}

// -----------------------------------------------------------------------------
// MAIN PIPELINE FLOW
// -----------------------------------------------------------------------------

workflow {
    // 1. Channel setup for inputs
    if (params.accession_file) {
        ch_inputs = Channel.fromPath(params.accession_file).splitText().map{ it.trim() }.filter{ it != "" }
    } else if (params.accession) {
        ch_inputs = Channel.of(params.accession)
    } else {
        error "Please supply raw query target(s) using --accession or --accession_file"
    }

    // 2. Query NCBI metadata engine
    RESOLVE_NCBI(ch_inputs)

    // 3. Fallback to Kingfisher annotations for empty search results
    RESOLVE_KINGFISHER(RESOLVE_NCBI.out.resolved)

    // 4. Diverge streams: isolate tokens that couldn't be resolved anywhere
    ch_metadata_results = RESOLVE_KINGFISHER.out.resolved
        .branch {
            failed:     !it[1].size()
            successful: it[1].size()
        }

    // Capture dead root IDs for final reporting
    ch_unresolved_parents = ch_metadata_results.failed
        .map { accession, file -> 
            def f = file("unresolved_parent_${accession}.txt")
            f.text = "${accession}\n"
            return f
        }

    // 5. Unpack valid run strings into parallel execution arrays
    ch_individual_runs = ch_metadata_results.successful
        .flatMap { accession, file -> file.readLines() }
        .map { it.trim() }
        .unique()

    // 6. Launch parallel dual-download workflows
    DUAL_DOWNLOAD_RUN(ch_individual_runs)

    // 7. Extract the hard-failed run IDs
    ch_failed_runs = DUAL_DOWNLOAD_RUN.out.failed_log
        .map { file ->
            def target_name = "failed_run_${file.simpleName}.txt"
            file.copyTo(file(target_name))
            return file(target_name)
        }

    // 8. Compile unified failure log when tasks wrap up
    CONSOLIDATE_FAILURES(
        ch_unresolved_parents.collect().ifEmpty([]), 
        ch_failed_runs.collect().ifEmpty([])
    )
}
