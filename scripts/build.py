#!/usr/bin/env python3
"""Render the catalogue markdown from data/*.yaml.

    python scripts/build.py            # write the markdown files
    python scripts/build.py --check    # fail if anything on disk is stale (CI)

Pages migrate one at a time. A domain with a `data/<slug>.yaml` is generated;
a domain without one stays hand-maintained and we only count its table rows for
the README. That way nobody is blocked on a big-bang conversion.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.schema import (  # noqa: E402
    DATA_DIR,
    CATALOGUE_ROOT,
    require_catalogue,
    Vocab,
    load_domain,
    load_domains,
    pdf_stem,
)

# The catalogue holds only markdown, so every path a generated page points at
# has to be an absolute URL into this repository -- a relative link would 404.
PIPELINE_URL = os.environ.get(
    "PIPELINE_URL", "https://github.com/1nslyn/biomedical-ai-pipeline"
).rstrip("/")
PIPELINE_BLOB = f"{PIPELINE_URL}/blob/main"

GENERATED_BANNER = (
    "<!-- GENERATED FILE - DO NOT EDIT BY HAND -->\n"
    "<!-- Generated from {source} in " + PIPELINE_URL + " -->\n"
    "<!-- Edits made here are overwritten by the next build. -->\n"
)

# Readable labels for the scale chips in a detail block.
SCALE_LABELS = {
    "whole_slide_images": "WSI",
    "evaluation_wsi": "WSI (eval)",
    "image_text_pairs": "pairs",
    "image_caption_pairs": "pairs",
    "qa_pairs": "QA pairs",
    "semantic_groups": "groups",
    "synthetic_captions": "captions",
    "patients": "patients",
    "specimens": "specimens",
}


def escape_cell(text: str) -> str:
    """Make a value safe inside a markdown table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def safe_url(url: str) -> str:
    """Percent-encode the parentheses markdown link targets cannot carry.

    Elsevier PIIs are full of them: .../PIIS1470-2045(25)00661-8/abstract would
    otherwise terminate the link at the first `)`.
    """
    return str(url).replace("(", "%28").replace(")", "%29")


def link(url: str, text: str | None = None) -> str:
    """A markdown link whose label defaults to the host + path, not the raw URL."""
    if not text:
        text = re.sub(r"^https?://(www\.)?", "", str(url)).rstrip("/")
        if len(text) > 60:
            text = text[:57] + "…"
    return f"[{text}]({safe_url(url)})"


def anchor_id(entry: dict) -> str:
    name = (entry.get("model") or {}).get("name") or entry.get("title", "")
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return f"model-{slug}-{str(entry.get('date', '')).replace('-', '')}"


def person_link(person: dict | None) -> str:
    if not person or not person.get("name"):
        return "—"
    name = person["name"]
    url = person.get("scholar") or person.get("homepage")
    return link(url, name) if url else name


def code_cell(entry: dict) -> str:
    model = entry.get("model") or {}
    links = []
    if model.get("repo"):
        links.append(link(model["repo"], "code"))
    if model.get("weights"):
        links.append(link(model["weights"], "weights"))
    return " · ".join(links) if links else "—"


def maintainer_line(maintainers: list[dict]) -> str:
    """Render maintainers with whatever profile links they have supplied."""
    parts = []
    for m in maintainers or []:
        name = m.get("name", "unknown")
        primary = m.get("homepage") or m.get("scholar") or (
            f"https://github.com/{m['github']}" if m.get("github") else None
        )
        label = f"[{name}]({primary})" if primary else name

        extras = []
        for key, text in (
            ("homepage", "homepage"),
            ("scholar", "Scholar"),
            ("linkedin", "LinkedIn"),
            ("twitter", "X"),
            ("github", "GitHub"),
        ):
            value = m.get(key)
            if not value:
                continue
            if key == "github":
                value = f"https://github.com/{value}"
            if value == primary:
                continue
            extras.append(f"[{text}]({value})")
        if extras:
            label += " (" + " · ".join(extras) + ")"
        parts.append(label)
    return ", ".join(parts) if parts else "_unassigned_"


# ---------------------------------------------------------------------------
# Domain page
# ---------------------------------------------------------------------------

