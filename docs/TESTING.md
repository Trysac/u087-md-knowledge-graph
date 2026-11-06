# Testing

## Running

```sh
uv run pytest --cov=md_knowledge_graph   # tests with coverage report
uv run python scripts/check.py           # every gate, as CI runs it
```

## Policy

- Branch coverage of `src/md_knowledge_graph` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import md_knowledge_graph`) and assert observable effects: return values, raised exceptions with their `code`, and exit statuses.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Behaviour that the tests must cover

The test modules are not part of the reviewed source snapshot, so no test file names are asserted here. The required checks are:

- Wiki link forms: `[[target]]`, `[[target|label]]`, `[[target#heading]]`, embeds `![[target]]`, and adjacent links parsed separately; links inside fenced code and inline code are ignored.
- Inline tags: `#` must follow the line start or whitespace, names must contain a non-digit, and `# ` is a heading.
- Resolution by stem, path and alias; `ambiguous` and `missing` broken links.
- Orphans, including a note that links only to itself.
- Byte-identical JSON across runs, with frontmatter dates written as ISO strings.
- Frontmatter errors with code `frontmatter` in strict mode and warnings otherwise; anchors, aliases and non-string keys rejected.
- CLI `--check` exit status 1 when outputs differ and 0 when byte-equal.
- INDEX.md escaping of titles, and exclusion of symlinks that leave the root.
