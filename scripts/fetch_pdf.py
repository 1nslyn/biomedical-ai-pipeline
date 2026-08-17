#!/usr/bin/env python3
"""Download whatever PDFs are legally free for a domain's papers.

    python scripts/fetch_pdf.py LLM
    python scripts/fetch_pdf.py LLM --only 10.1038/s41591-025-04151-2
    python scripts/fetch_pdf.py LLM --dry-run

For each entry in data/<domain>.yaml, tries -- in order -- the publisher page
itself (open-access articles serve their PDF with no login), the Springer
supplementary-file host, then three legal open-access aggregators (Unpaywall,
Semantic Scholar, OpenAlex). Every one of these is either the publisher
serving content it has already marked free, or an API built for exactly this
lookup; none of it is Google Scholar scraping, and nothing here attempts to
solve a CAPTCHA or a bot-detection challenge.

A paper with no route here is not a bug to fix -- it is genuinely paywalled,
and the report at the end says so rather than guessing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.schema import PIPELINE_ROOT, Vocab, load_domain, load_domains, pdf_stem  # noqa: E402

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
CONTACT_EMAIL = "leo.cheng.chen@gmail.com"  # required by Unpaywall's API terms
MIN_PDF_BYTES = 10_000  # below this it is an error page, not a paper


def fetch(url: str, timeout: int = 45) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError):
        return None


def fetch_json(url: str) -> dict | None:
    raw = fetch(url)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def is_pdf(data: bytes | None) -> bool:
    return bool(data) and len(data) >= MIN_PDF_BYTES and data[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Routes. Each takes an entry and returns PDF bytes or None -- never raises,
# a route that fails just means the next one gets a turn.
# ---------------------------------------------------------------------------

def route_publisher_direct(entry: dict) -> bytes | None:
    """The publisher page itself. Only pays off for articles marked open access."""
    url = entry.get("url", "")
    if "nature.com/articles/" not in url:
        return None
    return fetch(url.rstrip("/") + ".pdf")


def route_unpaywall(entry: dict) -> bytes | None:
    doi = entry.get("doi")
    if not doi:
        return None
    data = fetch_json(f"https://api.unpaywall.org/v2/{doi}?email={CONTACT_EMAIL}")
    if not data or not data.get("is_oa"):
        return None
    loc = data.get("best_oa_location") or {}
    pdf_url = loc.get("url_for_pdf") or loc.get("url")
    return fetch(pdf_url) if pdf_url else None


def route_semantic_scholar(entry: dict) -> bytes | None:
    doi = entry.get("doi")
    if not doi:
        return None
    data = fetch_json(
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
    )
    if not data:
        return None
    pdf = data.get("openAccessPdf") or {}
    url = pdf.get("url")
    return fetch(url) if url else None


def route_openalex(entry: dict) -> bytes | None:
    doi = entry.get("doi")
    if not doi:
        return None
    data = fetch_json(f"https://api.openalex.org/works/https://doi.org/{doi}")
    if not data:
        return None
    loc = data.get("best_oa_location") or {}
    url = loc.get("pdf_url")
    return fetch(url) if url else None


MAIN_ROUTES = [
    ("nature.com (open access)", route_publisher_direct),
    ("Unpaywall", route_unpaywall),
    ("Semantic Scholar", route_semantic_scholar),
    ("OpenAlex", route_openalex),
]


# Springer/Nature DOI suffix: s<journal>-<3-digit year code>-<article number>-<checksum>.
# CONTRIBUTING.md's documented derivation: 10.1038/s41586-024-08378-w -> journal
# 41586, year 2024, number 8378 (leading zeros stripped). The year code's first
# digit is always the century marker, so "20" + the code's last two digits.
SPRINGER_DOI_RE = re.compile(r"^10\.1038/s(\d{4,5})-(\d{3})-(\d{4,5})-?\w*$")


def springer_esm_stem(doi: str) -> str | None:
    match = SPRINGER_DOI_RE.match(doi)
    if not match:
        return None
    journal, year_code, number = match.groups()
    year = "20" + year_code[-2:]
    return f"{journal}_{year}_{number.lstrip('0') or '0'}"


def route_springer_supplement(entry: dict) -> tuple[bytes | None, str | None]:
    """Springer hosts supplementary files separately from the paywalled main
    text, so this often succeeds even when every MAIN_ROUTES entry fails.

    There is no API for the MediaObjects filename -- CONTRIBUTING.md's
    documented route is to try MOESM1..MOESM4 against the DOI-derived stem.
    """
    doi = entry.get("doi")
    stem = springer_esm_stem(doi) if doi else None
    if not stem:
        return None, None
    encoded_doi = urllib.parse.quote(doi, safe="")
    for n in range(1, 5):
        candidate = (
            f"https://static-content.springer.com/esm/art%3A{encoded_doi}"
            f"/MediaObjects/{stem}_MOESM{n}_ESM.pdf"
        )
        data = fetch(candidate)
        if is_pdf(data):
            return data, candidate
    return None, None


# ---------------------------------------------------------------------------


def default_out_dir(domain: dict) -> Path | None:
    pdf_repo = domain.get("pdf_repo")
    if not pdf_repo:
        return None
    name = pdf_repo.rstrip("/").rsplit("/", 1)[-1]
    return PIPELINE_ROOT.parent / name


def fetch_one(entry: dict, vocab: Vocab, out_dir: Path, dry_run: bool) -> dict:
    stem = pdf_stem(entry, vocab)
    main_path = out_dir / f"{stem}.pdf"
    supp_path = out_dir / f"{stem}_supp.pdf"
    result = {"title": entry.get("title", "Untitled"), "stem": stem}

    if main_path.exists():
        result["main"] = "already have"
    elif dry_run:
        result["main"] = "would try: " + ", ".join(name for name, _ in MAIN_ROUTES)
    else:
        result["main"] = "not found (paywalled, no OA copy)"
        for name, route in MAIN_ROUTES:
            data = route(entry)
            if is_pdf(data):
                out_dir.mkdir(parents=True, exist_ok=True)
                main_path.write_bytes(data)
                result["main"] = f"downloaded via {name}"
                break
            time.sleep(0.3)  # be polite to free APIs between attempts

    if supp_path.exists():
        result["supp"] = "already have"
    elif dry_run:
        result["supp"] = "would try: Springer supplement"
    else:
        data, source = route_springer_supplement(entry)
        if is_pdf(data):
            out_dir.mkdir(parents=True, exist_ok=True)
            supp_path.write_bytes(data)
            result["supp"] = f"downloaded ({source})"
        else:
            result["supp"] = "none found"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain", help="domain slug, e.g. LLM")
    parser.add_argument("--only", metavar="DOI", help="fetch a single entry by DOI")
    parser.add_argument("--out", metavar="DIR", help="override the PDF repo checkout path")
    parser.add_argument("--dry-run", action="store_true", help="show what would be tried, download nothing")
    args = parser.parse_args()

    domains = {d["slug"]: d for d in load_domains()}
    domain = domains.get(args.domain)
    if not domain:
        known = ", ".join(sorted(domains))
        print(f"unknown domain {args.domain!r}. Known: {known}", file=sys.stderr)
        return 1

    out_dir = Path(args.out).expanduser() if args.out else default_out_dir(domain)
    if not out_dir:
        print(
            f"data/domains.yaml has no pdf_repo for {args.domain!r} -- pass --out DIR",
            file=sys.stderr,
        )
        return 1

    entries = load_domain(args.domain)
    if args.only:
        entries = [e for e in entries if e.get("doi") == args.only]
        if not entries:
            print(f"no entry with doi {args.only!r} in data/{args.domain}.yaml", file=sys.stderr)
            return 1

    vocab = Vocab.load()
    print(f"PDF directory: {out_dir}\n")

    results = [fetch_one(entry, vocab, out_dir, args.dry_run) for entry in entries]

    got, missing = [], []
    for r in results:
        line = f"  {r['title'][:70]}\n    main: {r['main']}\n    supp: {r['supp']}"
        print(line)
        (missing if "not found" in r["main"] or "none found" in r["supp"] else got).append(r)

    print(f"\n{len(results)} entries checked.")
    if not args.dry_run:
        still_needed = [r for r in results if "not found" in r["main"]]
        if still_needed:
            print(f"\n{len(still_needed)} main-text PDF(s) need manual retrieval:")
            for r in still_needed:
                print(f"  - {r['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
