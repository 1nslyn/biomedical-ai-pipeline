---
description: Run the weekly paper scan for your own page — discover, triage with me, and open a PR
argument-hint: "[domain] [days back, default 7]"
---

Run this week's paper scan. `$ARGUMENTS` may name the domain page and how many
days back to look; default to 7 days.

**One paper, one page, one maintainer.** Nine people share this repository and
each owns exactly one page, so this command works on one page at a time.
Resolve the domain in this order and say which you used:

1. the slug in `$ARGUMENTS`, if given;
2. otherwise the page whose maintainer in `data/domains.yaml` has a `github:`
   matching `gh api user --jq .login`, or whose name matches `git config
   user.name`;
3. otherwise ask, and stop. Do not guess, and do not default to every page.

Candidates for other people's pages are **out of scope**. List them in one line
at the end so the owner can be told, then leave them alone.

This runs entirely on the local machine and the Claude Code subscription. No
API key, no repo secret, no billing beyond the session you are already in. It is
the everyday version of `.github/workflows/add-approved.yml`, which stays parked
until the team moves to a shared server.

## 1. Scan

```bash
python scripts/discover.py --days <n> --json /tmp/candidates.json --dry-run
```

PubMed only, which is the Nature and Science families per `data/vocab.yaml`.
Add `--include-preprints` if the user asks for bioRxiv and medRxiv, and
`--include-broad-journals` for Cell, NEJM, Lancet, JAMA and PNAS. Both widen the
list a lot, so only when asked.

Candidates arrive unrouted — that is expected. The API-based routing inside
`discover.py` is for unattended CI. You are the router here.

## 2. Triage

Read `/tmp/candidates.json` and, for each candidate, decide:

- **Which page**, by the routing rules in `.claude/commands/add-paper.md`.
  Apply them honestly — routing a paper to your page because it is nearly a fit
  is how two maintainers end up cataloguing it twice. When a call is genuinely
  close, say so rather than deciding silently.
- **Worth adding?** Only for candidates that land on your page. This catalogue
  is models and systems: a clinical trial report, a commentary or Perspective,
  a benchmark of an existing model with no new artifact, or a paper whose AI
  content is a single logistic regression is usually a skip. Skipping is the
  common case: a typical week is around 30 candidates and a handful belong here,
  most of those on someone else's page. A week with nothing for you is a normal
  result, not a failed scan — report it plainly and stop.

Then show a compact table of **your page's** candidates — title, venue, date,
one-line reason — recommendations marked, best first. Ask which to add. **Do not
add anything before they answer.** The value of this catalogue is that a person
vouched for every row.

Below it, one line per candidate that belongs to another page: title, venue and
whose page it is. No recommendation and no research on those — just enough that
the owner can be pointed at it.

### Unattended runs

If this was started by `/loop`, a cron job or a scheduled agent, there is nobody
to answer. Do not stall waiting and do not skip the week. Instead:

- add the candidates you would have recommended, and only those;
- put the table you would have shown into the PR description, skipped papers
  and reasons included, so the whole judgment call is reviewable;
- title the PR so it is obvious no human triaged it yet, e.g.
  `papers(pathology): 2 candidates, agent-triaged`.

The human gate moves from this conversation to PR review. It does not disappear
— an unattended run must never merge its own PR. Everything else, including
every "leave it empty and write a verify note" rule below, is unchanged.

## 3. Add the approved ones

For each approved link, follow `.claude/commands/add-paper.md` exactly. Every
house rule there applies: bibliographic fields from `scripts/fetch_meta.py`
rather than memory, `params` only when the paper states it, `performance` only
with numbers you can point at, honest `verify` notes for the rest.

### When you cannot reach the full text

Rarer than it looks. `add-paper.md` lists five access routes and most Nature
papers fall to the first two — a browser User-Agent on nature.com, and the
Springer supplement host. Work all five before calling a paper unreachable;
stopping at the abstract is how fields end up empty that were never actually
gated.

When a paper really is blocked — Elsevier and Lancet sit behind Cloudflare and a
CAPTCHA, which you do not attempt to defeat:

1. Fill everything the accessible sources support.
2. Leave `performance` empty and add a `verify` note naming the routes tried.
3. Collect the paper in the handoff list below so a human with browser or
   institutional access can finish it.

## 4. Build, validate, branch

```bash
python scripts/build.py
python scripts/validate.py --report
```

Both must pass.

**Two repositories, so two commits.** The record you wrote lives here; the
markdown it generates lives in the catalogue checkout (`CATALOGUE_PATH`, or the
sibling directory by default). Use the same branch name in both:

1. In **this** repository, branch `papers/<yyyy-mm-dd>` and commit the
   `data/<domain>.yaml` change. This is the one that matters — it is the source
   of truth and the thing worth reviewing.
2. In the **catalogue**, branch `papers/<yyyy-mm-dd>` and commit only the
   regenerated `.md`. Never add a script, a data file or a workflow there; that
   repository is markdown and nothing else, by agreement.
3. Open a PR on each with `gh pr create`, each linking the other, requesting
   review from the page's maintainers where `github:` is filled in
   `data/domains.yaml`.

If `gh` is not authenticated, stop at the branches and print the exact push
commands. Check whose account `gh` belongs to before opening anything — on a
shared machine it is often not yours, and a PR from someone else's account is
worse than no PR.

If nothing was approved, say so and stop. Do not open an empty PR — a bot that
files noise every week is a bot everyone mutes.

Never commit to `main` in either repository. Never merge.

## 5. Hand back

Report:

- what was added, per page, with the routing rule used;
- every `verify` note created;
- **PDFs to collect** — for each added paper, the filename its PDF needs in the
  maintainer's PDF repository. Get these from
  `python scripts/build.py --pdf-names <domain>`; never type the convention by
  hand. Flag which ones need institutional access.
- what you skipped and why, in one line each, so the user can overrule you.
