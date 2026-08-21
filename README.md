# DYNAMR pipelines

Bioinformatics pipelines maintained by the [DYNAMR](https://github.com/DYNAMR-group/dynamr)
group at the Malawi Liverpool Wellcome Research Programme. **One folder per
pipeline**.

## Pipelines

| Project | Description |
|----------|-------------|
| [`amr_track`](amr_track) | Data processing scripts for AMR surveillance data: organism name standardisation, deduplication, and cleaning of microbiology/LIMS data for analysis and visualisation |
| [`DLBCL_Structural_Analysis`](DLBCL_Structural_Analysis) | A reproducible Snakemake pipeline for whole-exome sequencing (WES) analysis of Diffuse Large B-Cell Lymphoma (DLBCL), integrating quality control, alignment, somatic variant calling, annotation, variant prioritization, mutant protein generation, and structural characterization of pathogenic variants. |
| [`genomic_diversty_esbl_ecoli_hh`](genomic_diversty_esbl_ecoli_hh) | A modular Nextflow pipeline for genomic analysis of diversity of ESBL-producing *E. coli* isolates from households, spanning raw reads through quality control, assembly, resistome profiling, and phylogenetics. |
| [`v-cholera-pipeline`](v_cholera_pipeline) | Pipeline for analysing *Vibrio cholerae* genomes, from acquisition of raw sequencing reads to phylogenetic analysis. |

## Adding project pipelines

1. Create a folder named after your project
3. Add your source files and a `README.md`
4. Open a pull request
