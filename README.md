# DYNAMR pipelines

Bioinformatics pipelines maintained by the [DYNAMR](https://github.com/DYNAMR-group/dynamr)
group at the Malawi Liverpool Wellcome Research Programme. **One folder per
pipeline**.

## Pipelines

| Project | Description |
|----------|-------------|
| [`amr_track`](amr_track) | Data processing scripts for AMR surveillance data: organism name standardisation, deduplication, and cleaning of microbiology/LIMS data for analysis and visualisation |
| [`DLBCL_Structural_Analysis`](DLBCL_Structural_Analysis) | A reproducible Snakemake pipeline for whole-exome sequencing (WES) analysis of Diffuse Large B-Cell Lymphoma (DLBCL), integrating quality control, alignment, somatic variant calling, annotation, variant prioritization, mutant protein generation, and structural characterization of pathogenic variants. |
| [`ena-fetch`](ena-fetch) | Download FASTQ reads from ENA by accession, verify checksums, optional FastQC/MultiQC |
| [`stwatch`](stwatch) | A pipeline that types bacterial assemblies with [`mlst`](https://github.com/tseemann/mlst), flags novel/untyped and high-risk sequence types against a watch-list, and produces an interactive HTML report with plots alongside plain CSV/TSV tables. |
| [`v-cholera-pipeline`](v_cholera_pipeline) | Pipeline for analysing *Vibrio cholerae* genomes, from acquisition of raw sequencing reads to phylogenetic analysis. |

## Adding a pipeline

1. Create a folder named after your pipeline
2. Add your source files and a `README.md`
3. Open a pull request
