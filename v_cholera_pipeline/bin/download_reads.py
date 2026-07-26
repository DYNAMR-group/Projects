#!/usr/bin/env python3
"""
download_reads.py

Downloads FASTQ files listed in a download_urls.csv produced by
fetch_ena_metadata.py (columns: accession, run_accession, url). Purely a
downloader -- does no ENA querying itself.

Also accepts --unresolved and/or --failed .txt files (also produced by
fetch_ena_metadata.py) listing runs/accessions with no known URL. These --
plus any URL that fails to download after retries -- are automatically handed
to Kingfisher, which tries ENA FTP, then AWS Open Data, then NCBI prefetch,
in order, until one source works. Kingfisher must be installed and on $PATH.

Outputs (all in --outdir):
  <run_accession>_<n>.fastq.gz   Downloaded files (n = position in the URL list for that run).
  kingfisher_fallback/            Files downloaded via the Kingfisher fallback, if used.
  failed_downloads.txt            Every run that could not be downloaded via any method.

Usage:
    ./download_reads.py results/download_urls.csv -o reads/
    ./download_reads.py results/download_urls.csv -o reads/ \\
        --unresolved results/unresolved_runs.txt \\
        --failed results/failed_accessions.txt

Requires only the Python standard library, plus Kingfisher on $PATH
(https://github.com/wwood/kingfisher-download).
"""

import argparse
import csv
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # 1 MB


def download_url(url, dest_path, retries=3, timeout=60):
    """Download a single URL to dest_path, retrying on failure. Returns True/False."""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "download_reads.py"})
            with urllib.request.urlopen(req, timeout=timeout) as response, open(dest_path, "wb") as out:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"    [WARN] Attempt {attempt}/{retries} failed for {url}: {e}", file=sys.stderr)
            if dest_path.exists():
                dest_path.unlink()
    return False


def run_kingfisher_fallback(run_accessions, outdir, methods=("ena-ftp", "aws-http", "prefetch")):
    """Attempt to download each run accession via Kingfisher. Returns list of result dicts."""
    kingfisher_path = shutil.which("kingfisher")
    results = []

    if not kingfisher_path:
        print(
            "  [WARN] Kingfisher fallback needed but 'kingfisher' is not on $PATH. "
            "Install it (e.g. via conda) and re-run. Skipping fallback downloads.",
            file=sys.stderr,
        )
        return [{"run_accession": r, "status": "kingfisher_not_found"} for r in run_accessions]

    fallback_dir = outdir / "kingfisher_fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)

    for run_acc in run_accessions:
        print(f"  Attempting Kingfisher fallback for run '{run_acc}' (methods: {', '.join(methods)}) ...")
        cmd = ["kingfisher", "get", "-r", run_acc, "-m", *methods, "-f", "fastq.gz",
               "--output-directory", str(fallback_dir)]
        try:
            subprocess.run(cmd, check=True)
            results.append({"run_accession": run_acc, "status": "downloaded"})
        except subprocess.CalledProcessError as e:
            print(f"  [WARN] Kingfisher failed for run '{run_acc}': {e}", file=sys.stderr)
            results.append({"run_accession": run_acc, "status": "failed"})

    return results


def read_txt_list(path):
    if not path:
        return []
    path = Path(path)
    if not path.is_file():
        print(f"  [WARN] List file not found: '{path}' -- skipping", file=sys.stderr)
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def main():
    parser = argparse.ArgumentParser(description="Download FASTQ files from a download_urls.csv, with optional Kingfisher fallback.")
    parser.add_argument("urls_csv", help="download_urls.csv produced by fetch_ena_metadata.py")
    parser.add_argument("-o", "--outdir", default="reads", help="Output directory (default: reads)")
    parser.add_argument("--retries", type=int, default=3, help="Retries per URL before giving up (default: 3)")
    parser.add_argument("--unresolved", help="unresolved_runs.txt from fetch_ena_metadata.py (runs with no URL)")
    parser.add_argument("--failed", help="failed_accessions.txt from fetch_ena_metadata.py (accessions ENA had no records for)")
    parser.add_argument(
        "--kingfisher-methods", nargs="+", default=["ena-ftp", "aws-http", "prefetch"],
        help="Kingfisher methods to try in order (default: ena-ftp aws-http prefetch)",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    urls_path = Path(args.urls_csv)
    if not urls_path.is_file():
        print(f"URLs file not found: {urls_path}", file=sys.stderr)
        sys.exit(1)

    with open(urls_path, newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} file(s) to download from {urls_path}")

    failed_runs = set()  # run_accessions that need the Kingfisher fallback

    # Group rows by run so multi-file runs (e.g. paired-end R1/R2) get numbered consistently
    runs_seen = {}
    for row in rows:
        run_acc = row["run_accession"]
        idx = runs_seen.get(run_acc, 0) + 1
        runs_seen[run_acc] = idx

        ext = ".fastq.gz" if row["url"].endswith(".gz") else Path(row["url"]).suffix or ".fastq"
        dest = outdir / f"{run_acc}_{idx}{ext}"

        print(f"Downloading {row['url']} -> {dest}")
        ok = download_url(row["url"], dest, retries=args.retries)
        if not ok:
            print(f"  [WARN] Failed to download {row['url']} after {args.retries} attempts", file=sys.stderr)
            failed_runs.add(run_acc)

    # Runs that never had a URL at all (from the metadata step)
    unresolved_runs = read_txt_list(args.unresolved)
    failed_accessions = read_txt_list(args.failed)
    # For failed accessions (no metadata at all), Kingfisher can still try using the
    # accession itself as a run identifier.
    fallback_candidates = sorted(set(failed_runs) | set(unresolved_runs) | set(failed_accessions))

    still_failed = []
    if fallback_candidates:
        print(f"\n{len(fallback_candidates)} run(s)/accession(s) need the Kingfisher fallback:")
        for r in fallback_candidates:
            print(f"    {r}")

        results = run_kingfisher_fallback(fallback_candidates, outdir, methods=args.kingfisher_methods)
        n_ok = sum(1 for r in results if r["status"] == "downloaded")
        print(f"  {n_ok}/{len(results)} downloaded successfully via Kingfisher.")
        still_failed = [r["run_accession"] for r in results if r["status"] != "downloaded"]

    if still_failed:
        failed_path = outdir / "failed_downloads.txt"
        with open(failed_path, "w") as f:
            f.write("\n".join(still_failed) + "\n")
        print(f"\n{len(still_failed)} run(s) could not be downloaded via any method.")
        print(f"  Written to: {failed_path}")
    else:
        print("\nAll files downloaded successfully.")


if __name__ == "__main__":
    main()
