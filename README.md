# biomedical-ai-pipeline

Tooling for [medfm-flare/AwesomeBiomedicalAI](https://github.com/medfm-flare/AwesomeBiomedicalAI).

The catalogue repository holds nothing but its markdown pages — no scripts, no
data, no CI. Everything that generates those pages lives here: the schema, the
controlled vocabularies, the per-paper records, and the agent prompts that turn
a paper link into an entry.

## Two repositories

```
Development/
├── biomedical-ai-pipeline/     ← this one: source of truth
│   ├── data/                     domains.yaml, vocab.yaml, <domain>.yaml
│   ├── scripts/                  build, validate, discover, fetch_meta
│   └── .claude/commands/         /add-paper, /weekly-scan
└── AwesomeBiomedicalAI/        ← published catalogue: markdown only
    ├── README.md                 generated
    └── pathology.md              generated
```

Clone them side by side and the default path works. Anywhere else, point at the
catalogue explicitly:

```bash
export CATALOGUE_PATH=/path/to/AwesomeBiomedicalAI
```

The build fails with that message rather than writing pages into a directory
nobody is watching.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Everyday use

```bash
.venv/bin/python scripts/build.py              # regenerate the catalogue markdown
.venv/bin/python scripts/validate.py --report  # schema, vocabulary, duplicates
```

`/weekly-scan` in Claude Code runs the whole weekly loop: scan, triage with you,
add what you approve, build, validate, open a PR. `/add-paper <link>` handles a
single paper. Neither needs an API key.

## Why the split

A paper's record is the source of truth and the markdown is a build artifact, so
the record has to be versioned somewhere. Keeping it here rather than
`.gitignore`-ing it inside the catalogue means it survives a lost laptop, is
reviewable in a pull request, and can be validated by CI.

The trade is that the catalogue no longer validates its own contents on push —
that check moved here, where the data lives. Never hand-edit a generated page in
the catalogue: the next build overwrites it.

Field reference, house rules and the routing table: [CONTRIBUTING.md](CONTRIBUTING.md).