def term_cell(terms: list[str] | None, limit: int = 3) -> str:
    """A few controlled-vocabulary terms, short enough to sit in a table cell."""
    terms = list(terms or [])
    if not terms:
        return "—"
    shown = ", ".join(terms[:limit])
    extra = len(terms) - limit
    return f"{shown} +{extra}" if extra > 0 else shown


def date_cell(entry: dict) -> str:
    """`2026-07` as `2026.07`.

    The hyphen is a break opportunity, so a narrow first column renders it as
    "2026-" over "07". A dot is not, so the cell always stays on one line.
    """
    date = str(entry.get("date") or "").strip()
    return date.replace("-", ".") if date else "—"


def params_cell(entry: dict) -> str:
    """Model size, with the scope that makes it comparable.

    A bare "48.5M" next to a bare "632M" reads as a 13x difference when it is
    really a slide encoder next to a tile encoder. And a bare em dash reads as
    "nobody looked", which is wrong for the entries where the authors simply
    publish no count -- so an empty cell says which it is.
    """
    params = entry.get("params")
    if not params:
        status = entry.get("params_status")
        return f"_{escape_cell(status)}_" if status else "—"
    scope = entry.get("params_scope")
    return f"{escape_cell(params)} ({escape_cell(scope)})" if scope else escape_cell(params)


def training_slides_cell(entry: dict) -> str:
    """Whole slides the model was actually trained on.

    Hand-written per entry rather than pulled from `data.scale`, which counts
    different things in different records -- training slides in one, evaluation
    slides in the next, image-text pairs in a third. Falling back to
    `whole_slide_images` would quietly print an evaluation set as a training
    set, so an entry that has not been curated shows an em dash instead.
    """
    return escape_cell(entry.get("training_slides") or "—")


def pretraining_cell(entry: dict) -> str:
    """The named recipe, falling back to the controlled-vocabulary terms.

    `pretraining` is a vocabulary built for filtering, and filtering wants
    coarse buckets: nearly every model on this page is `self-supervised`, so
    printing that distinguishes nothing. `pretraining_short` names the actual
    method -- DINOv2, iBOT -> CoCa, BEiT-3 MIM -> contrastive.
    """
    short = entry.get("pretraining_short")
    if short:
        return escape_cell(short)
    return escape_cell(term_cell(entry.get("pretraining")))


