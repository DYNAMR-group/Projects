# ena-fetch

Nextflow pipeline to download sequencing reads from the
[European Nucleotide Archive (ENA)](https://www.ebi.ac.uk/ena) by accession,
verify checksums, and report sequencing yield. Optionally runs FastQC and
MultiQC on the downloaded reads.

Part of the [DYNAMR](https://github.com/DYNAMR-group/pipelines) pipeline collection at the
Malawi Liverpool Wellcome Research Programme.

---

## Supported accession types

`ERR` · `SRR` · `ERX` · `SRX` · `ERS` · `SRS` · `PRJ`

Any accession type that maps to `read_run` entries in ENA.

## Requirements

- Nextflow ≥ 23.04
- `fastqc`, `multiqc` (only needed if using `--fastqc`)



---

## Usage

**Download reads**

```bash
nextflow run DYNAMR-group[/pipelines \
  -main-script ena-fetch/main.nf \
  --accessions accessions.txt \
  --outdir ena_downloads
```

**Download reads + run FastQC and MultiQC**

```bash
nextflow run DYNAMR-group/pipelines \
  -main-script ena-fetch/main.nf \
  --accessions accessions.txt \
  --outdir ena_downloads \
  --fastqc
```

---

## Input

A plain text file with one accession per line. Lines starting with `#` are
ignored.

```
# my accessions
ERR000001
ERR000002
SRR123456
```

---

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--accessions` | — | Path to accessions file (required) |
| `--outdir` | `ena_downloads` | Directory for downloaded FASTQ files |
| `--fastqc` | `false` | Run FastQC + MultiQC on downloaded reads |
| `--fastqc_outdir` | `fastqc` | Directory for FastQC/MultiQC output |

---

## Outputs

```
ena_downloads/
├── sample_R1.fastq.gz     downloaded FASTQ files
├── sample_R2.fastq.gz
└── yield_summary.tsv      accession, read count, base count

fastqc/                    (only if --fastqc)
├── sample_fastqc.html
├── sample_fastqc.zip
└── multiqc_report.html
```

`yield_summary.tsv` columns: `accession`, `reads`, `bases`

---

## What it does

1. **Query ENA** — fetches FASTQ URLs for each accession via the ENA Portal API
2. **Download** — downloads each FASTQ file with `wget`, retrying up to 3 times on failure and skips if still not found
3. **Verify** — checks the MD5 checksum of every file; fails if there is a mismatch
4. **Yield report** — counts reads and bases per sample and writes `yield_summary.tsv`
5. **QC** *(optional)* — runs FastQC per file and aggregates with MultiQC
