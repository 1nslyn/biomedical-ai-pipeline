# Contributing

Entries live in `data/*.yaml` **in this repository**. The markdown pages are
generated from them into the catalogue repository, which by agreement holds
nothing but markdown. So a pull request here edits YAML and never a `.md` file —
anything typed into a generated page is overwritten on the next build.

See [README.md](README.md) for how the two repositories sit together and how to
point the build at your catalogue checkout.

```bash
pip install -r requirements.txt
python scripts/build.py            # regenerate the markdown
python scripts/validate.py --report
```

## Adding a paper

```bash
python scripts/fetch_meta.py "10.1038/s41591-024-02857-3" --added-by "Your Name"
```

That prints a YAML stub with the bibliographic fields already filled from
Crossref (or arXiv). Paste it into the right `data/<domain>.yaml`, fill the
TODOs from the paper, then build and validate.

`.claude/commands/add-paper.md` is the same workflow written as a prompt: run
`/add-paper <link>` in Claude Code, or paste the file into ChatGPT with your
link. It exists so nine maintainers produce byte-identical records instead of
nine private conventions.

### Which page?

One paper, one page. When a paper spans several, apply the first rule that fits:

1. Built for one imaging modality → that modality's page (`pathology`,
   `radiology`, `biomedical_images`), even if the model itself is multimodal.
2. Primary data is longitudinal clinical records → `longitudinal`.
3. Primary data is molecular or omics → `AI4biology`.
4. Mainly an agentic or tool-using system → `AI_agent`.
5. Mainly a language model or text benchmark → `LLM`.
6. Scientific discovery outside medicine → `AI4Science`.
7. None of the above → `multimodal`.

Say which rule you used in the PR. The order is arguable — argue with it in an
issue rather than routing by feel.

## The schema

Required: `date`, `title`, `url`, `venue`, `model`.
Expected (a warning if missing): `doi`, `authors`, `backbone`, `data`, `tasks`,
`modalities`.

| Field | Notes |
| --- | --- |
| `date` | `YYYY-MM`. Publication month, not the month you added it. |
| `title` | As published. |
| `url` | Canonical publisher or preprint link. |
| `doi` | Bare DOI (`10.1038/...`), no `https://doi.org/` prefix. This is the dedup key — without it, dedup falls back to title matching, which is weaker. |
| `venue` | Must be in `data/vocab.yaml`. Add new ones there with a `short`. |
| `authors` | `first` and `last` only, each `{name, scholar}`. |
| `model` | `{name, repo, weights, license}`. Only `name` is required. |
| `params` | `632M`, `4.6B`. **Only if the paper states it** — see below. |
| `backbone` | One line of architecture. |
| `pretraining` | List, from the `pretraining` vocabulary. |
| `data.scale` | Integers, with keys naming what was counted. |
| `tasks` | List, from the `tasks` vocabulary. |
| `performance` | `[{benchmark, metric, value, note}]`. |
| `verify` | Free-text list of things you could not confirm. Renders on the page. |

The controlled vocabularies (`venues`, `tasks`, `modalities`, `pretraining`)
live in `data/vocab.yaml`. The validator rejects values outside them, which is
the point: nine people otherwise write "Nat Med", "Nat. Med." and "Nature
Medicine" for the same journal. If a term is genuinely missing, add it to the
vocabulary in the same PR.

### Two fields that are easy to get wrong

**`params`.** Leave it `null` unless the paper gives a number. A backbone name
is not a parameter count — "ViT-L" tells you the reference configuration, not
what these authors trained. Where an entry does carry an inferred count, it also
carries a `verify` note saying so.

**`performance`.** The headline benchmark results, two to five rows — what the
authors themselves lead with, not their full results table. Only numbers you can
point at in the paper. An empty list stays a fine answer: a wrong benchmark
number in a catalogue other people cite is worse than a missing one, and this is
the field an LLM is most likely to invent when it is working from an abstract.
Never carry a number across from a different paper about the same model.

When in doubt, write a `verify` note. It renders as a callout on the page and
`validate.py --report` lists every entry carrying one, so it becomes tracked
work instead of a silent hole.

## What a page looks like

Two parts, both generated:

- a scan table — model, model size, data size, pre-training, downstream tasks —
  with the model name linking into its record;
- one collapsed record per model, holding the paper, authors, architecture,
  data, tasks and reported performance.

