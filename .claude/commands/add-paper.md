---
description: Turn a paper link into a catalogue entry (input, paper link; output, a PR-ready YAML record)
argument-hint: <doi, publisher URL, or arXiv id>
---

Add the paper at `$ARGUMENTS` to this catalogue.

This file is also the team's shared prompt. If you are not running inside Claude
Code, paste the whole thing into ChatGPT or Claude with the link substituted for
`$ARGUMENTS` — the steps are the same, you just run the commands yourself.

## 1. Get the bibliographic metadata from an API, never from memory

```bash
python scripts/fetch_meta.py "$ARGUMENTS" --added-by "<your name>"
```

That returns a YAML stub with date, title, venue, DOI and first/last author
already correct — they come from Crossref or arXiv, not from a model. Do not
retype or "correct" these fields. If the command errors, the link is probably
not a DOI or arXiv id; find the DOI first.

If it warns that the venue is unknown, add the venue to `data/vocab.yaml` with a
`short` (used for the NotebookLM filename) and, for a journal, its `pubmed`
abbreviation. Then re-run.

## 2. Check it is not already catalogued

```bash
grep -ri "<the doi>" data/ *.md
```

Skip the paper if it is already there. If the existing entry is worse than what
you are about to write, improve that entry instead of adding a second one.

## 3. Pick the domain page

One paper, one page. `data/domains.yaml` lists the scope of each. When a paper
spans several, use this order:

1. If it is built for one imaging modality, that modality's page wins
   (pathology, radiology, biomedical_images) — even if the model is multimodal.
2. Otherwise, if its primary data is longitudinal clinical records, longitudinal.
3. Otherwise, if its primary data is molecular/omics, AI4biology.
4. Otherwise, if it is mainly an agentic or tool-using system, AI_agent.
5. Otherwise, if it is mainly a language model or a text benchmark, LLM.
6. Otherwise, if it targets scientific discovery outside medicine, AI4Science.
7. Only if none of the above fits, multimodal.

Say which rule you applied, so the choice can be argued with.

## 4. Fill in the fields that need the paper read

Read the paper (and its supplementary) for these. Every one has a house rule.

**Work the access routes before concluding a paper is unreachable.** "Paywalled"
is usually wrong, and settling for the abstract leaves fields empty that are
sitting in plain sight. In order:

**1. nature.com itself, with a browser User-Agent.** It 303s to
`?error=cookies_not_supported` and then serves the complete article — Results
and Methods included — for open-access papers. A default curl or library
User-Agent is what gets bounced, not you.

```bash
curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
  "https://www.nature.com/articles/s41591-026-04521-4"
```

**2. Springer supplements, no login.** Where Methods say "configurations are in
Supplementary Table 16", that table is fetchable. Derive the filename from the
DOI — `10.1038/s41586-024-08378-w` → journal `41586`, year `2024`, number `8378`
with leading zeros stripped — and read it with `pdftotext file.pdf -`. Try
`MOESM1` through `MOESM4`.

```bash
curl -sL "https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-08378-w/MediaObjects/41586_2024_8378_MOESM1_ESM.pdf" -o supp.pdf
```

**3. Europe PMC**, for the abstract and for PMC-deposited full text. Note its
`isOpenAccess` field goes stale — it says `N` for papers nature.com serves in
full, so treat it as a hint, not a verdict.

```bash
curl -s 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"<doi>"&resultType=core&format=json'
```

**4. Author-published artifacts** — the GitHub README and the HuggingFace model
card or `config.json`. For a parameter count these are often more explicit than
the paper, and they come from the same authors, so they are a citable source.
Say which component the number covers.

**5. OpenAlex / Semantic Scholar** to locate an OA copy elsewhere.

Only after all five: work from the abstract, leave `performance` empty, and add
a `verify` note naming the routes you tried. Never fill a field from a press
release, a secondary summary, or your own recollection. Elsevier and Lancet sit
behind Cloudflare or a CAPTCHA — do not attempt to defeat either; flag those for
a human with browser access.

