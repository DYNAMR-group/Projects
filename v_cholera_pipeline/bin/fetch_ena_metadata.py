#!/usr/bin/env python3
"""
fetch_ena_metadata.py

Queries the ENA Portal API for one or more accessions of ANY type (run, sample,
study/project, or secondary study accession) and writes out metadata + a list
of FASTQ download URLs. Does NOT download anything itself -- see
download_reads.py for that.

Outputs (all in --outdir):
  metadata.csv          One row per sequencing run, standard ENA fields.
  download_urls.csv      accession,run_accession,url -- one row per FASTQ file.
  unresolved_runs.txt     run_accession list: runs ENA returned but with no
                           fastq_ftp URL (candidates for Kingfisher, handled by
                           download_reads.py).
  failed_accessions.txt   accessions ENA returned no records for at all.

Accession input can be given as:
  - One or more accessions directly on the command line, and/or
  - One or more .txt files, each containing one accession per line
    (blank lines and lines starting with '#' are ignored)

Usage:
    ./fetch_ena_metadata.py SRR24673461 -o results/
    ./fetch_ena_metadata.py PRJNA123456 -o results/
    ./fetch_ena_metadata.py accessions.txt -o results/

Requires only the Python standard library.
"""

import argparse
import csv
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ENA_PORTAL_API = "https://www.ebi.ac.uk/ena/portal/api/filereport"

# See full field list at: https://www.ebi.ac.uk/ena/portal/api/returnFields?result=read_run
FIELDS = [
    "study_accession", "secondary_study_accession",
    "sample_accession", "secondary_sample_accession",
    "run_accession", "experiment_accession",
    "tax_id", "scientific_name",
    "instrument_platform", "instrument_model",
    "library_layout", "library_strategy", "library_source",
    "read_count", "base_count",
    "fastq_ftp", "fastq_md5", "fastq_bytes",
]


def expand_accessions(raw_args):
    """Expand any .txt file args into their contained accessions; pass others through."""
    expanded, seen = [], set()

    def add(acc):
        acc = acc.strip()
        if acc and acc not in seen:
            seen.add(acc)
            expanded.append(acc)

    for arg in raw_args:
        if arg.lower().endswith(".txt"):
            path = Path(arg)
            if not path.is_file():
                print(f"  [WARN] Accession list file not found: '{arg}' -- skipping", file=sys.stderr)
                continue
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        add(line)
        else:
            add(arg)
    return expanded


def query_ena(accession, fields=FIELDS, timeout=30):
    """Query ENA for a given accession (any type). Returns a list of run-record dicts."""
    params = {
        "accession": accession,
        "result": "read_run",
        "fields": ",".join(fields),
        "format": "tsv",
    }
    url = f"{ENA_PORTAL_API}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"  [WARN] Failed to query ENA for '{accession}': {e}", file=sys.stderr)
        return []

    lines = text.strip().splitlines()
    if len(lines) < 2:
        print(f"  [WARN] No records found for accession '{accession}'", file=sys.stderr)
        return []
    return list(csv.DictReader(lines, delimiter="\t"))


def build_url_rows(query_accession, run_records):
    """Build (accession, run_accession, url) rows; also flag runs with no fastq_ftp."""
    rows, unresolved = [], []
    for record in run_records:
        run_acc = record.get("run_accession", "")
        fastq_ftp = record.get("fastq_ftp", "")
        if not fastq_ftp:
            print(f"  [WARN] No fastq_ftp entries for run '{run_acc}'", file=sys.stderr)
            unresolved.append(run_acc)
            continue
        for raw_url in fastq_ftp.split(";"):
            raw_url = raw_url.strip()
            if not raw_url:
                continue
            if not raw_url.startswith(("http://", "https://", "ftp://")):
                raw_url = "https://" + raw_url
            rows.append({"accession": query_accession, "run_accession": run_acc, "url": raw_url})
    return rows, unresolved


def main():
    parser = argparse.ArgumentParser(description="Fetch ENA metadata and FASTQ URLs for any accession type.")
    parser.add_argument(
        "accessions", nargs="+",
        help="Accessions (run/sample/study/project) and/or .txt list files. Can be mixed.",
    )
    parser.add_argument("-o", "--outdir", default="ena_output", help="Output directory (default: ena_output)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    accessions = expand_accessions(args.accessions)
    if not accessions:
        print("No valid accessions to query. Exiting.", file=sys.stderr)
        sys.exit(1)
    print(f"Resolved {len(accessions)} unique accession(s) to query.")

    all_records, all_url_rows, unresolved_runs, failed_queries = [], [], [], []

    for accession in accessions:
        print(f"Querying ENA for accession: {accession}")
        records = query_ena(accession)
        if not records:
            failed_queries.append(accession)
            continue
        for record in records:
            record["queried_accession"] = accession
        all_records.extend(records)
        url_rows, unresolved = build_url_rows(accession, records)
        all_url_rows.extend(url_rows)
        unresolved_runs.extend(unresolved)

    if all_records:
        fieldnames = ["queried_accession"] + FIELDS
        with open(outdir / "metadata.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in all_records:
                writer.writerow({k: record.get(k, "") for k in fieldnames})

        with open(outdir / "download_urls.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["accession", "run_accession", "url"])
            writer.writeheader()
            writer.writerows(all_url_rows)

        print(f"\nMetadata written to: {outdir / 'metadata.csv'}  ({len(all_records)} run records)")
        print(f"Download URLs written to: {outdir / 'download_urls.csv'}  ({len(all_url_rows)} files)")
    else:
        print("\nNo metadata retrieved for any accession.", file=sys.stderr)

    if unresolved_runs:
        with open(outdir / "unresolved_runs.txt", "w") as f:
            f.write("\n".join(unresolved_runs) + "\n")
        print(f"Runs with no fastq_ftp URL written to: {outdir / 'unresolved_runs.txt'} ({len(unresolved_runs)})")

    if failed_queries:
        with open(outdir / "failed_accessions.txt", "w") as f:
            f.write("\n".join(failed_queries) + "\n")
        print(f"Accessions with no ENA records written to: {outdir / 'failed_accessions.txt'} ({len(failed_queries)})")


if __name__ == "__main__":
    main()
