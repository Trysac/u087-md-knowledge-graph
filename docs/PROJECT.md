# Project record

## Objective

Build an INDEX.md and a JSON graph from Markdown notes with YAML frontmatter and wiki links, reporting broken links and orphans. The tool is deterministic and runs without an editor, so it can be used in scripts and CI.

## Scope

- In scope: parsing frontmatter, titles, tags and wiki links; building the link graph; reporting broken links and orphans; rendering INDEX.md and JSON; the `md-knowledge-graph` command line options `--index`, `--json`, `--group-by`, `--strict` and `--check`.
- Out of scope: embeddings, HTML output, and editing notes. Runtime dependencies beyond PyYAML need an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 508363 / 144788 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.0670 |

## Factory run u087 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2600 | 126464 | 0 | 4246 | 0.6353 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 792 | 8081 | 43149 | 0.0324 |
| fix-2 | claude-sonnet-5-5 | no | 10 | 1694 | 9162 | 73327 | 0.0472 |
| fix-3 | claude-sonnet-5-5 | no | 4 | 263 | 5732 | 24680 | 0.0194 |
| fix-4 | claude-sonnet-5-5 | no | 6 | 858 | 7647 | 41011 | 0.0318 |
| audit | claude-sonnet-5-5 | no | 14 | 6678 | 48994 | 170667 | 0.2064 |
| docs | claude-haiku-5-5 | no | 148643 | 8039 | 0 | 0 | 0.0944 |

Total: $1.0670. Prices: Anthropic list prices.