- `model.name` — the name the authors give it. No name, use the method acronym.
- `params` — total parameter count, format `632M` / `4.6B`. Fill it from the
  paper, its supplement, or the authors' own model card or repo — all three are
  citable, and the supplement is where it usually hides. **Never infer one from
  a backbone name, never compute it, and never copy a figure another team's
  paper quotes about this model.** Leave it `null` only once you have worked the
  routes above and come up empty.
- `params_scope` — set this whenever the count covers one component rather than
  the released model: `tile enc.`, `slide enc.`, `MIL head`, `both towers`.
  Without it the scan table puts a 48.5M slide encoder next to a 632M tile
  encoder and invites the wrong conclusion. Omit for a whole model.
- `params_status` — required whenever `params` is null, because an empty cell
  otherwise reads as "nobody looked". `not published` once you have worked every
  route above and the authors state none; `n/a` when the paper introduces no
  model; `unchecked` if you are leaving it for someone else, which the validator
  will keep warning about until it is resolved.
- `backbone` — architecture in one line.
- `pretraining` — terms from the `pretraining` list in `data/vocab.yaml`.
  `pretraining_detail` — the recipe in one or two sentences.
- `pretraining_short` — the same recipe compressed to a table cell, ≤44
  characters: `DINOv2`, `iBOT → CoCa`, `BEiT-3 MIM → contrastive`. **Name the
  method, not the supervision paradigm.** "self-supervised" is true of nearly
  every model in this catalogue, so it tells a reader nothing. Where the authors
  genuinely describe no recipe, say what the system does instead
  (`WSI → molecular inference → hierarchy`). This is a summary of
  `pretraining_detail` and must not add a claim it does not support.
- `data.description` and `data.scale` — real integers from the paper. Use keys
  that say what was counted (`whole_slide_images`, `patients`, `image_text_pairs`).
  Drop the placeholder keys you do not need.
- `training_slides` — whole slides the model was *trained* on, ≤28 characters:
  `1.5M`, `60.5K`. Do not derive this from `data.scale` — half the papers here
  report an evaluation set in the same units, and printing one as the other is a
  silent factual error. When the model never sees a whole slide, say what it did
  see: `none (208K image–text)`. When the paper counts something else, say so:
  `not stated (8.2K patients)`.
- `tasks` — terms from the `tasks` list. `tasks_detail` — the specifics.
- `modalities` — terms from the `modalities` list.
- `performance` — headline benchmark results, as
  `{benchmark, metric, value, note}`. **Only numbers you can point to in the
  paper.** An empty list is correct and expected; a wrong number is not. This
  field is the one most likely to be silently fabricated, so if you are working
  from an abstract alone, leave it empty and say so.
- `verify` — a list of anything you could not confirm. Prefer writing an honest
  `verify` note over filling a field with a plausible guess; the note renders on
  the page and CI reports it, so it will get fixed.

Scholar links for `authors.first.scholar` / `authors.last.scholar` are nice but
optional. Do not invent a profile URL — leave `null` if you cannot find one.

## 5. Write, build, validate

Add the record to `data/<domain>.yaml` in date order (newest first), then:

```bash
python scripts/build.py
python scripts/validate.py --report
```

`build.py` regenerates the markdown — never edit `.md` files directly, they are
overwritten. `validate.py` must print `OK`. Fix any error it reports; warnings
are acceptable if you note why.

If the domain page has no `data/<slug>.yaml` yet, it is still hand-maintained
markdown. Either migrate the page first, or append a row to the existing table
in the same column order and say that you did.

## 6. Report back

Show a compact summary: model name, venue, date, target page, the routing rule
you used, anything in `verify`, and whether `performance` is empty and why.

Finish with the filename the paper's PDF needs in the maintainer's PDF
repository, from `python scripts/build.py --pdf-names <domain>`. Do not type the
convention by hand and do not commit the PDF here.