def render_index_table(entries: list[dict]) -> list[str]:
    """The scan table: one row per model, linking into its detail block.

    Columns are the five the team agreed on -- model, model size, data size,
    pre-training and downstream tasks -- plus date and venue to sort by. The
    paper title, authors, code and benchmark numbers live in the detail block,
    which is one click away on the model name.
    """
    lines = [
        "| Date | Model | Venue | Model size | Training slides | Pre-training | Downstream tasks |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        model = entry.get("model") or {}
        lines.append(
            "| {date} | [{name}](#{anchor}) | {venue} | {params} | {slides} "
            "| {pretraining} | {tasks} |".format(
                date=date_cell(entry),
                name=escape_cell(model.get("name", "—")),
                anchor=anchor_id(entry),
                venue=escape_cell(entry.get("venue", "—")),
                params=params_cell(entry),
                slides=training_slides_cell(entry),
                pretraining=pretraining_cell(entry),
                tasks=escape_cell(term_cell(entry.get("tasks"))),
            )
        )
    return lines


# Only printed when the table above actually uses the convention it explains.
TABLE_LEGEND = (
    "<sub><b>Model size</b> is the count the authors publish, with the component "
    "it covers in brackets — a slide encoder and a tile encoder are not "
    "comparable. <i>not published</i> means the access routes were worked and no "
    "author source states one; <i>n/a</i> means the paper does not introduce a "
    "model. <b>Training slides</b> counts whole slides used for training, so a "
    "model trained on tiles or image–text pairs shows what it used instead.</sub>"
)


def needs_legend(entries: list[dict]) -> bool:
    return any(
        entry.get("params_scope") or entry.get("params_status") or entry.get("training_slides")
        for entry in entries
    )


def group_entries(domain: dict, entries: list[dict]) -> list[tuple[str | None, list[dict]]]:
    """Split a page into the sub-tables its domain declares, or leave it whole.

    A domain with no `groups` key renders as one table, which is what most of
    them want. Declaring groups is how a page like AI for Biology separates
    genomics from transcriptomics from proteomics instead of stacking them.
    """
    groups = domain.get("groups") or []
    if not groups:
        return [(None, entries)]

    buckets: dict[str, list[dict]] = {name: [] for name in groups}
    other: list[dict] = []
    for entry in entries:
        bucket = buckets.get(entry.get("group"))
        (bucket if bucket is not None else other).append(entry)

    out = [(name, rows) for name, rows in buckets.items() if rows]
    if other:
        out.append(("Other", other))
    return out


def render_detail(entry: dict, vocab: Vocab) -> list[str]:
    model = entry.get("model") or {}
    authors = entry.get("authors") or {}
    out: list[str] = []

    name = model.get("name", entry.get("title", "Untitled"))

    # The anchor sits outside <details> so the index link lands on the summary
    # line rather than inside a collapsed element.
    out.append(f'<a id="{anchor_id(entry)}"></a>')
    out.append("<details>")
    out.append(
        f"<summary><b>{escape_cell(name)}</b> — {escape_cell(entry.get('title', ''))}"
        f" <i>({escape_cell(entry.get('venue', ''))} {entry.get('date', '')})</i></summary>"
    )
    out.append("")
    out.append(f"**{link(entry.get('url', ''), entry.get('title', ''))}**")
    out.append("")

    byline = [f"*{entry.get('venue', '')}* · {entry.get('date', '')}"]
    first, last = person_link(authors.get("first")), person_link(authors.get("last"))
    if first != "—" or last != "—":
        byline.append(f"{first} & {last}")
    if entry.get("doi"):
        byline.append(link(f"https://doi.org/{entry['doi']}", f"doi:{entry['doi']}"))
    out.append(" · ".join(byline))
    out.append("")

    rows: list[tuple[str, str]] = []
    if entry.get("params"):
        rows.append(("Parameters", entry["params"]))
    if model.get("params_note"):
        rows.append(("Parameter note", model["params_note"]))
    if entry.get("backbone"):
        rows.append(("Backbone", entry["backbone"]))

    pretraining = entry.get("pretraining") or []
    detail = entry.get("pretraining_detail")
    if pretraining or detail:
        value = ", ".join(f"`{p}`" for p in pretraining)
        if detail:
            value = f"{value}<br>{detail}" if value else detail
        rows.append(("Pre-training", value))

    data = entry.get("data") or {}
    if data:
        value = data.get("description", "")
        scale = data.get("scale") or {}
        if scale:
            chips = " · ".join(
                f"**{v:,}** {SCALE_LABELS.get(k, k.replace('_', ' '))}"
                if isinstance(v, int)
                else f"**{v}** {k.replace('_', ' ')}"
                for k, v in scale.items()
            )
            value = f"{value}<br>{chips}" if value else chips
        rows.append(("Training data", value))

    tasks = entry.get("tasks") or []
    tasks_detail = entry.get("tasks_detail")
    if tasks or tasks_detail:
        value = ", ".join(f"`{t}`" for t in tasks)
        if tasks_detail:
            value = f"{value}<br>{tasks_detail}" if value else tasks_detail
        rows.append(("Downstream tasks", value))

    if entry.get("modalities"):
        rows.append(("Modalities", ", ".join(f"`{m}`" for m in entry["modalities"])))
    if model.get("repo"):
        rows.append(("Code", link(model["repo"])))
    if model.get("weights"):
        rows.append(("Weights", link(model["weights"])))
    if model.get("license"):
        rows.append(("License", model["license"]))
    if entry.get("notebooklm"):
        rows.append(("NotebookLM", link(entry["notebooklm"], "open notebook")))
    if entry.get("note"):
        rows.append(("Note", entry["note"]))

    out.append("| | |")
    out.append("| --- | --- |")
    for label, value in rows:
        out.append(f"| **{label}** | {escape_cell(value)} |")
    out.append("")

    perf = entry.get("performance") or []
    if perf:
        out.append("**Reported performance**")
        out.append("")
        out.append("| Benchmark | Metric | Value | Note |")
        out.append("| --- | --- | --- | --- |")
        for row in perf:
            out.append(
                "| {b} | {m} | {v} | {n} |".format(
                    b=escape_cell(row.get("benchmark", "")),
                    m=escape_cell(row.get("metric", "")),
                    v=escape_cell(row.get("value", "")),
                    n=escape_cell(row.get("note", "") or ""),
                )
            )
        out.append("")

    out.append("</details>")
    out.append("")
    return out


def render_domain_page(domain: dict, entries: list[dict], vocab: Vocab) -> str:
    slug = domain["slug"]
    out = [GENERATED_BANNER.format(source=f"data/{slug}.yaml")]
    out.append(f"# {domain['name']}")
    out.append("")
    out.append(f"{domain['scope']}.")
    out.append("")
    out.append(f"**Maintainer:** {maintainer_line(domain.get('maintainers'))}")
    out.append("")

    summary = [f"**{len(entries)} entries**"]
    if domain.get("pdf_repo"):
        summary.append(f"[Paper PDFs]({domain['pdf_repo']})")
    if domain.get("notebooklm"):
        summary.append(f"[NotebookLM]({domain['notebooklm']})")
    summary.append("[Back to index](README.md)")
    out.append(" · ".join(summary))
    out.append("")

    if not entries:
        out.append("_No entries yet._")
        return "\n".join(out) + "\n"

    for group_name, rows in group_entries(domain, entries):
        if group_name:
            out.append(f"## {group_name}")
            out.append("")
        out.extend(render_index_table(rows))
        out.append("")

    if needs_legend(entries):
        out.append(TABLE_LEGEND)
        out.append("")

    out.append("## Details")
    out.append("")
    out.append("Click a model to expand its record.")
    out.append("")
    for entry in entries:
        out.extend(render_detail(entry, vocab))

    out.append("---")
    out.append("")
    out.append(
        f"This page is generated. Add a paper by editing "
        f"[`data/{slug}.yaml`]({PIPELINE_BLOB}/data/{slug}.yaml) in the "
        f"[pipeline repository]({PIPELINE_URL}) and rebuilding — edits made here are "
        f"overwritten. The schema and house rules are in "
        f"[CONTRIBUTING.md]({PIPELINE_BLOB}/CONTRIBUTING.md)."
    )
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

# The catalogue README is hand-maintained by the team -- this build does not
# touch it. Generating a shared front page from one maintainer's data would
# overwrite everyone else's edits on every run.
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit non-zero if any generated file is out of date",
    )
    parser.add_argument(
        "--pdf-names",
        metavar="DOMAIN",
        help="print the PDF filenames for a domain and exit -- the naming "
        "convention for your paper PDF repository, generated so nobody types it",
    )
    args = parser.parse_args()

    vocab = Vocab.load()
    domains = load_domains()

    if args.pdf_names:
        slug = args.pdf_names
        if not (DATA_DIR / f"{slug}.yaml").exists():
            known = ", ".join(d["slug"] for d in domains)
            print(f"no data/{slug}.yaml. Domains: {known}", file=sys.stderr)
            return 1
        for entry in load_domain(slug):
            stem = pdf_stem(entry, vocab)
            print(f"{stem}.pdf")
            print(f"{stem}_supp.pdf")
        return 0

    # Only the rendering paths need the catalogue; --pdf-names above does not.
    # Without this a missing checkout reports every page as "out of date",
    # which reads like stale data rather than a wrong path.
    require_catalogue()

    rendered: dict[Path, str] = {}
    counts: dict[str, int] = {}

    for domain in domains:
        slug = domain["slug"]
        page = CATALOGUE_ROOT / domain["file"]
        if (DATA_DIR / f"{slug}.yaml").exists():
            entries = load_domain(slug)
            counts[slug] = len(entries)
            rendered[page] = render_domain_page(domain, entries, vocab)
        # Pages without a data file are hand-maintained; nothing to render.

    stale: list[Path] = []
    for path, content in rendered.items():
        current = path.read_text() if path.exists() else None
        if current == content:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(content)

    rel = lambda p: p.relative_to(CATALOGUE_ROOT)  # noqa: E731

    if args.check:
        if stale:
            print("Generated files are out of date:")
            for path in stale:
                print(f"  - {rel(path)}")
            print("\nRun `python scripts/build.py` and commit the result.")
            return 1
        print(f"All {len(rendered)} generated files are up to date.")
        return 0

    if stale:
        for path in stale:
            print(f"wrote {rel(path)}")
    else:
        print("No changes.")
    pages = "page" if len(counts) == 1 else "pages"
    print(f"{sum(counts.values())} models across {len(counts)} generated {pages}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