The scan table answers "which model do I want?" in one screen; the record
answers everything else without making anyone scroll past it. Change the layout
in `scripts/build.py` and every page changes together — that is the point of
generating them.

`pathology.md` is the worked example. The other eight pages are still
hand-maintained markdown and stay that way until their maintainer migrates them.

## Migrating your page

Your page, your call, one page at a time — nothing here is blocked on a
big-bang cutover. A page with a `data/<slug>.yaml` is generated; a page without
one stays exactly as you wrote it and the build only counts its rows for the
README.

To migrate yours:

1. `python scripts/fetch_meta.py "<doi>"` for each row — that fills the
   bibliographic half from Crossref or arXiv, so it is right by construction.
   Expect it to disagree with the old table sometimes; trust the API and note
   the correction.
2. Fill the fields that need the paper read, following the house rules above.
3. `python scripts/build.py` — this **overwrites `<slug>.md`**, so read the
   generated page before committing.

Or run `/add-paper` per row and let it do both halves.

## Weekly discovery

`.github/workflows/weekly-discovery.yml` runs every Monday. It searches PubMed
across the high-impact journal allowlist in `data/vocab.yaml`, drops news and
editorials by publication type, drops anything already catalogued, and opens one
issue with a checklist grouped by domain page. A typical week is around 30
candidates.

bioRxiv, medRxiv and arXiv are off by default — they roughly quintuple the list
for a much lower hit rate. Turn them on per run from the Actions tab, or with
`--include-preprints` / `--include-arxiv` locally.

It proposes; it does not commit. The human gate is deliberate — a bot that
writes straight into the catalogue would fill it with near-misses, and the only
reason to trust this list is that someone vouched for every row.

### The weekly loop, run locally

Run `/weekly-scan` in Claude Code. It scans, proposes what it thinks belongs and
where, waits for you to choose, adds only what you approved, then builds,
validates and opens a PR per page.

It costs nothing beyond the Claude subscription you already have: no API key, no
repo secret, no billing per paper. `discover.py` calls PubMed, and everything
that needs judgment happens in your session.

`.github/workflows/add-approved.yml` is the same loop unattended, for when this
moves to a shared server. It is parked on manual dispatch until then, and the
file explains what to switch on.

### Which journals get scanned

The Nature family and the Science family, per the team's decision. npj titles
are out. Cell, NEJM, Lancet, JAMA, PNAS and JCO remain perfectly good venues for
a paper you add by hand — they are just not scanned every week. To widen one
run:

```bash
python scripts/discover.py --days 7 --include-broad-journals --dry-run
```

### Paywalls

Nature-family full text is unreachable from off campus, which is normal and
handled rather than worked around: the entry gets what the abstract supports,
`performance` stays empty, and a `verify` note records that the full text was
not reachable. Running the scan from a UofT desktop fills more fields.

Run it by hand from the Actions tab, or locally:

```bash
python scripts/discover.py --days 7 --dry-run
python scripts/discover.py --check-journals   # verify the PubMed abbreviations
```

`ANTHROPIC_API_KEY` in repo secrets is optional. With it, candidates arrive
grouped by domain with a one-line rationale; without it, they arrive unrouted
and the scan still works.

## PDFs and NotebookLM

**Never commit publisher PDFs to either repository**, supplementary files
included. Most are under publisher copyright and this repo is public.

Each maintainer keeps a separate repository of the PDFs for their page. Point
`pdf_repo` in `data/domains.yaml` at it and the link appears in the README's
Papers column and on your page header. NotebookLM clones a repo in one step,
which is also how you get past the 50-source limit on the free tier that
uploading files one at a time runs into.

The naming convention is generated, not typed:

```bash
python scripts/build.py --pdf-names pathology
```

prints `2026_07_NatMed_PRISM2.pdf` and `2026_07_NatMed_PRISM2_supp.pdf` for
every entry, derived from `date`, `venue` and `model.name`. Use exactly what it
prints — no publisher hashes, no random strings.

## Splitting a long page

A page with 30 entries in one table is hard to read. Declare the sections in
`data/domains.yaml`:

```yaml
  groups: [Genomics, Transcriptomics, Proteomics]
```

then tag each entry in `data/<slug>.yaml` with a matching `group:`. The build
renders one table per group, in the order you listed them; anything untagged
collects in a final "Other" table. Leave `groups` out for a single-table page.
